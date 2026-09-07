from types import SimpleNamespace

import pytest


async def test_create_embedding_client_defaults_to_local_fastembed(monkeypatch) -> None:
    from app.plugin.module_ai.knowledge import embedding

    created: dict[str, object] = {}

    class FakeTextEmbedding:
        def __init__(self, model_name: str, cache_dir: str) -> None:
            created["model_name"] = model_name
            created["cache_dir"] = cache_dir

        def embed(self, texts: list[str]):
            created["texts"] = texts
            return [[0.1, 0.2]]

    monkeypatch.setattr(embedding.settings, "EMBEDDING_PROVIDER", "local")
    monkeypatch.setattr(embedding.settings, "LOCAL_EMBEDDING_MODEL", "BAAI/bge-small-zh-v1.5")
    monkeypatch.setattr(embedding.settings, "LOCAL_EMBEDDING_CACHE_DIR", "./data/fastembed")
    monkeypatch.setattr(embedding, "TextEmbedding", FakeTextEmbedding)

    client = embedding.create_embedding_client()
    assert await client.embed_texts(["hello"]) == [[0.1, 0.2]]
    assert created == {
        "model_name": "BAAI/bge-small-zh-v1.5",
        "cache_dir": "./data/fastembed",
        "texts": ["hello"],
    }


async def test_create_embedding_client_uses_synced_vector_model(monkeypatch) -> None:
    from app.plugin.module_ai.chat import model_config_service
    from app.plugin.module_ai.knowledge import embedding

    created: dict[str, object] = {}

    class FakeTextEmbedding:
        def __init__(self, model_name: str, cache_dir: str) -> None:
            created["model_name"] = model_name

        def embed(self, texts: list[str]):
            return [[0.1, 0.2] for _ in texts]

    monkeypatch.setattr(
        model_config_service,
        "_active_embedding_config",
        model_config_service.EmbeddingRuntimeConfig("local", "synced-embedding", "", ""),
    )
    monkeypatch.setattr(embedding, "TextEmbedding", FakeTextEmbedding)

    client = embedding.create_embedding_client()
    await client.embed_texts(["hello"])

    assert created["model_name"] == "synced-embedding"


def test_create_embedding_client_can_select_openai_provider(monkeypatch) -> None:
    from app.plugin.module_ai.knowledge import embedding

    monkeypatch.setattr(embedding.settings, "EMBEDDING_PROVIDER", "openai")
    monkeypatch.setattr(embedding.settings, "OPENAI_API_KEY", "test_key")
    monkeypatch.setattr(embedding.settings, "OPENAI_BASE_URL", "https://example.test/v1")
    monkeypatch.setattr(embedding.settings, "OPENAI_EMBEDDING_MODEL", "embed-test")
    monkeypatch.setattr(embedding, "AsyncOpenAI", lambda **kwargs: SimpleNamespace(embeddings=object()))

    assert isinstance(embedding.create_embedding_client(), embedding.OpenAICompatibleEmbeddingClient)


async def test_embedding_client_reports_empty_provider_data(monkeypatch) -> None:
    from app.plugin.module_ai.knowledge import embedding

    class FakeEmbeddings:
        async def create(self, **kwargs):
            return SimpleNamespace(data=[])

    class FakeClient:
        embeddings = FakeEmbeddings()

    monkeypatch.setattr(embedding.settings, "OPENAI_API_KEY", "test_key")
    monkeypatch.setattr(embedding.settings, "OPENAI_BASE_URL", "https://example.test/v1")
    monkeypatch.setattr(embedding.settings, "OPENAI_EMBEDDING_MODEL", "embed-test")
    monkeypatch.setattr(embedding, "AsyncOpenAI", lambda **kwargs: FakeClient())

    with pytest.raises(ValueError, match="Embedding service returned no vectors"):
        await embedding.OpenAICompatibleEmbeddingClient().embed_texts(["hello"])


async def test_embedding_client_sends_one_input_per_request(monkeypatch) -> None:
    from app.plugin.module_ai.knowledge import embedding

    calls: list[dict[str, object]] = []

    class FakeEmbeddings:
        async def create(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(data=[SimpleNamespace(embedding=[float(len(calls)), 0.2])])

    class FakeClient:
        embeddings = FakeEmbeddings()

    monkeypatch.setattr(embedding.settings, "OPENAI_API_KEY", "test_key")
    monkeypatch.setattr(embedding.settings, "OPENAI_BASE_URL", "https://example.test/v1")
    monkeypatch.setattr(embedding.settings, "OPENAI_EMBEDDING_MODEL", "embed-test")
    monkeypatch.setattr(embedding, "AsyncOpenAI", lambda **kwargs: FakeClient())

    assert await embedding.OpenAICompatibleEmbeddingClient().embed_texts(["hello", "world"]) == [[1.0, 0.2], [2.0, 0.2]]
    assert calls == [
        {"model": "embed-test", "input": ["hello"]},
        {"model": "embed-test", "input": ["world"]},
    ]


async def test_embedding_client_reports_vector_count_mismatch(monkeypatch) -> None:
    from app.plugin.module_ai.knowledge import embedding

    class FakeEmbeddings:
        async def create(self, **kwargs):
            return SimpleNamespace(
                data=[
                    SimpleNamespace(embedding=[0.1, 0.2]),
                    SimpleNamespace(embedding=[0.3, 0.4]),
                ]
            )

    class FakeClient:
        embeddings = FakeEmbeddings()

    monkeypatch.setattr(embedding.settings, "OPENAI_API_KEY", "test_key")
    monkeypatch.setattr(embedding.settings, "OPENAI_BASE_URL", "https://example.test/v1")
    monkeypatch.setattr(embedding.settings, "OPENAI_EMBEDDING_MODEL", "embed-test")
    monkeypatch.setattr(embedding, "AsyncOpenAI", lambda **kwargs: FakeClient())

    with pytest.raises(ValueError, match="Embedding service returned 2 vectors for 1 texts"):
        await embedding.OpenAICompatibleEmbeddingClient().embed_texts(["hello", "world"])
