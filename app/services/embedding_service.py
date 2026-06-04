"""Embedding service — OpenAI compatible embedding for RAG."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_EMBEDDING_CACHE: dict[str, list[float]] = {}
_MAX_CACHE_SIZE = 10_000


class OpenAIEmbeddingService:
    """Async embedding service using OpenAI-compatible API.

    Caches embeddings by text content (in-memory LRU via simple dict eviction).
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "text-embedding-3-small",
        dimension: int = 1536,
        api_base: str = "https://api.openai.com/v1",
        max_retries: int = 3,
    ):
        self.api_key = api_key or settings.llm_api_key or ""
        self.model = model
        self.dimension = dimension
        self.api_base = api_base
        self.max_retries = max_retries

    async def embed_text(self, text: str) -> list[float]:
        """Embed a single text string."""
        # Check cache
        cache_key = f"{self.model}:{text[:500]}"
        cached = _EMBEDDING_CACHE.get(cache_key)
        if cached is not None:
            return cached

        result = await self.embed_texts([text])
        if result:
            vec = result[0]
            # Evict if cache too large
            if len(_EMBEDDING_CACHE) >= _MAX_CACHE_SIZE:
                _EMBEDDING_CACHE.clear()
            _EMBEDDING_CACHE[cache_key] = vec
            return vec
        return [0.0] * self.dimension

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of text strings in one API call."""
        if not texts:
            return []

        for attempt in range(self.max_retries):
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    resp = await client.post(
                        f"{self.api_base}/embeddings",
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json",
                        },
                        json={"input": texts, "model": self.model},
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    # Sort by index to preserve input order
                    sorted_data = sorted(data["data"], key=lambda x: x["index"])
                    return [item["embedding"] for item in sorted_data]

            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 429 and attempt < self.max_retries - 1:
                    wait = 2 ** (attempt + 1)
                    logger.warning("Embedding rate limited, retrying in %ds", wait)
                    await asyncio.sleep(wait)
                    continue
                logger.error("Embedding API error: %s", exc)
                return []
            except Exception as exc:
                logger.error("Embedding request failed: %s", exc)
                return []

        logger.warning("Embedding failed after %d retries", self.max_retries)
        return []

    async def batch_ingest_chunks(
        self,
        chunks: list[dict[str, Any]],
        collection,
        batch_size: int = 20,
    ) -> int:
        """Embed a list of chunk dicts and add them to a ChromaDB collection.

        Each chunk should have: id, text, metadata (dict).
        Returns the number of successfully embedded chunks.
        """
        embedded_count = 0
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i : i + batch_size]
            texts = [c["text"] for c in batch]
            embeddings = await self.embed_texts(texts)

            for j, chunk in enumerate(batch):
                if j < len(embeddings) and embeddings[j]:
                    try:
                        collection.add(
                            ids=[chunk["id"]],
                            embeddings=[embeddings[j]],
                            documents=[chunk["text"]],
                            metadatas=[chunk.get("metadata", {})],
                        )
                        embedded_count += 1
                    except Exception as exc:
                        logger.error(
                            "ChromaDB insert failed for %s: %s",
                            chunk["id"],
                            exc,
                        )

        return embedded_count


# Module-level singleton
_embedding_service: OpenAIEmbeddingService | None = None


def get_embedding_service() -> OpenAIEmbeddingService:
    """Get or create the global embedding service singleton."""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = OpenAIEmbeddingService(
            api_key=settings.llm_api_key or None,
            model=settings.embedding_model,
            dimension=settings.embedding_dimension,
        )
    return _embedding_service
