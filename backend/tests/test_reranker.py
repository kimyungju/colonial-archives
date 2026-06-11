"""Unit tests for the cross-encoder reranker service (model mocked).

The real model (sentence-transformers CrossEncoder, PyTorch CPU) is only
exercised by the manual smoke script — these tests mock the _predict seam,
which returns raw logits.
"""

from unittest.mock import patch

import pytest

from app.services.reranker import RerankerService


@pytest.fixture
def service():
    return RerankerService()


def chunk(cid, text):
    return {"id": cid, "text": text, "cite_type": "archive"}


class TestScore:
    @pytest.mark.asyncio
    async def test_applies_sigmoid_to_raw_logits(self, service):
        with patch.object(service, "_predict", return_value=[0.0, 10.0, -10.0]):
            scores = await service.score("q", ["a", "b", "c"])
        assert scores[0] == pytest.approx(0.5)
        assert scores[1] == pytest.approx(1.0, abs=1e-3)
        assert scores[2] == pytest.approx(0.0, abs=1e-3)

    @pytest.mark.asyncio
    async def test_pairs_query_with_each_text(self, service):
        with patch.object(service, "_predict", return_value=[1.0, 2.0]) as mock_pred:
            await service.score("my query", ["text one", "text two"])
        mock_pred.assert_called_once_with(
            [("my query", "text one"), ("my query", "text two")]
        )

    @pytest.mark.asyncio
    async def test_empty_texts_returns_empty_without_model(self, service):
        with patch.object(service, "_predict") as mock_pred:
            scores = await service.score("q", [])
        assert scores == []
        mock_pred.assert_not_called()


class TestRerank:
    @pytest.mark.asyncio
    async def test_orders_chunks_by_score_descending(self, service):
        chunks = [chunk("c1", "weak"), chunk("c2", "strong"), chunk("c3", "mid")]
        with patch.object(service, "_predict", return_value=[-2.0, 3.0, 0.5]):
            ranked, _max = await service.rerank("q", chunks, top_n=3)
        assert [c["id"] for c in ranked] == ["c2", "c3", "c1"]

    @pytest.mark.asyncio
    async def test_truncates_to_top_n(self, service):
        chunks = [chunk(f"c{i}", f"t{i}") for i in range(5)]
        with patch.object(service, "_predict", return_value=[5.0, 4.0, 3.0, 2.0, 1.0]):
            ranked, _max = await service.rerank("q", chunks, top_n=2)
        assert [c["id"] for c in ranked] == ["c0", "c1"]

    @pytest.mark.asyncio
    async def test_returns_max_score(self, service):
        chunks = [chunk("c1", "a"), chunk("c2", "b")]
        with patch.object(service, "_predict", return_value=[0.0, 10.0]):
            _ranked, max_score = await service.rerank("q", chunks, top_n=1)
        assert max_score == pytest.approx(1.0, abs=1e-3)

    @pytest.mark.asyncio
    async def test_attaches_rerank_score_to_chunks(self, service):
        chunks = [chunk("c1", "a")]
        with patch.object(service, "_predict", return_value=[0.0]):
            ranked, _max = await service.rerank("q", chunks, top_n=1)
        assert ranked[0]["rerank_score"] == pytest.approx(0.5)

    @pytest.mark.asyncio
    async def test_empty_chunks_returns_empty_and_zero(self, service):
        with patch.object(service, "_predict") as mock_pred:
            ranked, max_score = await service.rerank("q", [], top_n=5)
        assert ranked == []
        assert max_score == 0.0
        mock_pred.assert_not_called()
