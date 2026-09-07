from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select

from app.core.base_schema import AuthSchema
from app.core.database import async_db_session
from app.core.logger import logger
from app.plugin.module_ai.config import settings, validate_model_base_url
from app.plugin.module_ai.secret import decrypt_secret, encrypt_secret

from .model import AiEmbeddingConfigModel, AiModelConfigModel
from .schema import (
    AiEmbeddingConfigPushSchema,
    AiEmbeddingSyncOutSchema,
    AiModelConfigOutSchema,
    AiModelConfigUpdateSchema,
)


@dataclass(frozen=True, slots=True)
class ChatModelRuntimeConfig:
    protocol: str
    base_url: str
    model: str
    api_key: str


@dataclass(frozen=True, slots=True)
class EmbeddingRuntimeConfig:
    """Effective vector-model configuration used by indexing and retrieval."""

    provider: str
    model: str
    base_url: str
    api_key: str


_active_config: ChatModelRuntimeConfig | None = None
_active_embedding_config: EmbeddingRuntimeConfig | None = None


def _is_configured_api_key(value: str) -> bool:
    normalized = value.strip().lower()
    return bool(normalized and normalized not in {"your_api_key", "sk-yourapikey", "your-api-key"})


def _encrypt_api_key(api_key: str) -> str:
    return encrypt_secret(api_key)


def _decrypt_api_key(value: str | None) -> str | None:
    return decrypt_secret(value)


def _environment_config() -> ChatModelRuntimeConfig:
    return ChatModelRuntimeConfig(
        protocol="openai",
        # Environment files are deployment-owned configuration. User-edited
        # database values still go through the DNS-aware validator below.
        base_url=validate_model_base_url(settings.OPENAI_BASE_URL, resolve_dns=False) if settings.OPENAI_BASE_URL.strip() else "",
        model=settings.OPENAI_MODEL.strip(),
        api_key=settings.OPENAI_API_KEY.strip(),
    )


def _environment_embedding_config() -> EmbeddingRuntimeConfig:
    provider = settings.EMBEDDING_PROVIDER.strip().lower() or "local"
    if provider == "remote":
        provider = "openai"
    if provider not in {"local", "openai"}:
        logger.warning("AI embedding provider is invalid; falling back to local")
        provider = "local"
    if provider == "local":
        return EmbeddingRuntimeConfig(
            provider=provider,
            model=settings.LOCAL_EMBEDDING_MODEL.strip(),
            base_url="",
            api_key="",
        )
    base_url = validate_model_base_url(settings.OPENAI_BASE_URL, resolve_dns=False) if settings.OPENAI_BASE_URL.strip() else ""
    return EmbeddingRuntimeConfig(
        provider=provider,
        model=settings.OPENAI_EMBEDDING_MODEL.strip(),
        base_url=base_url,
        api_key=settings.OPENAI_API_KEY.strip(),
    )


def get_active_chat_model_config() -> ChatModelRuntimeConfig:
    return _active_config or _environment_config()


def get_active_embedding_model_config() -> EmbeddingRuntimeConfig:
    return _active_embedding_config or _environment_embedding_config()


def _apply_record(record: AiModelConfigModel | None) -> ChatModelRuntimeConfig:
    global _active_config
    if record is None:
        _active_config = _environment_config()
        return _active_config

    _active_config = ChatModelRuntimeConfig(
        protocol=record.protocol if record.protocol in {"openai", "anthropic"} else "openai",
        base_url=validate_model_base_url(record.openai_base_url),
        model=record.openai_model.strip(),
        api_key=_decrypt_api_key(record.encrypted_api_key) or _environment_config().api_key,
    )
    return _active_config


