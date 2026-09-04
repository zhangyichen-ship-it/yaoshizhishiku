from dataclasses import dataclass
from typing import Any, Literal

from fastapi import Query
from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.base_params import BaseQueryParam, UserByQueryParam
from app.plugin.module_ai.config import validate_model_base_url

EmbeddingProvider = Literal["local", "openai"]


class ChatQuerySchema(BaseModel):
    """WebSocket chat request."""

    message: str = Field(..., min_length=1, max_length=8_000, description="Message content")
    session_id: str | None = Field(None, description="Session ID")
    files: list[dict[str, Any]] | None = Field(None, description="Ad-hoc file context")
    knowledge_base_ids: list[int] = Field(default_factory=list, max_length=20, description="Knowledge base IDs")


class ChatSessionCreateSchema(BaseModel):
    """Create chat session request."""

    title: str = Field(..., min_length=1, max_length=200, description="Session title")

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 1 or len(value) > 200:
            raise ValueError("会话标题长度必须在 1-200 个字符之间")
        return value


class ChatSessionUpdateSchema(BaseModel):
    """Update chat session request."""

    title: str = Field(..., min_length=1, max_length=200, description="Session title")

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 1 or len(value) > 200:
            raise ValueError("会话标题长度必须在 1-200 个字符之间")
        return value


@dataclass
class ChatSessionQueryParam(BaseQueryParam, UserByQueryParam):
    """Chat session list query."""

    title: str | None = Query(None, description="Session title")


class AiChatRequestSchema(BaseModel):
    """Non-streaming AI chat request."""

    message: str = Field(..., min_length=1, max_length=8_000, description="User message")
    session_id: str | None = Field(None, description="Session ID; creates a new session when omitted")
    knowledge_base_ids: list[int] = Field(default_factory=list, max_length=20, description="Knowledge base IDs")

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 1:
            raise ValueError("用户消息内容不能为空")
        return value


class AiChatResponseSchema(BaseModel):
    """Non-streaming AI chat response."""

    response: str = Field(..., description="AI response content")
    session_id: str = Field(..., description="Session ID")
    function_calls: list[dict[str, Any]] | None = Field(None, description="Function call metadata")
    action: dict[str, Any] | None = Field(None, description="Suggested action")


class AiEmbeddingConfigOutSchema(BaseModel):
    """Safe vector-model configuration received from the cloud panel."""

    provider: EmbeddingProvider
    model: str
    base_url: str


class AiModelConfigOutSchema(BaseModel):
    """Safe AI runtime configuration status."""

    chat_protocol: Literal["openai", "anthropic"]
    openai_base_url: str
    openai_model: str
    openai_embedding_model: str
    embedding_provider: EmbeddingProvider
    embedding_model: str
    embedding_base_url: str
    embedding_api_key_configured: bool
    local_embedding_model: str
    openai_api_key_configured: bool
    chroma_persist_dir: str
    chroma_collection_name: str


class AiModelConfigUpdateSchema(BaseModel):
    """Editable chat and vector-model configuration."""

    chat_protocol: Literal["openai", "anthropic"] | None = "openai"
    openai_base_url: str | None = Field(default=None, min_length=1, max_length=500)
    openai_model: str | None = Field(default=None, min_length=1, max_length=200)
    openai_api_key: str | None = Field(default=None, min_length=1, max_length=512)
    embedding_provider: EmbeddingProvider | None = None
    embedding_model: str | None = Field(default=None, max_length=200)
    embedding_base_url: str | None = Field(default=None, max_length=500)
    embedding_api_key: str | None = Field(default=None, min_length=1, max_length=512)

    @field_validator("openai_base_url")
    @classmethod
    def validate_base_url(cls, value: str) -> str:
        if value is None:
            return value
        return validate_model_base_url(value)

    @field_validator("openai_model")
    @classmethod
    def validate_model(cls, value: str) -> str:
        if value is None:
            return value
        normalized = value.strip()
        if not normalized:
            raise ValueError("对话模型名称不能为空")
        return normalized

    @field_validator("openai_api_key")
    @classmethod
    def normalize_api_key(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("embedding_model")
    @classmethod
    def validate_embedding_model(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = value.strip()
        if not normalized:
            raise ValueError("向量模型名称不能为空")
        return normalized

    @field_validator("embedding_base_url")
    @classmethod
    def validate_embedding_base_url(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = value.strip()
        return validate_model_base_url(normalized) if normalized else ""

    @field_validator("embedding_api_key")
    @classmethod
    def normalize_embedding_api_key(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @model_validator(mode="after")
    def validate_chat_or_embedding_config(self) -> "AiModelConfigUpdateSchema":
        has_embedding_config = any(
            value is not None
            for value in (
                self.embedding_provider,
                self.embedding_model,
                self.embedding_base_url,
                self.embedding_api_key,
            )
        )
        if has_embedding_config:
            if not self.embedding_provider or not self.embedding_model:
                raise ValueError("请同时配置向量来源和向量模型")
            if self.embedding_provider == "openai" and not self.embedding_base_url:
                raise ValueError("OpenAI 向量模型必须配置 API 地址")
        if has_embedding_config and not self.openai_base_url and not self.openai_model:
            return self
        if not self.chat_protocol or not self.openai_base_url or not self.openai_model:
            raise ValueError("请配置完整的对话模型")
        return self


class AiEmbeddingSyncOutSchema(BaseModel):
    """Result of explicitly syncing vector configuration from the cloud panel."""

    config: AiModelConfigOutSchema
    requires_reindex: bool
