from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.plugin.module_ai.knowledge.chroma_store import ChromaKnowledgeStore, get_cached_chroma_store, get_embedding_collection_name
from app.plugin.module_ai.knowledge.embedding import EmbeddingClient, get_cached_embedding_client

MAX_DOCUMENT_CHARS = 6_000


def _clip(value: Any, limit: int) -> str:
    """Limit untrusted text before it enters retrieval metadata."""
    text = str(value or "")
    return text if len(text) <= limit else f"{text[:limit]}\n[内容已截断]"


@dataclass(slots=True)
class KnowledgeRetrievalDocument:
    """A retrieved knowledge fragment."""

    content: str
    metadata: dict[str, Any] = field(default_factory=dict)


class KeywordKnowledgeRetriever:
    """Small dependency-free retriever for ad-hoc file context."""

    def __init__(self, documents: list[KnowledgeRetrievalDocument] | None = None, top_k: int = 4) -> None:
        self.documents = documents or self._default_documents()
        self.top_k = top_k

    async def retrieve(
        self,
        *,
        query: str,
        user_id: str,
        scope_id: str,
        session_id: str | None,
        knowledge_base_ids: list[int] | None = None,
        files: list[dict[str, Any]] | None = None,
    ) -> list[KnowledgeRetrievalDocument]:
        candidates = [*self._documents_from_files(files), *self.documents]
        query_tokens = self._tokenize(query)
        scored = [(self._score(doc, query, query_tokens), doc) for doc in candidates]
        scored = [(score, doc) for score, doc in scored if score > 0]
        scored.sort(key=lambda item: item[0], reverse=True)
        return [doc for _, doc in scored[: self.top_k]]

    @staticmethod
    def _default_documents() -> list[KnowledgeRetrievalDocument]:
        return [
            KnowledgeRetrievalDocument(
                content="用户管理页面用于维护系统用户，路由路径是 /system/user。",
                metadata={"source": "system-menu", "name": "用户管理"},
            ),
            KnowledgeRetrievalDocument(
                content="角色管理页面用于配置角色和权限，路由路径是 /system/role。",
                metadata={"source": "system-menu", "name": "角色管理"},
            ),
            KnowledgeRetrievalDocument(
                content="菜单管理页面用于维护菜单、按钮和接口权限，路由路径是 /system/menu。",
                metadata={"source": "system-menu", "name": "菜单管理"},
            ),
            KnowledgeRetrievalDocument(
                content="字典管理页面用于维护系统字典类型和字典数据，路由路径是 /system/dict。",
                metadata={"source": "system-menu", "name": "字典管理"},
            ),
            KnowledgeRetrievalDocument(
                content="系统日志页面用于查看登录日志和操作日志，路由路径是 /system/log。",
                metadata={"source": "system-menu", "name": "系统日志"},
            ),
        ]

    @staticmethod
    def _documents_from_files(files: list[dict[str, Any]] | None) -> list[KnowledgeRetrievalDocument]:
        documents: list[KnowledgeRetrievalDocument] = []
        for index, file in enumerate(files or []):
            content = file.get("content") or file.get("text") or file.get("summary")
            if not isinstance(content, str) or not content.strip():
                continue
            name = file.get("name") or file.get("filename") or f"file-{index + 1}"
            documents.append(
                KnowledgeRetrievalDocument(
                    content=_clip(content.strip(), MAX_DOCUMENT_CHARS),
                    metadata={"source": "uploaded-file", "name": str(name)},
                )
            )
        return documents

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        normalized = text.lower()
        tokens = {part for part in normalized.replace("/", " ").replace("_", " ").split() if part}
        for keyword in ("用户", "角色", "菜单", "字典", "日志", "权限", "路由", "路径"):
            if keyword in text:
                tokens.add(keyword)
        return tokens

    @staticmethod
    def _score(doc: KnowledgeRetrievalDocument, query: str, query_tokens: set[str]) -> int:
        searchable = f"{doc.content.lower()} {' '.join(str(value) for value in doc.metadata.values()).lower()}"
        score = sum(2 for token in query_tokens if token in searchable)
        return score + 4 if query and query.lower() in searchable else score


class ChromaKnowledgeRetriever:
    """Retriever backed by ChromaDB for persisted knowledge-base chunks."""

    def __init__(
        self,
        *,
        store: ChromaKnowledgeStore | None = None,
        embedding_client: EmbeddingClient | None = None,
        top_k: int = 5,
    ) -> None:
        self.store = store
        self.embedding_client = embedding_client
        self.top_k = top_k
        self.file_retriever = KeywordKnowledgeRetriever(documents=[], top_k=top_k)

    async def retrieve(
        self,
        *,
        query: str,
        user_id: str,
        scope_id: str,
        session_id: str | None,
        knowledge_base_ids: list[int] | None = None,
        files: list[dict[str, Any]] | None = None,
    ) -> list[KnowledgeRetrievalDocument]:
        if not knowledge_base_ids:
            return await self.file_retriever.retrieve(
                query=query,
                user_id=user_id,
                scope_id=scope_id,
                session_id=session_id,
                files=files,
            )

        embeddings = await self._get_embedding_client().embed_texts([query])
        raw = await self._get_store().query(
            query_embedding=embeddings[0],
            knowledge_base_ids=knowledge_base_ids,
            top_k=self.top_k,
        )
        return self._documents_from_chroma(raw)

    def _get_store(self) -> ChromaKnowledgeStore:
        if self.store is None:
            self.store = get_cached_chroma_store(collection_name=get_embedding_collection_name())
        return self.store

    def _get_embedding_client(self) -> EmbeddingClient:
        if self.embedding_client is None:
            self.embedding_client = get_cached_embedding_client()
        return self.embedding_client

    @staticmethod
    def _documents_from_chroma(raw: dict[str, Any]) -> list[KnowledgeRetrievalDocument]:
        documents = (raw.get("documents") or [[]])[0] or []
        metadatas = (raw.get("metadatas") or [[]])[0] or []
        distances = (raw.get("distances") or [[]])[0] or []
        result: list[KnowledgeRetrievalDocument] = []
        for index, content in enumerate(documents):
            metadata = dict(metadatas[index] if index < len(metadatas) and metadatas[index] else {})
            if index < len(distances):
                metadata["distance"] = distances[index]
            result.append(KnowledgeRetrievalDocument(content=str(content), metadata=metadata))
        return result
