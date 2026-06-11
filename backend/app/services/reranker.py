"""Cross-encoder reranker for the Colonial Archives Graph-RAG backend.

Scores (query, chunk_text) pairs with a pretrained PyTorch cross-encoder
(sentence-transformers, CPU inference) so that:

  1. the top-N chunks fed to the LLM are ordered by true query relevance,
     not just bi-encoder vector distance, and
  2. the max score acts as a corpus-tuned relevance gate — when even the
     best candidate scores below the threshold the query is out-of-corpus
     and must not be answered with archive grounding (FINDINGS.md Gap 1).

The model is lazy-loaded on first use so the app imports (and unit tests
run) without torch when RERANKER_ENABLED is false. _predict is the seam
unit tests mock; it returns raw logits, and score() maps them through a
sigmoid to [0, 1].
"""

from __future__ import annotations

import asyncio
import logging
import math

from app.config.settings import settings

logger = logging.getLogger(__name__)


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


class RerankerService:
    def __init__(self) -> None:
        self._model = None

    def _get_model(self):
        if self._model is None:
            import torch
            from sentence_transformers import CrossEncoder

            logger.info("Loading cross-encoder model: %s", settings.RERANK_MODEL)
            # Identity activation -> predict returns raw logits; score()
            # owns the sigmoid so normalization happens exactly once.
            # (kwarg renamed across sentence-transformers majors)
            try:
                self._model = CrossEncoder(
                    settings.RERANK_MODEL,
                    device="cpu",
                    activation_fn=torch.nn.Identity(),
                )
            except TypeError:
                self._model = CrossEncoder(
                    settings.RERANK_MODEL,
                    device="cpu",
                    default_activation_function=torch.nn.Identity(),
                )
        return self._model

    def _predict(self, pairs: list[tuple[str, str]]) -> list[float]:
        """Raw model logits for each (query, text) pair. Mockable seam."""
        return [float(s) for s in self._get_model().predict(pairs)]

    async def score(self, query: str, texts: list[str]) -> list[float]:
        """Sigmoid-normalized relevance scores in [0, 1], one per text."""
        if not texts:
            return []
        pairs = [(query, t) for t in texts]
        loop = asyncio.get_event_loop()
        raw = await loop.run_in_executor(None, self._predict, pairs)
        return [_sigmoid(r) for r in raw]

    async def rerank(
        self,
        query: str,
        chunks: list[dict],
        top_n: int,
    ) -> tuple[list[dict], float]:
        """Return (top_n chunks sorted by relevance desc, max score).

        Each returned chunk gets a ``rerank_score`` key. Empty input
        returns ([], 0.0) without touching the model.
        """
        if not chunks:
            return [], 0.0
        scores = await self.score(query, [c.get("text", "") for c in chunks])
        for c, s in zip(chunks, scores):
            c["rerank_score"] = s
        ranked = sorted(chunks, key=lambda c: c["rerank_score"], reverse=True)
        return ranked[:top_n], max(scores)


# Module-level singleton (matches the other services)
reranker_service = RerankerService()