def _apply_embedding_record(record: AiEmbeddingConfigModel | None) -> EmbeddingRuntimeConfig:
    global _active_embedding_config
    environment = _environment_embedding_config()
    if record is None:
        _active_embedding_config = environment
        return _active_embedding_config

    try:
        provider = record.provider.strip().lower()
        model = record.model.strip()
        base_url = validate_model_base_url(record.base_url) if provider == "openai" else ""
    except (AttributeError, TypeError, ValueError):
        logger.warning("AI embedding configuration is invalid; falling back to environment configuration")
        _active_embedding_config = environment
        return _active_embedding_config

    if provider not in {"local", "openai"} or not model or (provider == "openai" and not base_url):
        logger.warning("AI embedding configuration is incomplete; falling back to environment configuration")
        _active_embedding_config = environment
        return _active_embedding_config

    _active_embedding_config = EmbeddingRuntimeConfig(
        provider=provider,
        model=model,
        base_url=base_url,
        api_key=environment.api_key if provider == "openai" else "",
    )
    return _active_embedding_config


async def _find_record(auth: AuthSchema) -> AiModelConfigModel | None:
    db = getattr(auth, "db", None)
    if db is None or not hasattr(db, "execute"):
        return None
    result = await db.execute(select(AiModelConfigModel).where(AiModelConfigModel.is_deleted.is_(False)).order_by(AiModelConfigModel.id.asc()).limit(1))
    return result.scalars().first()


async def _find_embedding_record(auth: AuthSchema) -> AiEmbeddingConfigModel | None:
    db = getattr(auth, "db", None)
    if db is None or not hasattr(db, "execute"):
        return None
    result = await db.execute(
        select(AiEmbeddingConfigModel)
        .where(AiEmbeddingConfigModel.is_deleted.is_(False))
        .order_by(AiEmbeddingConfigModel.id.asc())
        .limit(1)
    )
    record = result.scalars().first()
    return record if isinstance(record, AiEmbeddingConfigModel) else None


async def load_runtime_chat_model_config(auth: AuthSchema) -> ChatModelRuntimeConfig:
    """Load the persisted override for this process/request, if one exists."""
    record = await _find_record(auth)
    return _apply_record(record)


async def load_runtime_embedding_model_config(auth: AuthSchema) -> EmbeddingRuntimeConfig:
    """Load the persisted vector-model override for this process/request."""
    return _apply_embedding_record(await _find_embedding_record(auth))


async def initialize_runtime_chat_model_config() -> ChatModelRuntimeConfig:
    """Load the persisted override during application startup."""
    async with async_db_session() as db:
        async with db.begin():
            auth = AuthSchema(db=db, check_data_scope=False)
            config = await load_runtime_chat_model_config(auth)
            await load_runtime_embedding_model_config(auth)
            return config


def _to_output(
    config: ChatModelRuntimeConfig,
    embedding: EmbeddingRuntimeConfig | None = None,
) -> AiModelConfigOutSchema:
    api_key = config.api_key.strip()
    embedding = embedding or get_active_embedding_model_config()
    return AiModelConfigOutSchema(
        chat_protocol=config.protocol,  # type: ignore[arg-type]
        openai_base_url=config.base_url,
        openai_model=config.model,
        openai_embedding_model=embedding.model if embedding.provider == "openai" else settings.OPENAI_EMBEDDING_MODEL,
        embedding_provider=embedding.provider,  # type: ignore[arg-type]
        embedding_model=embedding.model,
        embedding_base_url=embedding.base_url,
        embedding_api_key_configured=_is_configured_api_key(embedding.api_key),
        local_embedding_model=embedding.model if embedding.provider == "local" else settings.LOCAL_EMBEDDING_MODEL,
        openai_api_key_configured=_is_configured_api_key(api_key),
        chroma_persist_dir=settings.CHROMA_PERSIST_DIR,
        chroma_collection_name=settings.CHROMA_COLLECTION_NAME,
    )


async def get_model_config(auth: AuthSchema) -> AiModelConfigOutSchema:
    config = await load_runtime_chat_model_config(auth)
    embedding = await load_runtime_embedding_model_config(auth)
    return _to_output(config, embedding)


def _embedding_update_requested(data: AiModelConfigUpdateSchema) -> bool:
    return any(
        value is not None
        for value in (
            data.embedding_provider,
            data.embedding_model,
            data.embedding_base_url,
            data.embedding_api_key,
        )
    )


