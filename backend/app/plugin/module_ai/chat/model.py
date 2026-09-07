from __future__ import annotations

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import ModelMixin, UserMixin


class AiModelConfigModel(ModelMixin, UserMixin):
    """Persisted global chat-model override for the single-organization app."""

    __tablename__ = "ai_model_config"
    __table_args__ = {"comment": "AI chat model configuration"}
    __loader_options__: list[str] = ["created_by", "updated_by", "deleted_by"]

    protocol: Mapped[str] = mapped_column(String(32), default="openai", nullable=False)
    openai_base_url: Mapped[str] = mapped_column(String(500), nullable=False)
    openai_model: Mapped[str] = mapped_column(String(200), nullable=False)
    encrypted_api_key: Mapped[str | None] = mapped_column(Text, default=None, nullable=True)


class AiEmbeddingConfigModel(ModelMixin, UserMixin):
    """Persisted local vector-model configuration."""

    __tablename__ = "ai_embedding_config"
    __table_args__ = {"comment": "AI embedding model configuration"}
    __loader_options__: list[str] = ["created_by", "updated_by", "deleted_by"]

    provider: Mapped[str] = mapped_column(String(16), default="local", nullable=False)
    model: Mapped[str] = mapped_column(String(200), nullable=False)
    base_url: Mapped[str] = mapped_column(String(500), default="", nullable=False)
