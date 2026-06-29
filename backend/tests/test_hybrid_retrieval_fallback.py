import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.hybrid_retrieval import HybridRetrievalService


@pytest.mark.asyncio
async def test_archive_fallback_without_web_results_has_no_archive_citations():
    service = HybridRetrievalService()

    with patch("app.services.hybrid_retrieval.vector_search_service") as mock_vs, \
         patch("app.services.hybrid_retrieval.embeddings_service") as mock_embed, \
         patch("app.services.hybrid_retrieval.neo4j_service") as mock_neo4j, \
         patch("app.services.hybrid_retrieval.storage_service") as mock_storage, \
         patch("app.services.hybrid_retrieval.llm_service") as mock_llm, \
         patch("app.services.hybrid_retrieval.web_search_service") as mock_web:

        mock_embed.embed_query = AsyncMock(return_value=[0.1] * 768)
        mock_vs.search = AsyncMock(return_value=[
            {"id": "doc_a_chunk_0", "distance": 0.3},
        ])
        mock_neo4j.search_entities = AsyncMock(return_value=[])

        mock_blob = MagicMock()
        mock_blob.download_as_text.return_value = json.dumps([
            {"chunk_id": "doc_a_chunk_0", "text": "Archive text.", "pages": [1]},
        ])
        mock_storage._bucket = MagicMock()
        mock_storage._bucket.blob.return_value = mock_blob

        archive_fallback = "I cannot answer this based on the available sources."
        mock_llm.generate_answer = AsyncMock(return_value={
            "answer": archive_fallback,
            "context_chunks": [],
        })
        mock_web.search = AsyncMock(return_value=[])

        result = await service.query("What is the population of Singapore in 2026?")

    assert result.answer == archive_fallback
    assert result.citations == []
    assert result.graph is None
