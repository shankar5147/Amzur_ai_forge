from __future__ import annotations

from typing import Iterable

from openai import AsyncOpenAI

from app.core.config import settings


class EmbeddingService:
    """Wrapper around LiteLLM's OpenAI-compatible embeddings API.

    Service fails open: if the provider is unavailable, callers can fall back
    to lexical scoring so chat remains functional.
    """

    def __init__(self) -> None:
        self._enabled = settings.rag_enabled and bool(settings.litellm_virtual_key)
        self._model = settings.rag_embedding_model

        self._client: AsyncOpenAI | None = None
        if self._enabled:
            self._client = AsyncOpenAI(
                api_key=settings.litellm_virtual_key,
                base_url=f"{settings.litellm_proxy_url}/v1",
                default_headers={
                    "x-litellm-user": settings.litellm_user_id,
                    "x-litellm-department": settings.litellm_department,
                    "x-litellm-environment": settings.litellm_environment,
                },
            )

    @property
    def enabled(self) -> bool:
        return self._enabled and self._client is not None

    async def generate_embedding(self, text: str) -> list[float] | None:
        if not self.enabled:
            return None

        value = text.strip()
        if not value:
            return None

        try:
            response = await self._client.embeddings.create(
                model=self._model,
                input=value,
            )
            return list(response.data[0].embedding)
        except Exception:
            return None

    async def generate_embeddings(self, texts: Iterable[str]) -> list[list[float] | None]:
        items = [text.strip() for text in texts]
        if not items:
            return []

        if not self.enabled:
            return [None for _ in items]

        try:
            response = await self._client.embeddings.create(
                model=self._model,
                input=items,
            )
            vectors = [list(item.embedding) for item in response.data]
            if len(vectors) != len(items):
                # Defensive: preserve positional mapping.
                return [None for _ in items]
            return vectors
        except Exception:
            return [None for _ in items]
