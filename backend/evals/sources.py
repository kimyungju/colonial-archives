"""Expand truncated citation spans to full chunk texts for the judge.

ArchiveCitation.text_span is truncated to 300 chars by the API, which made
the faithfulness judge score answers against fragments (FINDINGS.md Gap 2).
Citations carry doc_id but not chunk_id, so we recover the full text by
prefix-matching the span against the doc's chunk file in GCS. Falls back to
the span itself for graph citations (empty doc_id) or when GCS/matching
fails — the judge then sees at worst what it saw before.
"""

from __future__ import annotations

import asyncio
import json
import logging

from app.services.storage import storage_service

logger = logging.getLogger(__name__)


async def full_texts_for_citations(citations) -> list[str]:
    """Return one source text per citation, expanded to the full chunk text
    where the truncated span can be matched back to its chunk."""
    doc_ids = sorted({c.doc_id for c in citations if c.doc_id})

    async def _download(doc_id: str) -> tuple[str, list[dict]]:
        blob = storage_service._bucket.blob(f"chunks/{doc_id}.json")
        loop = asyncio.get_event_loop()
        try:
            raw = await loop.run_in_executor(None, blob.download_as_text)
            return doc_id, json.loads(raw)
        except Exception:  # noqa: BLE001
            logger.warning("Could not load chunks for %s; using spans", doc_id)
            return doc_id, []

    results = await asyncio.gather(*[_download(d) for d in doc_ids])
    chunks_by_doc: dict[str, list[dict]] = dict(results)

    texts: list[str] = []
    for cite in citations:
        full = None
        if cite.doc_id and cite.text_span:
            for chunk in chunks_by_doc.get(cite.doc_id, []):
                if chunk.get("text", "").startswith(cite.text_span):
                    full = chunk["text"]
                    break
        texts.append(full or cite.text_span)
    return texts
