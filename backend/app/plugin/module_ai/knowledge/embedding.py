from functools import lru_cache
from typing import Protocol

import anyio
from fastembed import TextEmbedding
from openai import AsyncOpenAI

from app.plugin.module_ai.config import settings


class EmbeddingClient(Protocol):
    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Return one embedding vector per input text."""


class LocalFastEmbedEmbeddingClient:
    """Local embedding client backed by fastembed."""

    def __init__(self, model_name: str | None = None, cache_dir: str | None = None) -> None:
        self.model_name = model_name or settings.LOCAL_EMBEDDING_MODEL
        if not self.model_name.strip():
            raise ValueError("LOCAL_EMBEDDING_MODEL is not configured")
        self.model = TextEmbedding(model_name=self.model_name, cache_dir=cache_dir or settings.LOCAL_EMBEDDING_CACHE_DIR)

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        return await anyio.to_thread.run_sync(self._embed_texts_sync, texts)

    def _embed_texts_sync(self, texts: list[str]) -> list[list[float]]:
        vectors = list(self.model.embed(texts))
        embeddings = [vector.tolist() if hasattr(vector, "tolist") else list(vector) for vector in vectors]
        _validate_embeddings(embeddings, len(texts))
        return embeddings


class OpenAICompatibleEmbeddingClient:
    """Embedding client for OpenAI-compatible providers."""

    # 单批次最多提交的文本条数；超过 provider 单请求条数/token 上限会导致整批失败，
    # 分批后单批失败不影响其它批次已经成功的向量。
    BATCH_SIZE = 64

    def __init__(
        self,
        *,
        model_name: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
    ) -> None:
        self.model_name = model_name or settings.OPENAI_EMBEDDING_MODEL
        self.base_url = base_url if base_url is not None else settings.OPENAI_BASE_URL
        self.api_key = api_key if api_key is not None else settings.OPENAI_API_KEY
        self._validate_config(self.model_name, self.base_url, self.api_key)
        self.client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        embeddings: list[list[float]] = []
        for start in range(0, len(texts), self.BATCH_SIZE):
            batch = texts[start : start + self.BATCH_SIZE]
            embeddings.extend(await self._embed_batch(batch))
        _validate_embeddings(
            embeddings,
            len(texts),
            empty_message=("Embedding service returned no vectors. Check OPENAI_EMBEDDING_MODEL and whether OPENAI_BASE_URL supports the /embeddings endpoint."),
        )
        return embeddings

    async def _embed_batch(self, batch: list[str]) -> list[list[float]]:
        response = await self.client.embeddings.create(model=self.model_name, input=batch)
        embeddings = [item.embedding for item in response.data or [] if getattr(item, "embedding", None)]
        _validate_embeddings(
            embeddings,
            len(batch),
            empty_message=("Embedding service returned no vectors. Check OPENAI_EMBEDDING_MODEL and whether OPENAI_BASE_URL supports the /embeddings endpoint."),
        )
        return embeddings

    @staticmethod
    def _validate_config(model_name: str, base_url: str, api_key: str) -> None:
        if not api_key.strip() or api_key.strip() == "your_api_key":
            raise ValueError("OPENAI_API_KEY is not configured")
        if not base_url.strip():
            raise ValueError("OPENAI_BASE_URL is not configured")
        if not model_name.strip() or model_name.strip() == "your_embedding_model":
            raise ValueError("OPENAI_EMBEDDING_MODEL is not configured")


def _effective_embedding_values(provider: str | None = None) -> tuple[str, str, str, str]:
    from app.plugin.module_ai.chat.model_config_service import get_active_embedding_model_config

    active = get_active_embedding_model_config()
    selected = (provider or active.provider or "local").strip().lower()
    if provider is None or selected == active.provider:
        return selected, active.model, active.base_url, active.api_key
    if selected == "local":
        return selected, settings.LOCAL_EMBEDDING_MODEL, "", ""
    if selected in {"openai", "remote"}:
        return selected, settings.OPENAI_EMBEDDING_MODEL, settings.OPENAI_BASE_URL, settings.OPENAI_API_KEY
    return selected, "", "", ""


def create_embedding_client(provider: str | None = None) -> EmbeddingClient:
    selected, model, base_url, api_key = _effective_embedding_values(provider)
    if selected == "local":
        return LocalFastEmbedEmbeddingClient(model_name=model)
    if selected in {"openai", "remote"}:
        return OpenAICompatibleEmbeddingClient(model_name=model, base_url=base_url, api_key=api_key)
    raise ValueError("EMBEDDING_PROVIDER must be 'local' or 'openai'")


@lru_cache(maxsize=4)
def _cached_embedding_client(config: tuple[str, ...]) -> EmbeddingClient:
    """Create one embedding client per effective provider configuration."""
    selected, model, cache_dir, api_key, base_url = config
    if selected == "local":
        return LocalFastEmbedEmbeddingClient(model_name=model, cache_dir=cache_dir)
    return OpenAICompatibleEmbeddingClient(model_name=model, base_url=base_url, api_key=api_key)


def get_cached_embedding_client(provider: str | None = None) -> EmbeddingClient:
    """Reuse the process-local embedding client for normal request paths."""
    selected, model, base_url, api_key = _effective_embedding_values(provider)
    config = (
        selected,
        model,
        settings.LOCAL_EMBEDDING_CACHE_DIR,
        api_key,
        base_url,
    )
    return _cached_embedding_client(config)


def _validate_embeddings(
    embeddings: list[list[float]],
    expected_count: int,
    *,
    empty_message: str = "Embedding service returned no vectors",
) -> None:
    if not embeddings:
        raise ValueError(empty_message)
    if len(embeddings) != expected_count:
        raise ValueError(f"Embedding service returned {len(embeddings)} vectors for {expected_count} texts")
