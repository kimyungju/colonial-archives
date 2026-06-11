"""Hybrid retrieval service for the Colonial Archives Graph-RAG backend.

Phase 2 implementation: parallel vector search + Neo4j graph traversal,
combined relevance scoring, and GraphPayload in the response.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from collections import defaultdict

from app.config.logging_config import log_stage
from app.config.settings import settings
from app.models.schemas import (
    ArchiveCitation,
    GraphEdge,
    GraphNode,
    GraphPayload,
    QueryResponse,
    WebCitation,
)
from app.services.embeddings import embeddings_service
from app.services.llm import llm_service
from app.services.neo4j_service import neo4j_service
from app.services.reranker import reranker_service
from app.services.storage import storage_service
from app.services.vector_search import vector_search_service
from app.services.web_search import web_search_service

logger = logging.getLogger(__name__)

FALLBACK_ANSWER = "I cannot answer this based on the available sources."


class HybridRetrievalService:
    """Orchestrates vector search, graph traversal, and answer generation.

    Pipeline:
        1. Embed query
        2a. Vector search (parallel)
        2b. Graph traversal from entity hints (parallel)
        3. Merge + score results
        4. Generate answer via LLM
        5. Build response with citations and graph payload
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def query(
        self,
        question: str,
        filter_categories: list[str] | None = None,
    ) -> QueryResponse:
        """Run the full hybrid-retrieval pipeline and return a QueryResponse."""

        # Step 0 — Check for full-text page requests (bypass LLM entirely).
        full_text_result = await self._try_full_text_request(question)
        if full_text_result is not None:
            return full_text_result

        # Step 1 — Embed the question.
        with log_stage("query_embed", logger=logger):
            query_embedding: list[float] = await embeddings_service.embed_query(question)

        # Step 1b — Extract entity hints from the question (simple keyword extraction).
        entity_hints = self._extract_entity_hints(question)
        logger.info("Entity hints from question: %s", entity_hints)

        # Step 2 — Parallel: vector search + graph traversal.
        async def _timed_vector():
            with log_stage("vector_search", logger=logger):
                # With the reranker on, over-fetch candidates so the
                # cross-encoder has a real pool to rerank down to TOP_N.
                top_k = (
                    settings.RERANK_CANDIDATES if settings.RERANKER_ENABLED else None
                )
                return await vector_search_service.search(
                    query_embedding, top_k=top_k, filter_categories=filter_categories
                )

        async def _timed_graph():
            with log_stage("graph_search", logger=logger):
                return await self._graph_search(entity_hints, filter_categories)

        vector_results, graph_result = await asyncio.gather(
            asyncio.wait_for(_timed_vector(), timeout=30),
            asyncio.wait_for(_timed_graph(), timeout=15),
            return_exceptions=True,
        )

        # Handle exceptions from parallel tasks
        if isinstance(vector_results, BaseException):
            logger.warning("Vector search failed: %s", vector_results)
            vector_results = []
        if isinstance(graph_result, BaseException):
            logger.warning("Graph search failed: %s", graph_result)
            graph_result = {"payload": None, "context_chunks": []}

        # Step 3 — Early exit when there are no results.
        if not vector_results and not graph_result.get("context_chunks"):
            logger.info("No results for question; returning fallback")
            return QueryResponse(
                answer=FALLBACK_ANSWER,
                source_type="archive",
                citations=[],
                graph=None,
            )

        # Step 4 — Load chunk texts from GCS for vector results.
        vector_context: list[dict] = []
        if vector_results:
            vector_context = await self._load_chunk_contexts(vector_results)

        # Step 5a — Cross-encoder rerank of vector chunks (graph "Entity:"
        # chunks are synthetic evidence on a different score scale; they
        # pass through unreranked). The max score doubles as the relevance
        # signal for the out-of-corpus gate below.
        rerank_max_score: float | None = None
        if settings.RERANKER_ENABLED and vector_context:
            try:
                with log_stage("rerank", logger=logger):
                    vector_context, rerank_max_score = await reranker_service.rerank(
                        question, vector_context, settings.RERANK_TOP_N
                    )
                # The cross-encoder score is the better relevance estimate;
                # surface it as the citation confidence (same [0,1],
                # higher-better semantics as the vector similarity).
                for chunk in vector_context:
                    chunk["confidence"] = chunk["rerank_score"]
            except Exception:
                logger.exception("Reranker failed; using unreranked vector context")
                rerank_max_score = None

        # Step 5b — Merge vector + graph context chunks, deduplicate.
        graph_context = graph_result.get("context_chunks", [])
        merged_context = self._merge_contexts(vector_context, graph_context)

        # Step 6 — Compute combined relevance score.
        vector_score = 0.0
        if vector_results:
            avg_distance = sum(r["distance"] for r in vector_results) / len(
                vector_results
            )
            vector_score = max(1.0 - avg_distance, 0.0)

        graph_hit_ratio = 0.0
        if entity_hints and graph_context:
            graph_hit_ratio = min(len(graph_context) / max(len(entity_hints), 1), 1.0)

        # Phase 2 combined scoring
        if graph_context:
            relevance_score = vector_score * 0.6 + graph_hit_ratio * 0.4
        else:
            relevance_score = vector_score

        logger.info(
            "Relevance: vector=%.4f, graph_ratio=%.4f, combined=%.4f",
            vector_score,
            graph_hit_ratio,
            relevance_score,
        )

        # Step 6b — Out-of-corpus relevance gate (FINDINGS.md Gap 1). Two
        # corpus-tuned signals, either can gate; both default off:
        #   - min vector distance: even the closest chunk is farther than
        #     any in-domain query ever gets (the signal that actually
        #     separates on this corpus — see the Phase 1 sweep)
        #   - max rerank score: kept as an optional second signal
        # Gated queries skip the archive LLM (saves a Gemini call) and go
        # straight to the labelled web fallback.
        min_distance = (
            min(r["distance"] for r in vector_results) if vector_results else None
        )
        distance_gated = (
            settings.DISTANCE_GATE_THRESHOLD > 0.0
            and min_distance is not None
            and min_distance > settings.DISTANCE_GATE_THRESHOLD
        )
        rerank_gated = (
            settings.RERANKER_ENABLED
            and rerank_max_score is not None
            and rerank_max_score < settings.RERANK_GATE_THRESHOLD
        )
        gated = distance_gated or rerank_gated

        if gated:
            logger.info(
                "Relevance gate: min_distance=%s (threshold %.4f), "
                "max_rerank=%s (threshold %.4f); skipping archive answer",
                f"{min_distance:.4f}" if min_distance is not None else "n/a",
                settings.DISTANCE_GATE_THRESHOLD,
                f"{rerank_max_score:.4f}" if rerank_max_score is not None else "n/a",
                settings.RERANK_GATE_THRESHOLD,
            )
            answer_text = FALLBACK_ANSWER
        else:
            # Step 7 — Generate archive-only answer via LLM.
            with log_stage("llm_generation", logger=logger):
                llm_result: dict = await llm_service.generate_answer(
                    question, merged_context, source_type="archive"
                )
            answer_text = llm_result["answer"]

        # Step 8 — If archive couldn't answer (or was gated), try web fallback.
        web_context: list[dict] = []
        source_type = "archive"

        if (gated or answer_text.strip() == FALLBACK_ANSWER) and merged_context:
            logger.info("Archive could not answer; triggering web fallback")
            try:
                web_context = await web_search_service.search(question)
                if web_context:
                    from app.services.llm import WEB_FALLBACK_PROMPT

                    web_llm_result = await llm_service.generate_answer(
                        question, web_context, source_type="web_fallback",
                        prompt_template=WEB_FALLBACK_PROMPT,
                    )
                    web_answer = web_llm_result["answer"]
                    disclaimer = (
                        "The requested information was not found in the colonial "
                        "archive documents. Below is an answer based on web sources:\n\n"
                    )
                    answer_text = disclaimer + web_answer
                    source_type = "web_fallback"
                    merged_context = web_context
                    logger.info("Web fallback answer generated")
            except Exception:
                logger.exception("Web fallback failed")

        # A gated query must never go out with archive grounding. If the web
        # fallback could not produce an answer, abstain with no citations
        # (same shape as the no-results early exit in step 3).
        if gated and source_type == "archive":
            return QueryResponse(
                answer=FALLBACK_ANSWER,
                source_type="archive",
                citations=[],
                graph=None,
            )

        # Step 9 — Build citation list (archive + web).
        citations: list[ArchiveCitation | WebCitation] = []
        archive_idx = 0
        web_idx = 0

        for chunk in merged_context:
            cite_type = chunk.get("cite_type", "archive")
            if cite_type == "web":
                web_idx += 1
                citations.append(
                    WebCitation(
                        id=web_idx,
                        title=chunk.get("title", ""),
                        url=chunk.get("url", ""),
                    )
                )
            else:
                archive_idx += 1
                text_span = chunk.get("text", "")
                if len(text_span) > 300:
                    text_span = text_span[:300]
                citations.append(
                    ArchiveCitation(
                        id=archive_idx,
                        doc_id=chunk.get("doc_id", ""),
                        pages=chunk.get("pages", []),
                        text_span=text_span,
                        confidence=chunk.get("confidence", 0.0),
                    )
                )

        # Step 10 — Build graph payload (archive answers only; web fallback has no archive graph).
        graph_payload = graph_result.get("payload") if source_type != "web_fallback" else None

        return QueryResponse(
            answer=answer_text,
            source_type=source_type,
            citations=citations,
            graph=graph_payload,
        )

    # ------------------------------------------------------------------
    # Full-text page request detection
    # ------------------------------------------------------------------

    # Trigger phrases that indicate a full-text request
    _FULL_TEXT_TRIGGERS = re.compile(
        r"(?:full\s+text|show\s+(?:the\s+)?text|give\s+(?:me\s+)?(?:the\s+)?(?:full\s+)?text|"
        r"ocr\s+text|raw\s+text|exact\s+text|original\s+text|page\s+text|transcript)",
        re.IGNORECASE,
    )

    # Maximum pages to include in a single chat response
    _MAX_CHAT_PAGES = 20

    async def _try_full_text_request(self, question: str) -> QueryResponse | None:
        """Detect document retrieval requests and return OCR text directly.

        Bypasses RAG when:
        - A trigger phrase ("full text", "show text", etc.) AND a doc ref are found
        - A doc ref AND an explicit page spec are found (no trigger needed)

        Supports: single page, page range, and all pages.
        """
        from app.services.document_reference import parse_document_reference

        ref = parse_document_reference(question)
        if ref is None:
            return None

        # Require either a trigger phrase or explicit page spec
        has_trigger = self._FULL_TEXT_TRIGGERS.search(question)
        has_pages = ref.pages is not None
        if not has_trigger and not has_pages:
            return None

        doc_id = ref.doc_id
        logger.info("Full-text request detected: doc_id=%s, pages=%s", doc_id, ref.pages)

        # Fetch OCR data from GCS
        blob_path = f"ocr/{doc_id}_ocr.json"
        try:
            blob = storage_service._bucket.blob(blob_path)
            loop = asyncio.get_event_loop()
            raw = await loop.run_in_executor(None, blob.download_as_text)
            all_pages = json.loads(raw)
        except Exception:
            logger.warning("OCR data not found for %s", doc_id)
            return QueryResponse(
                answer=f"Document {doc_id} was not found in the archive collection. "
                       f"Please check the volume and file numbers.",
                source_type="archive",
                citations=[],
                graph=None,
            )

        total_pages = len(all_pages)

        if ref.pages is not None:
            # Single page or page range
            start, end = ref.pages
            selected = [p for p in all_pages if start <= p["page_number"] <= end]
            selected.sort(key=lambda p: p["page_number"])

            if not selected:
                if start == end:
                    return QueryResponse(
                        answer=f"Page {start} not found in {doc_id} (document has {total_pages} pages).",
                        source_type="archive",
                        citations=[],
                        graph=None,
                    )
                return QueryResponse(
                    answer=f"Pages {start}-{end} not found in {doc_id} (document has {total_pages} pages).",
                    source_type="archive",
                    citations=[],
                    graph=None,
                )
        else:
            # All pages
            selected = sorted(all_pages, key=lambda p: p["page_number"])

        # Pagination for very large documents
        truncated = False
        if len(selected) > self._MAX_CHAT_PAGES:
            selected = selected[: self._MAX_CHAT_PAGES]
            truncated = True

        # Build answer
        page_numbers = [p["page_number"] for p in selected]
        if len(selected) == 1:
            p = selected[0]
            header = f"**Full OCR text of {doc_id}, page {p['page_number']}:**"
            answer = f"{header}\n\n{p['text']}"
        else:
            if ref.pages is None:
                header = f"**Full OCR text of {doc_id}** ({total_pages} pages)"
            else:
                header = f"**OCR text of {doc_id}, pages {ref.pages[0]}-{ref.pages[1]}:**"
            parts = [header]
            for p in selected:
                parts.append(f"\n---\n**Page {p['page_number']}:**\n\n{p['text']}")
            answer = "\n".join(parts)

        if truncated:
            answer += (
                f"\n\n---\n*Showing pages {page_numbers[0]}-{page_numbers[-1]} "
                f"of {total_pages}. Ask for a specific page range to see more.*"
            )

        # Build citation
        span_text = selected[0]["text"][:300] if selected else ""
        citation = ArchiveCitation(
            id=1,
            doc_id=doc_id,
            pages=page_numbers,
            text_span=span_text,
            confidence=1.0,
        )

        return QueryResponse(
            answer=f"{answer} [archive:1]",
            source_type="archive",
            citations=[citation],
            graph=None,
        )

    # ------------------------------------------------------------------
    # Entity hint extraction
    # ------------------------------------------------------------------

    _STOP_WORDS = {
        "what", "who", "where", "when", "how", "why", "which",
        "does", "did", "was", "were", "are", "is", "the", "and",
        "for", "with", "from", "about", "into", "that", "this",
        "have", "has", "had", "can", "could", "would", "should",
        "tell", "describe", "explain", "me", "please",
        "a", "an", "of", "in", "on", "to", "by",
        "do", "be", "been", "being", "not", "no", "so",
        "they", "them", "their", "its", "our", "your", "my",
        "it", "he", "she", "we", "you", "his", "her",
        "also", "but", "or", "if", "then", "than", "very",
        "just", "more", "some", "any", "all", "each", "every",
        "much", "many", "most", "other", "only", "same",
        "there", "here", "will", "shall", "may", "might",
        "know", "think", "want", "need", "like", "make",
        "role", "work", "part", "thing", "time", "year",
    }

    # Cap to bound Neo4j fan-out from `search_entities` (one query per hint).
    # A long lowercase question can otherwise yield 20+ hints because
    # `question.title()` makes every word a multi-word regex match candidate.
    _MAX_ENTITY_HINTS = 6

    @staticmethod
    def _extract_entity_hints(question: str) -> list[str]:
        """Extract likely entity names from the question.

        Priority order (so the cap doesn't drop real entities):
          1. Multi-word phrases the user originally capitalised
             ("Sir Stamford Raffles", "Straits Settlements").
          2. Single capitalised words from the original input
             ("Singapore", "Opium").
          3. Lowercase fallback: 4+ char content words, non-stop-word,
             RANKED BY LENGTH (descending) before applying the cap.
             This ranking is a coarse heuristic — proper nouns
             ("Singapore", "Settlements", "Farquhar") tend to be longer
             than common nouns ("policy", "ports") that share the
             field. Without a ranking pass the first-six-in-question-
             order truncation drops real entities that appear later in
             a long sentence.

        Limitation: lowercase entity extraction is fundamentally
        ambiguous without a graph lookup. Word length is a weak
        proxy for "is this a proper noun". The Neo4j full-text index
        will still surface real entities at search time even if some
        regex hints are weak — `_graph_search` only fails when ALL
        hints miss, which is rare in practice. A future improvement
        is to feed the question text directly to
        ``db.index.fulltext.queryNodes`` and let Neo4j produce the
        candidate entity list.

        We deliberately skip the title-cased multi-word regex from the
        previous implementation: applying it to ``question.title()``
        produced noise hits like "What Was" and "Of The Opium" that
        starved the cap.
        """
        stop_words = HybridRetrievalService._STOP_WORDS
        max_hints = HybridRetrievalService._MAX_ENTITY_HINTS

        multi_pattern = r"\b(?:[A-Z][a-z.]+(?:\s+[A-Z][a-z.]+)+)\b"
        single_pattern = r"\b([A-Z][a-z]{2,})\b"

        hints: list[str] = []

        # Priority 1: multi-word proper-noun phrases in original casing
        for phrase in re.findall(multi_pattern, question):
            words = [w for w in phrase.split() if w.lower() not in stop_words]
            if not words:
                continue
            cleaned = " ".join(words)
            if cleaned not in hints:
                hints.append(cleaned)

        # Priority 2: single capitalised words from original casing
        for word in re.findall(single_pattern, question):
            if word.lower() in stop_words:
                continue
            if any(word.lower() in mw.lower() for mw in hints):
                continue
            hints.append(word)

        # If priorities 1+2 produced anything, return them — do NOT
        # dilute with lowercase fallback noise.
        if hints:
            return hints[:max_hints]

        # Priority 3: all-lowercase input fallback. Extract 4+ char
        # content words and rank by length DESCENDING (then by original
        # order for stable tie-break) before applying the cap.
        candidates: list[tuple[int, int, str]] = []
        seen_titled: set[str] = set()
        for idx, w in enumerate(re.findall(r"\b([a-zA-Z]{4,})\b", question)):
            if w.lower() in stop_words:
                continue
            titled = w.title()
            if titled in seen_titled:
                continue
            seen_titled.add(titled)
            candidates.append((-len(w), idx, titled))

        candidates.sort()
        return [titled for _len, _idx, titled in candidates[:max_hints]]

    # ------------------------------------------------------------------
    # Graph search
    # ------------------------------------------------------------------

    async def _graph_search(
        self,
        entity_hints: list[str],
        categories: list[str] | None,
    ) -> dict:
        """Search Neo4j for entities matching hints, return subgraph + context.

        Searches and subgraph fetches are parallelized via asyncio.gather.

        Returns a dict with ``payload`` (GraphPayload | None) and
        ``context_chunks`` (list of context dicts for LLM).
        """
        if not entity_hints:
            logger.debug("No entity hints extracted from query")
            return {"payload": None, "context_chunks": []}

        # --- Phase 1: Search all entity hints in parallel ---
        search_results = await asyncio.gather(*[
            neo4j_service.search_entities(hint, limit=5, categories=categories)
            for hint in entity_hints
        ], return_exceptions=True)

        # Collect seeds for subgraph fetches — use top 3 per hint, dedup, cap total
        MAX_SEEDS_PER_HINT = 3
        MAX_GRAPH_SEEDS = 8

        seeds: list[GraphNode] = []
        seen_seed_ids: set[str] = set()
        for hint, result in zip(entity_hints, search_results):
            if isinstance(result, BaseException) or not result:
                logger.debug("No Neo4j match for hint '%s'", hint)
                continue
            for node in result[:MAX_SEEDS_PER_HINT]:
                if node.canonical_id not in seen_seed_ids:
                    seen_seed_ids.add(node.canonical_id)
                    seeds.append(node)

        # Cap total seeds to limit Neo4j query volume
        if len(seeds) > MAX_GRAPH_SEEDS:
            seeds = seeds[:MAX_GRAPH_SEEDS]

        logger.info("Graph search: %d seeds from %d hints", len(seeds), len(entity_hints))

        if not seeds:
            return {"payload": None, "context_chunks": []}

        # --- Phase 2: Fetch all subgraphs in parallel ---
        subgraph_results = await asyncio.gather(*[
            neo4j_service.get_subgraph(seed.canonical_id, categories=categories)
            for seed in seeds
        ], return_exceptions=True)

        # --- Phase 3: Merge results ---
        all_nodes: dict[str, GraphNode] = {}
        all_edges: list[GraphEdge] = []
        context_chunks: list[dict] = []
        center_node: str | None = None

        for subgraph in subgraph_results:
            if isinstance(subgraph, BaseException) or subgraph is None:
                continue

            if center_node is None and subgraph.nodes:
                center_node = subgraph.nodes[0].canonical_id

            for node in subgraph.nodes:
                all_nodes[node.canonical_id] = node

            all_edges.extend(subgraph.edges)

            # Build context chunk from entity evidence for LLM grounding
            for node in subgraph.nodes:
                if node.highlighted:
                    context_chunks.append(
                        {
                            "id": node.canonical_id,
                            "text": f"Entity: {node.name}. "
                            + " ".join(
                                f"{k}: {v}" for k, v in node.attributes.items()
                            ),
                            "doc_id": "",
                            "pages": [],
                            "confidence": 0.8,
                            "cite_type": "archive",
                        }
                    )

        # Deduplicate edges
        seen_edges: set[str] = set()
        unique_edges: list[GraphEdge] = []
        for edge in all_edges:
            key = f"{edge.source}-{edge.type}-{edge.target}"
            if key not in seen_edges:
                seen_edges.add(key)
                unique_edges.append(edge)

        payload = None
        if all_nodes:
            payload = GraphPayload(
                nodes=list(all_nodes.values()),
                edges=unique_edges,
                center_node=center_node or "",
            )

        return {"payload": payload, "context_chunks": context_chunks}

    # ------------------------------------------------------------------
    # Context merging
    # ------------------------------------------------------------------

    @staticmethod
    def _merge_contexts(
        vector_context: list[dict],
        graph_context: list[dict],
    ) -> list[dict]:
        """Merge vector and graph context chunks, deduplicating by id."""
        seen_ids: set[str] = set()
        merged: list[dict] = []

        # Vector results take priority
        for chunk in vector_context:
            cid = chunk.get("id", "")
            if cid not in seen_ids:
                seen_ids.add(cid)
                merged.append(chunk)

        for chunk in graph_context:
            cid = chunk.get("id", "")
            if cid not in seen_ids:
                seen_ids.add(cid)
                merged.append(chunk)

        return merged

    # ------------------------------------------------------------------
    # GCS chunk loading (unchanged from Phase 1)
    # ------------------------------------------------------------------

    async def _load_chunk_contexts(
        self,
        vector_results: list[dict],
    ) -> list[dict]:
        """Load full chunk texts from GCS and merge with vector distances.

        Downloads are parallelized via asyncio.gather + run_in_executor.
        """

        distance_by_chunk: dict[str, float] = {
            r["id"]: r["distance"] for r in vector_results
        }

        doc_chunks: dict[str, list[str]] = defaultdict(list)
        for chunk_id in distance_by_chunk:
            parts = chunk_id.split("_chunk_", 1)
            doc_id = parts[0] if len(parts) == 2 else chunk_id
            doc_chunks[doc_id].append(chunk_id)

        # --- Parallel GCS downloads ---
        async def _download(doc_id: str) -> tuple[str, list[dict]]:
            blob_path = f"chunks/{doc_id}.json"
            try:
                blob = storage_service._bucket.blob(blob_path)
                loop = asyncio.get_event_loop()
                raw_text = await loop.run_in_executor(None, blob.download_as_text)
                return doc_id, json.loads(raw_text)
            except Exception:
                logger.warning(
                    "Failed to load chunk file from GCS: %s",
                    blob_path,
                    exc_info=True,
                )
                return doc_id, []

        results = await asyncio.gather(*[
            _download(doc_id) for doc_id in doc_chunks
        ])

        chunk_lookup: dict[str, dict] = {}
        for _doc_id, chunks_data in results:
            for chunk in chunks_data:
                cid = chunk.get("chunk_id", "")
                if cid in distance_by_chunk:
                    chunk_lookup[cid] = chunk

        # --- Build context list ---
        # The index uses COSINE_DISTANCE (lower = better). Expose confidence
        # as similarity (1 - distance) so higher = better, consistent with
        # the graph chunks' 0.8 and with vector_score in query() step 6.
        context_chunks: list[dict] = []
        for chunk_id, distance in distance_by_chunk.items():
            stored = chunk_lookup.get(chunk_id, {})
            parts = chunk_id.split("_chunk_", 1)
            doc_id = parts[0] if len(parts) == 2 else chunk_id

            context_chunks.append(
                {
                    "id": chunk_id,
                    "text": stored.get("text", ""),
                    "doc_id": doc_id,
                    "pages": stored.get("pages", []),
                    "confidence": max(1.0 - distance, 0.0),
                    "cite_type": "archive",
                }
            )

        context_chunks.sort(key=lambda c: c["confidence"], reverse=True)

        logger.info(
            "Loaded %d / %d chunk contexts from GCS",
            len(chunk_lookup),
            len(distance_by_chunk),
        )
        return context_chunks


# Module-level singleton
hybrid_retrieval_service = HybridRetrievalService()
