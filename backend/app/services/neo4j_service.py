"""Neo4j graph database service for the Colonial Archives Graph-RAG backend.

Manages entity and relationship storage using MERGE operations (never CREATE)
to ensure idempotent re-ingestion.  Provides subgraph traversal and entity
search for the query pipeline and graph API endpoints.
"""

from __future__ import annotations

import json
import logging

from neo4j import AsyncGraphDatabase

from app.config.settings import settings
from app.models.schemas import (
    Evidence,
    GraphEdge,
    GraphNode,
    GraphOverviewPayload,
    GraphPayload,
    OverviewNode,
)

logger = logging.getLogger(__name__)

_SUBGRAPH_RELATIONSHIP_LIMIT = 120


class Neo4jService:
    """Async Neo4j driver wrapper with MERGE-only write operations."""

    def __init__(self) -> None:
        self._driver = None

    @property
    def driver(self):
        if self._driver is None:
            self._driver = AsyncGraphDatabase.driver(
                settings.NEO4J_URI,
                auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
            )
            logger.info(
                "Neo4jService initialised (uri=%s)", settings.NEO4J_URI
            )
        return self._driver

    async def close(self) -> None:
        """Close the driver connection pool."""
        if self._driver is not None:
            await self._driver.close()
            logger.info("Neo4jService driver closed")

    async def verify_connectivity(self) -> bool:
        """Check that the driver can reach Neo4j."""
        try:
            await self.driver.verify_connectivity()
            return True
        except Exception:
            logger.warning("Neo4j connectivity check failed", exc_info=True)
            return False

    # ------------------------------------------------------------------
    # Write operations (MERGE only)
    # ------------------------------------------------------------------

    async def merge_entity(
        self,
        canonical_id: str,
        name: str,
        main_categories: list[str],
        sub_category: str | None,
        aliases: list[str],
        attributes: dict,
        evidence: Evidence,
    ) -> None:
        """MERGE an entity node.  Updates properties and appends aliases."""
        query = """
        MERGE (e:Entity {canonical_id: $canonical_id})
        SET e.name = $name,
            e.main_categories = $main_categories,
            e.sub_category = $sub_category,
            e.attributes = $attributes_json,
            e.evidence_doc_id = $evidence_doc_id,
            e.evidence_page = $evidence_page,
            e.evidence_text_span = $evidence_text_span,
            e.evidence_chunk_id = $evidence_chunk_id,
            e.evidence_confidence = $evidence_confidence
        WITH e
        // Append new aliases without duplicates
        SET e.aliases = [x IN
            coalesce(e.aliases, []) + $aliases
            WHERE x IS NOT NULL | x
        ]
        WITH e
        SET e.aliases = [x IN e.aliases WHERE x IS NOT NULL | x]
        WITH e, e.aliases AS raw
        UNWIND raw AS a
        WITH e, collect(DISTINCT a) AS unique_aliases
        SET e.aliases = unique_aliases
        """
        params = {
            "canonical_id": canonical_id,
            "name": name,
            "main_categories": main_categories,
            "sub_category": sub_category,
            "aliases": aliases,
            "attributes_json": json.dumps(attributes),
            "evidence_doc_id": evidence.doc_id,
            "evidence_page": evidence.page,
            "evidence_text_span": evidence.text_span,
            "evidence_chunk_id": evidence.chunk_id,
            "evidence_confidence": evidence.confidence,
        }
        async with self.driver.session() as session:
            await session.run(query, params)

        logger.debug("Merged entity %s (%s)", canonical_id, name)

    async def merge_relationship(
        self,
        source_canonical_id: str,
        target_canonical_id: str,
        rel_type: str,
        attributes: dict,
        evidence: Evidence,
    ) -> None:
        """MERGE a relationship between two entity nodes."""
        # Sanitise relationship type for Cypher (must be a valid identifier)
        safe_type = rel_type.upper().replace(" ", "_")
        safe_type = "".join(c for c in safe_type if c.isalnum() or c == "_")
        if not safe_type:
            safe_type = "RELATED_TO"

        # Neo4j does not support parameterised relationship types, so we use
        # APOC-free dynamic approach: MERGE with a generic label and store the
        # semantic type as a property.
        query = """
        MATCH (a:Entity {canonical_id: $source_id})
        MATCH (b:Entity {canonical_id: $target_id})
        MERGE (a)-[r:RELATED_TO {rel_type: $rel_type}]->(b)
        SET r.attributes = $attributes_json,
            r.evidence_doc_id = $evidence_doc_id,
            r.evidence_page = $evidence_page,
            r.evidence_text_span = $evidence_text_span,
            r.evidence_chunk_id = $evidence_chunk_id,
            r.evidence_confidence = $evidence_confidence
        """
        params = {
            "source_id": source_canonical_id,
            "target_id": target_canonical_id,
            "rel_type": safe_type,
            "attributes_json": json.dumps(attributes),
            "evidence_doc_id": evidence.doc_id,
            "evidence_page": evidence.page,
            "evidence_text_span": evidence.text_span,
            "evidence_chunk_id": evidence.chunk_id,
            "evidence_confidence": evidence.confidence,
        }
        async with self.driver.session() as session:
            await session.run(query, params)

        logger.debug(
            "Merged relationship %s -[%s]-> %s",
            source_canonical_id,
            safe_type,
            target_canonical_id,
        )

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    async def get_subgraph(
        self,
        canonical_id: str,
        depth: int | None = None,
        categories: list[str] | None = None,
        limit: int = _SUBGRAPH_RELATIONSHIP_LIMIT,
    ) -> GraphPayload | None:
        """Return a bounded one-hop neighborhood around an entity.

        The graph explorer calls this on click, so the query intentionally
        avoids variable-length traversal. Neo4j filters categories before the
        limit, then returns compact row maps for payload assembly.
        """
        _ = depth
        relationship_limit = max(1, min(limit, 300))

        cypher = """
        MATCH (center:Entity {canonical_id: $canonical_id})
        OPTIONAL MATCH (center)-[r:RELATED_TO]-(neighbor:Entity)
        WHERE neighbor IS NULL
           OR size($categories) = 0
           OR any(c IN coalesce(neighbor.main_categories, [])
                  WHERE c IN $categories)
        WITH center, neighbor, r
        ORDER BY coalesce(r.evidence_confidence, 0) DESC,
                 coalesce(neighbor.name, "")
        WITH center, collect({neighbor: neighbor, rel: r})[..$limit] AS rows
        RETURN center, rows
        """
        params = {
            "canonical_id": canonical_id,
            "categories": categories or [],
            "limit": relationship_limit,
        }

        async with self.driver.session() as session:
            result = await session.run(cypher, params)
            record = await result.single()

        if record is None:
            return None

        center_node = record["center"]
        nodes_map: dict[str, GraphNode] = {
            canonical_id: self._record_to_graph_node(center_node, highlighted=True),
        }

        rows = record["rows"] or []
        relationships = []

        for row in rows:
            if row is None:
                continue
            neighbor = row.get("neighbor")
            rel = row.get("rel")
            if neighbor is None:
                continue
            nid = neighbor.get("canonical_id", "")
            if not nid or nid in nodes_map:
                if rel is not None:
                    relationships.append(rel)
                continue
            node = self._record_to_graph_node(neighbor, highlighted=False)
            nodes_map[nid] = node
            if rel is not None:
                relationships.append(rel)

        edges: list[GraphEdge] = []
        seen_edges: set[str] = set()

        for rel in relationships:
            if rel is None:
                continue
            source_id = rel.start_node.get("canonical_id", "") if rel.start_node else ""
            target_id = rel.end_node.get("canonical_id", "") if rel.end_node else ""
            rel_type = rel.get("rel_type") or rel.type or "RELATED_TO"

            if source_id not in nodes_map or target_id not in nodes_map:
                continue

            edge_key = f"{source_id}-{rel_type}-{target_id}"
            if edge_key in seen_edges:
                continue
            seen_edges.add(edge_key)

            attrs: dict = {}
            raw_attrs = rel.get("attributes")
            if raw_attrs:
                try:
                    attrs = json.loads(raw_attrs)
                except (json.JSONDecodeError, TypeError):
                    pass

            edges.append(
                GraphEdge(
                    id=f"edge_{rel.element_id}",
                    source=source_id,
                    target=target_id,
                    type=rel_type,
                    attributes=attrs,
                    highlighted=(
                        source_id == canonical_id or target_id == canonical_id
                    ),
                )
            )

        return GraphPayload(
            nodes=list(nodes_map.values()),
            edges=edges,
            center_node=canonical_id,
        )

    async def search_entities(
        self,
        query_text: str,
        limit: int = 20,
        categories: list[str] | None = None,
    ) -> list[GraphNode]:
        """Search entities by name or alias.

        Hot path is full-text only. Legacy CONTAINS runs ONLY as a
        gated fallback when:
          * the sanitiser yields no usable Lucene tokens, or
          * the full-text call raises a missing/populating-index error
            (deploy-window safety net for B1 not-yet-applied).

        Any other full-text error propagates — those are real bugs and
        masking them with a label-scan would just hide outages while
        doubling Neo4j load. An earlier draft of this method ran legacy
        in parallel for every query; that was rejected because
        ``_graph_search`` already fans out one ``search_entities`` call
        per entity hint (cap 6 from D1), so always-parallel meant up to
        12 concurrent Neo4j queries per user question — half of them
        the same label scan the migration was supposed to retire.
        """
        if not query_text or not query_text.strip():
            return []

        sanitised = self._sanitise_fulltext_query(query_text)
        if not sanitised:
            # No usable Lucene tokens (e.g. all reserved chars or all <2 chars).
            return await self._search_entities_legacy(query_text, limit, categories)

        try:
            return await self._run_fulltext_query(sanitised, limit, categories)
        except Exception as exc:
            if self._is_missing_index_error(exc):
                logger.warning(
                    "Fulltext index 'entity_name_fulltext' unavailable "
                    "(%s); falling back to legacy CONTAINS scan. "
                    "Run scripts/neo4j_migration.py to re-enable fast path.",
                    exc,
                )
                return await self._search_entities_legacy(query_text, limit, categories)
            # Unrecognised error — propagate rather than mask with a slow path.
            raise

    async def _run_fulltext_query(
        self,
        sanitised: str,
        limit: int,
        categories: list[str] | None,
    ) -> list[GraphNode]:
        """Run the full-text Cypher and return GraphNodes.

        Pushes category filter into Cypher BEFORE ``LIMIT $limit`` so
        small-limit callers don't get starved by high-scored out-of-
        category hits.
        """
        cypher = """
        CALL db.index.fulltext.queryNodes('entity_name_fulltext', $search_term)
        YIELD node, score
        WHERE size($categories) = 0
           OR any(c IN coalesce(node.main_categories, [])
                  WHERE c IN $categories)
        RETURN node AS e, score
        ORDER BY score DESC
        LIMIT $limit
        """
        params = {
            "search_term": sanitised,
            "limit": limit,
            "categories": categories or [],
        }

        async with self.driver.session() as session:
            result = await session.run(cypher, params)
            records = [r async for r in result]

        return [
            self._record_to_graph_node(rec["e"], highlighted=False)
            for rec in records
        ]

    @staticmethod
    def _is_missing_index_error(exc: Exception) -> bool:
        """Identify the Neo4j error raised when a full-text index does not
        exist or is still in the POPULATING state.

        Matches Neo4jError messages by substring rather than by code so the
        guard works across driver versions and minor wording changes.

        We normalise the message before matching:
          * lowercase (Neo4j sometimes capitalises ``IndexNotFound``)
          * strip hyphens (Neo4j docs say "full-text" but the runtime error
            string says "fulltext"; either may surface in future versions)
          * collapse whitespace (multi-line errors)
        """
        raw = str(exc).lower().replace("-", "")
        msg = " ".join(raw.split())
        return any(
            needle in msg
            for needle in (
                "no such fulltext schema index",
                "no such fulltext index",
                "no such index",
                "indexnotfound",
                "populat",
            )
        )

    async def _search_entities_legacy(
        self,
        query_text: str,
        limit: int,
        categories: list[str] | None,
    ) -> list[GraphNode]:
        """Pre-fulltext-index entity search. Kept as a fallback path for
        deploys where ``scripts/neo4j_migration.py`` has not run yet or
        the index is still being built. Slower than the full-text path
        (label scan over Entity.name and aliases) but functionally
        equivalent for the common case.

        Category filtering happens INSIDE the Cypher WHERE clause, BEFORE
        ``LIMIT``. Filtering in Python after ``LIMIT`` (which the original
        pre-plan implementation did) can starve small-limit callers when
        higher-confidence out-of-category rows occupy the top-N. The
        full-text path applies the same in-Cypher filter for parity.
        """
        search_term = query_text.lower()

        cypher = """
        MATCH (e:Entity)
        WHERE (toLower(e.name) CONTAINS $search_term
               OR any(alias IN coalesce(e.aliases, [])
                      WHERE toLower(alias) CONTAINS $search_term))
          AND (size($categories) = 0
               OR any(c IN coalesce(e.main_categories, [])
                      WHERE c IN $categories))
        RETURN e
        ORDER BY e.evidence_confidence DESC
        LIMIT $limit
        """
        params = {
            "search_term": search_term,
            "limit": limit,
            "categories": categories or [],
        }
        async with self.driver.session() as session:
            result = await session.run(cypher, params)
            records = [r async for r in result]

        return [self._record_to_graph_node(rec["e"], highlighted=False) for rec in records]

    # Lucene reserved characters that must be escaped or stripped before
    # being passed to db.index.fulltext.queryNodes.
    _LUCENE_RESERVED = set('+-&|!(){}[]^"~*?:\\/')

    @staticmethod
    def _sanitise_fulltext_query(text: str) -> str:
        """Strip Lucene specials, lowercase tokens, drop short ones,
        OR-combine the rest with prefix-wildcard and fuzzy operators.

        Lowercasing is critical: Lucene treats ``AND``/``OR``/``NOT``/``TO``
        as case-sensitive operator keywords. A user typing "AND" or
        "Singapore AND Penang" would otherwise inject those tokens as
        operators or trigger a parse error. Lowercasing turns them into
        ordinary terms that match the analyzer-lowercased index content.

        Tokens are joined by whitespace, which Lucene treats as the default
        OR operator. We deliberately avoid emitting an explicit ``OR``
        separator so the sanitised string never contains the uppercase
        operator keyword — that keeps a user-supplied ``"OR"`` from being
        confused with our join token in tests and logs.

        Example::

            "Raffles opium" -> "raffles* raffles~1 opium* opium~1"
            "AND OR NOT"    -> "and* and~1 or* or~1 not* not~1"
        """
        if not text:
            return ""
        cleaned = "".join(
            c if c not in Neo4jService._LUCENE_RESERVED else " " for c in text
        )
        tokens = [t.lower() for t in cleaned.split() if len(t) >= 2]
        if not tokens:
            return ""
        return " ".join(f"{t}* {t}~1" for t in tokens)

    async def get_all_entity_names(self) -> list[dict]:
        """Return all entity canonical_ids, names, and aliases for normalization."""
        cypher = """
        MATCH (e:Entity)
        RETURN e.canonical_id AS canonical_id,
               e.name AS name,
               coalesce(e.aliases, []) AS aliases
        """
        async with self.driver.session() as session:
            result = await session.run(cypher)
            records = [r async for r in result]

        return [
            {
                "canonical_id": rec["canonical_id"],
                "name": rec["name"],
                "aliases": list(rec["aliases"]),
            }
            for rec in records
        ]

    async def get_entity_ids_with_prefix(self, prefix: str) -> list[str]:
        """Return all canonical_ids starting with *prefix*."""
        cypher = """
        MATCH (e:Entity)
        WHERE e.canonical_id STARTS WITH $prefix
        RETURN e.canonical_id AS canonical_id
        """
        async with self.driver.session() as session:
            result = await session.run(cypher, {"prefix": prefix})
            records = [r async for r in result]

        return [rec["canonical_id"] for rec in records]

    async def get_overview_graph(self) -> GraphOverviewPayload:
        """Return all entities and relationships for the overview visualization.

        Each node includes a connection_count (number of relationships) so the
        frontend can size nodes proportionally. Node and edge queries run in
        parallel to halve the round-trip overhead.
        """
        import asyncio

        async def _fetch_nodes() -> list[OverviewNode]:
            async with self.driver.session() as session:
                result = await session.run(
                    """
                    MATCH (e:Entity)
                    OPTIONAL MATCH (e)-[r:RELATED_TO]-()
                    WITH e, count(r) AS connection_count
                    RETURN e.canonical_id AS canonical_id,
                           e.name AS name,
                           coalesce(e.main_categories, []) AS main_categories,
                           e.sub_category AS sub_category,
                           connection_count,
                           e.evidence_doc_id AS evidence_doc_id,
                           e.evidence_page AS evidence_page
                    ORDER BY connection_count DESC
                    """
                )
                return [
                    OverviewNode(
                        canonical_id=rec["canonical_id"],
                        name=rec["name"],
                        main_categories=list(rec["main_categories"]),
                        sub_category=rec.get("sub_category"),
                        connection_count=rec["connection_count"],
                        evidence_doc_id=rec.get("evidence_doc_id"),
                        evidence_page=rec.get("evidence_page"),
                    )
                    async for rec in result
                ]

        async def _fetch_edges() -> list[GraphEdge]:
            async with self.driver.session() as session:
                result = await session.run(
                    """
                    MATCH (a:Entity)-[r:RELATED_TO]->(b:Entity)
                    RETURN a.canonical_id AS source_id,
                           b.canonical_id AS target_id,
                           r.rel_type AS rel_type
                    """
                )
                edges = []
                idx = 0
                async for rec in result:
                    edges.append(
                        GraphEdge(
                            id=f"overview_edge_{idx}",
                            source=rec["source_id"],
                            target=rec["target_id"],
                            type=rec["rel_type"] or "RELATED_TO",
                            attributes={},
                            highlighted=False,
                        )
                    )
                    idx += 1
                return edges

        nodes, edges = await asyncio.gather(_fetch_nodes(), _fetch_edges())

        logger.info(
            "Overview graph: %d nodes, %d edges", len(nodes), len(edges)
        )
        return GraphOverviewPayload(nodes=nodes, edges=edges)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _record_to_graph_node(
        node_record,
        highlighted: bool = False,
    ) -> GraphNode:
        """Convert a Neo4j node record to a GraphNode Pydantic model."""
        attrs = {}
        raw_attrs = node_record.get("attributes")
        if raw_attrs:
            try:
                attrs = json.loads(raw_attrs)
            except (json.JSONDecodeError, TypeError):
                pass

        return GraphNode(
            canonical_id=node_record.get("canonical_id", ""),
            name=node_record.get("name", ""),
            main_categories=list(node_record.get("main_categories", [])),
            sub_category=node_record.get("sub_category"),
            attributes=attrs,
            highlighted=highlighted,
            evidence_doc_id=node_record.get("evidence_doc_id"),
            evidence_page=node_record.get("evidence_page"),
            evidence_text_span=node_record.get("evidence_text_span"),
            evidence_confidence=node_record.get("evidence_confidence"),
        )


# Module-level singleton
neo4j_service = Neo4jService()
