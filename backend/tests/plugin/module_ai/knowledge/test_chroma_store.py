import sys
from types import SimpleNamespace

from app.plugin.module_ai.knowledge.chroma_store import ChromaKnowledgeStore, get_embedding_collection_name


def test_build_metadata_filter_for_one_knowledge_base():
    assert ChromaKnowledgeStore.build_where_filter([3]) == {"knowledge_base_id": 3}


def test_build_metadata_filter_for_multiple_knowledge_bases():
    assert ChromaKnowledgeStore.build_where_filter([1, 2]) == {
        "knowledge_base_id": {"$in": [1, 2]}
    }


def test_build_metadata_filter_without_knowledge_base():
    assert ChromaKnowledgeStore.build_where_filter([]) is None


def test_embedding_collection_name_isolated_by_model(monkeypatch):
    monkeypatch.setattr(
        "app.plugin.module_ai.knowledge.chroma_store.settings.CHROMA_COLLECTION_NAME",
        "knowledge_base",
    )
    monkeypatch.setattr(
        "app.plugin.module_ai.knowledge.chroma_store.settings.LOCAL_EMBEDDING_MODEL",
        "legacy-model",
    )

    legacy = SimpleNamespace(provider="local", model="legacy-model", base_url="")
    remote = SimpleNamespace(provider="openai", model="qwen3-embedding", base_url="https://modelservice.jdcloud.com/v1")

    assert get_embedding_collection_name(legacy) == "knowledge_base"
    assert get_embedding_collection_name(remote).startswith("knowledge_base-")
    assert get_embedding_collection_name(remote) != "knowledge_base"


def test_uses_persistent_client_with_configured_directory(monkeypatch, tmp_path):
    calls = {}

    class FakeClient:
        def __init__(self, *, path):
            calls["path"] = path

        def get_or_create_collection(self, *, name):
            calls["collection_name"] = name
            return object()

    fake_chromadb = SimpleNamespace(PersistentClient=FakeClient)
    monkeypatch.setitem(sys.modules, "chromadb", fake_chromadb)
    monkeypatch.setattr(
        "app.plugin.module_ai.knowledge.chroma_store.settings.CHROMA_PERSIST_DIR",
        str(tmp_path),
    )
    monkeypatch.setattr(
        "app.plugin.module_ai.knowledge.chroma_store.settings.CHROMA_COLLECTION_NAME",
        "local_knowledge",
    )

    ChromaKnowledgeStore()

    assert calls == {"path": str(tmp_path), "collection_name": "local_knowledge"}
