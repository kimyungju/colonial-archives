"""Vertex AI text-embedding service for the Colonial Archives Graph-RAG backend."""

import asyncio
import logging

import vertexai
from vertexai.language_models import TextEmbeddingInput, TextEmbeddingModel

from app.config.settings import settings
from app.models.schemas import Chunk

logger = logging.getLogger(__name__)

EMBEDDING_BATCH_SIZE = 250  # Vertex AI items-per-request limit
# Vertex AI text-embedding-004 has a 20,000 token limit per request.
# With ~450-token chunks (some up to ~600), 25 chunks ≈ 15,000 tokens — safe margin.
EMBEDDING_TOKEN_SAFE_BATCH = 25


class EmbeddingsService:
    """Wraps the Vertex AI TextEmbeddingModel for chunk and query embedding."""

    def __init__(self) -> None:
        self._model = None

    @property
    def model(self):
        if self._model is None:
            # Other services (LlmService, vector_search) call vertexai.init
            # with different regions. TextEmbeddingModel.from_pretrained pins
            # the constructed model to whatever region is global at call time,
            # so we must re-pin to GCP_REGION right before construction.
            vertexai.init(
                project=settings.GCP_PROJECT_ID,
                location=settings.GCP_REGION,
            )
            self._model = TextEmbeddingModel.from_pretrained(settings.VERTEX_EMBED_MODEL)
            logger.info(
                "EmbeddingsService initialised with model=%s in %s",
                settings.VERTEX_EMBED_MODEL,
                settings.GCP_REGION,
            )
        return self._model

    async def embed_chunks(self, chunks: list[Chunk]) -> list[list[float]]:
        """Embed a list of Chunk objects for document retrieval.

        Extracts the text from each chunk and delegates to embed_texts with
        task_type ``RETRIEVAL_DOCUMENT``.
        """
        texts = [chunk.text for chunk in chunks]
        logger.info("Embedding %d chunks", len(texts))
        return await self.embed_texts(texts, task_type="RETRIEVAL_DOCUMENT")

    async def embed_query(self, query: str) -> list[float]:
        """Embed a single query string for retrieval.

        Returns a flat list of floats (the embedding vector).
        """
        logger.info("Embedding query (%d chars)", len(query))
        results = await self.embed_texts([query], task_type="RETRIEVAL_QUERY")
        return results[0]

    async def embed_texts(
        self,
        texts: list[str],
        task_type: str = "RETRIEVAL_DOCUMENT",
    ) -> list[list[float]]:
        """Batch-embed a list of raw text strings.

        Texts are processed in batches of ``EMBEDDING_BATCH_SIZE`` to stay
        within the Vertex AI per-request limit.  The blocking
        ``model.get_embeddings`` call is offloaded to a thread via
        ``run_in_executor``.
        """
        all_vectors: list[list[float]] = []
        loop = asyncio.get_event_loop()

        batch_size = min(EMBEDDING_BATCH_SIZE, EMBEDDING_TOKEN_SAFE_BATCH)
        for start in range(0, len(texts), batch_size):
            batch = texts[start : start + batch_size]
            inputs = [
                TextEmbeddingInput(text=t, task_type=task_type) for t in batch
            ]

            logger.debug(
                "Requesting embeddings for batch %d-%d / %d",
                start,
                start + len(batch),
                len(texts),
            )

            embeddings = await loop.run_in_executor(
                None, self.model.get_embeddings, inputs
            )
            all_vectors.extend([e.values for e in embeddings])

        logger.info(
            "Produced %d embedding vectors (dim=%d)",
            len(all_vectors),
            len(all_vectors[0]) if all_vectors else 0,
        )
        return all_vectors


embeddings_service = EmbeddingsService()