async def _update_embedding_record(
    auth: AuthSchema,
    data: AiModelConfigUpdateSchema,
    record: AiEmbeddingConfigModel | None,
) -> AiEmbeddingConfigModel:
    if not data.embedding_provider or not data.embedding_model:
        raise ValueError("请同时配置向量来源和向量模型")

    provider = data.embedding_provider
    model = data.embedding_model.strip()
    base_url = data.embedding_base_url or ""
    if provider == "openai":
        base_url = validate_model_base_url(base_url)
    else:
        base_url = ""

    user_id = getattr(getattr(auth, "user", None), "id", None)
    if record is None:
        record = AiEmbeddingConfigModel(provider=provider, model=model, base_url=base_url, created_id=user_id)
        auth.db.add(record)
    else:
        record.provider = provider
        record.model = model
        record.base_url = base_url
        record.updated_id = user_id
    return record


async def apply_embedding_model_config(
    auth: AuthSchema,
    remote: AiEmbeddingConfigPushSchema | dict[str, str],
) -> AiEmbeddingSyncOutSchema:
    """Apply a safe vector snapshot from either the cloud pull or push path."""
    previous = await load_runtime_embedding_model_config(auth)
    remote_config = AiEmbeddingConfigPushSchema.model_validate(remote)
    data = AiModelConfigUpdateSchema(
        embedding_provider=remote_config.provider,
        embedding_model=remote_config.model,
        embedding_base_url=remote_config.base_url,
    )
    record = await _update_embedding_record(auth, data, await _find_embedding_record(auth))
    await auth.db.flush()
    embedding = _apply_embedding_record(record)
    chat = await load_runtime_chat_model_config(auth)
    requires_reindex = (
        previous.provider != embedding.provider
        or previous.model != embedding.model
        or previous.base_url != embedding.base_url
    )
    return AiEmbeddingSyncOutSchema(
        config=_to_output(chat, embedding),
        requires_reindex=requires_reindex,
    )


async def sync_embedding_model_config(auth: AuthSchema) -> AiEmbeddingSyncOutSchema:
    """Pull the tenant-bound vector settings without importing a provider key."""
    from ..knowledge.member_client import CloudMemberClient

    remote = await CloudMemberClient(db=getattr(auth, "db", None)).get_embedding_config()
    return await apply_embedding_model_config(auth, remote)


async def update_model_config(
    auth: AuthSchema,
    data: AiModelConfigUpdateSchema,
) -> AiModelConfigOutSchema:
    record = await _find_record(auth)
    embedding_record = await _find_embedding_record(auth)
    has_embedding_update = _embedding_update_requested(data)
    has_chat_update = bool(data.chat_protocol and data.openai_base_url and data.openai_model)
    if not has_chat_update:
        if not has_embedding_update:
            raise ValueError("请配置完整的对话模型")
        embedding_record = await _update_embedding_record(auth, data, embedding_record)
        await auth.db.flush()
        embedding = _apply_embedding_record(embedding_record)
        return _to_output(await load_runtime_chat_model_config(auth), embedding)

    current = get_active_chat_model_config()
    if record is None:
        record = AiModelConfigModel(
            protocol=data.chat_protocol,
            openai_base_url=validate_model_base_url(data.openai_base_url),
            openai_model=data.openai_model,
            encrypted_api_key=_encrypt_api_key(data.openai_api_key or current.api_key) if (data.openai_api_key or current.api_key) else None,
            created_id=getattr(getattr(auth, "user", None), "id", None),
        )
        auth.db.add(record)
    else:
        record.protocol = data.chat_protocol
        record.openai_base_url = validate_model_base_url(data.openai_base_url)
        record.openai_model = data.openai_model
        if data.openai_api_key:
            record.encrypted_api_key = _encrypt_api_key(data.openai_api_key)
        record.updated_id = getattr(getattr(auth, "user", None), "id", None)

    if has_embedding_update:
        embedding_record = await _update_embedding_record(auth, data, embedding_record)
    await auth.db.flush()
    _apply_record(record)
    embedding = _apply_embedding_record(embedding_record) if has_embedding_update else get_active_embedding_model_config()
    return _to_output(get_active_chat_model_config(), embedding)
