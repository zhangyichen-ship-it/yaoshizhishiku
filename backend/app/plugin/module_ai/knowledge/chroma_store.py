from __future__ import annotations

import hashlib
import re
from functools import lru_cache
from typing import Any

import anyio

from app.plugin.module_ai.config import settings


def get_embedding_collection_name(embedding_config: object | None = None) -> str:
    """Return a stable Chroma collection name for the active embedding model."""
    if embedding_config is None:
        from app.plugin.module_ai.chat.model_config_service import get_active_embedding_model_config

        embedding_config = get_active_embedding_model_config()

    base_name = (settings.CHROMA_COLLECTION_NAME or "knowledge_base").strip()
    provider = str(getattr(embedding_config, "provider", "")).strip().lower()
    model = str(getattr(embedding_config, "model", "")).strip()
    base_url = str(getattr(embedding_config, "base_url", "")).strip().rstrip("/")
    if provider == "local" and model == settings.LOCAL_EMBEDDING_MODEL.strip():
        return base_name

    safe_base_name = re.sub(r"[^a-zA-Z0-9_-]+", "-", base_name).strip("-_") or "knowledge_base"
    fingerprint = hashlib.sha256(f"{provider}\0{base_url}\0{model}".encode()).hexdigest()[:12]
    return f"{safe_base_name[:50]}-{fingerprint}"


class ChromaKnowledgeStore:
    """Thin adapter around local ChromaDB collection operations."""

    def __init__(
        self,
        *,
        persist_dir: str | None = None,
        collection_name: str | None = None,
    ) -> None:
        try:
            import chromadb
        except ImportError as exc:
            raise RuntimeError("chromadb is required for knowledge-base vector search") from exc

        self.persist_dir = persist_dir or settings.CHROMA_PERSIST_DIR
        self.collection_name = collection_name or settings.CHROMA_COLLECTION_NAME
        self.client = chromadb.PersistentClient(path=self.persist_dir)
        self.collection = self.client.get_or_create_collection(name=self.collection_name)

    @staticmethod
    def build_where_filter(knowledge_base_ids: list[int] | None) -> dict[str, Any] | None:
        if not knowledge_base_ids:
            return None
        if len(knowledge_base_ids) == 1:
            return {"knowledge_base_id": knowledge_base_ids[0]}
        return {"knowledge_base_id": {"$in": knowledge_base_ids}}

    async def upsert_chunks(
        self,
        *,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict[str, Any]],
    ) -> None:
        await anyio.to_thread.run_sync(lambda: self.collection.upsert(ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas))

    async def query(self, *, query_embedding: list[float], knowledge_base_ids: list[int], top_k: int = 5) -> dict[str, Any]:
        return await anyio.to_thread.run_sync(
            lambda: self.collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                where=self.build_where_filter(knowledge_base_ids),
                include=["documents", "metadatas", "distances"],
            )
        )

    async def get_by_ids(self, ids: list[str]) -> dict[str, Any]:
        if not ids:
            return {"ids": [], "documents": [], "metadatas": []}
        return await anyio.to_thread.run_sync(lambda: self.collection.get(ids=ids, include=["documents", "metadatas"]))

    async def delete_ids(self, ids: list[str]) -> None:
        if ids:
            await anyio.to_thread.run_sync(lambda: self.collection.delete(ids=ids))

    async def delete_document(self, document_id: int) -> None:
        await anyio.to_thread.run_sync(lambda: self.collection.delete(where={"document_id": document_id}))


@lru_cache(maxsize=4)
def get_cached_chroma_store(
    persist_dir: str | None = None,
    collection_name: str | None = None,
) -> ChromaKnowledgeStore:
    """Reuse one Chroma client per local collection configuration."""
    return ChromaKnowledgeStore(persist_dir=persist_dir, collection_name=collection_name)
