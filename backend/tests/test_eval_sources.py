"""Tests for expanding truncated citation spans to full chunk texts.

Gap 2: the faithfulness judge previously saw only the 300-char
ArchiveCitation.text_span, making faithfulness an artificial lower bound.
full_texts_for_citations recovers the full chunk text from GCS by
prefix-matching the span against the doc's chunk file.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from evals.sources import full_texts_for_citations


class FakeCitation:
    def __init__(self, doc_id, text_span):
        self.doc_id = doc_id
        self.text_span = text_span


FULL_TEXT = "A" * 300 + " and the rest of the chunk that was truncated away."


@pytest.fixture
def mock_storage():
    chunks_by_path = {
        "chunks/doc_x.json": json.dumps([
            {"chunk_id": "doc_x_chunk_0", "text": FULL_TEXT, "pages": [1]},
            {"chunk_id": "doc_x_chunk_1", "text": "Unrelated chunk text.", "pages": [2]},
        ]),
    }

    mock_bucket = MagicMock()

    def fake_blob(path):
        blob = MagicMock()
        if path in chunks_by_path:
            blob.download_as_text.return_value = chunks_by_path[path]
        else:
            blob.download_as_text.side_effect = Exception("not found")
        return blob

    mock_bucket.blob.side_effect = fake_blob

    with patch("evals.sources.storage_service") as mock_svc:
        mock_svc._bucket = mock_bucket
        yield mock_bucket


class TestFullTextsForCitations:
    @pytest.mark.asyncio
    async def test_expands_truncated_span_to_full_chunk_text(self, mock_storage):
        cite = FakeCitation("doc_x", FULL_TEXT[:300])
        texts = await full_texts_for_citations([cite])
        assert texts == [FULL_TEXT]

    @pytest.mark.asyncio
    async def test_falls_back_to_span_when_no_chunk_matches(self, mock_storage):
        cite = FakeCitation("doc_x", "span that matches no chunk")
        texts = await full_texts_for_citations([cite])
        assert texts == ["span that matches no chunk"]

    @pytest.mark.asyncio
    async def test_graph_citation_with_empty_doc_id_uses_span(self, mock_storage):
        cite = FakeCitation("", "Entity: Raffles. role: Governor")
        texts = await full_texts_for_citations([cite])
        assert texts == ["Entity: Raffles. role: Governor"]
        mock_storage.blob.assert_not_called()

    @pytest.mark.asyncio
    async def test_gcs_failure_falls_back_to_span(self, mock_storage):
        cite = FakeCitation("doc_missing", "some span text")
        texts = await full_texts_for_citations([cite])
        assert texts == ["some span text"]

    @pytest.mark.asyncio
    async def test_one_download_per_doc(self, mock_storage):
        cites = [
            FakeCitation("doc_x", FULL_TEXT[:300]),
            FakeCitation("doc_x", "Unrelated chunk text."),
        ]
        texts = await full_texts_for_citations(cites)
        assert texts == [FULL_TEXT, "Unrelated chunk text."]
        assert mock_storage.blob.call_count == 1
