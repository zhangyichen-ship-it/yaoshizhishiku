from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import ModelMixin, UserMixin


class KnowledgeBaseModel(ModelMixin, UserMixin):
    """Knowledge base metadata stored in MySQL."""

    __tablename__ = "ai_knowledge_base"
    __table_args__ = {"comment": "AI knowledge base"}
    __loader_options__: list[str] = ["created_by", "updated_by", "deleted_by"]

    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True, comment="Knowledge base name")
    description: Mapped[str | None] = mapped_column(Text, default=None, nullable=True, comment="Description")
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("1"), nullable=False, index=True)

    documents: Mapped[list["KnowledgeDocumentModel"]] = relationship(
        "KnowledgeDocumentModel",
        back_populates="knowledge_base",
        cascade="all, delete-orphan",
    )
    access_grants: Mapped[list["KnowledgeBaseAccessModel"]] = relationship(
        "KnowledgeBaseAccessModel",
        back_populates="knowledge_base",
        cascade="all, delete-orphan",
    )


class KnowledgeDocumentModel(ModelMixin, UserMixin):
    """Document metadata and indexing status stored in MySQL."""

    __tablename__ = "ai_knowledge_document"
    __table_args__ = {"comment": "AI knowledge document"}
    __loader_options__: list[str] = ["knowledge_base", "created_by", "updated_by", "deleted_by"]

    knowledge_base_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("ai_knowledge_base.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str | None] = mapped_column(String(500), default=None, nullable=True)
    file_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    file_size: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"), nullable=False)
    parse_status: Mapped[str] = mapped_column(String(32), default="pending", server_default=text("'pending'"), nullable=False, index=True)
    index_status: Mapped[str] = mapped_column(String(32), default="pending", server_default=text("'pending'"), nullable=False, index=True)
    error_message: Mapped[str | None] = mapped_column(Text, default=None, nullable=True)
    parsed_at: Mapped[datetime | None] = mapped_column(DateTime, default=None, nullable=True)
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime, default=None, nullable=True)

    knowledge_base: Mapped[KnowledgeBaseModel] = relationship("KnowledgeBaseModel", back_populates="documents")
    chunks: Mapped[list["KnowledgeChunkModel"]] = relationship(
        "KnowledgeChunkModel",
        back_populates="document",
        cascade="all, delete-orphan",
    )


class KnowledgeChunkModel(ModelMixin, UserMixin):
    """Chunk metadata stored in MySQL; vector content lives in ChromaDB."""

    __tablename__ = "ai_knowledge_chunk"
    __table_args__ = {"comment": "AI knowledge chunk"}
    __loader_options__: list[str] = ["document", "created_by", "updated_by", "deleted_by"]

    knowledge_base_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("ai_knowledge_base.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("ai_knowledge_document.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"), nullable=False)
    chroma_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)

    document: Mapped[KnowledgeDocumentModel] = relationship("KnowledgeDocumentModel", back_populates="chunks")


class AiControlPlaneConfigModel(ModelMixin):
    """Encrypted customer-side binding to the cloud member service."""

    __tablename__ = "ai_control_plane_config"
    __table_args__ = {"comment": "AI 云面板成员服务绑定配置"}

    api_url: Mapped[str] = mapped_column(String(500), nullable=False, comment="云面板成员服务地址")
    instance_id: Mapped[int] = mapped_column(Integer, nullable=False, comment="客户知识库实例ID")
    encrypted_service_credential: Mapped[str] = mapped_column(Text, nullable=False, comment="加密后的云面板服务凭证")


class KbMemberModel(ModelMixin):
    """Minimal local projection of a cloud employee.

    The customer knowledge base never owns the employee credential.  The
    ``cloud_user_id`` is an external identifier and deliberately has no
    database foreign key because the cloud control plane uses a different
    database.
    """

    __tablename__ = "kb_member"
    __table_args__ = (
        UniqueConstraint("cloud_user_id", name="uq_kb_member_cloud_user"),
        UniqueConstraint("username", name="uq_kb_member_username"),
        {"comment": "客户知识库云端员工最小映射"},
    )

    cloud_user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True, comment="云端用户ID")
    username: Mapped[str] = mapped_column(String(64), nullable=False, comment="云端登录账号")
    name: Mapped[str] = mapped_column(String(32), nullable=False, comment="员工名称")
    email: Mapped[str | None] = mapped_column(String(254), default=None, nullable=True, comment="员工邮箱")
    cloud_status: Mapped[int] = mapped_column(Integer, default=0, nullable=False, index=True, comment="云端账号状态")
    cloud_knowledge_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default=text("0"),
        nullable=False,
        index=True,
        comment="云端生效的知识库产品权限",
    )
    local_role: Mapped[str] = mapped_column(String(16), default="member", server_default=text("'member'"), nullable=False, comment="客户知识库本地角色")
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime, default=None, nullable=True, comment="最后同步时间")

    access_grants: Mapped[list["KnowledgeBaseAccessModel"]] = relationship(
        "KnowledgeBaseAccessModel",
        back_populates="member",
        cascade="all, delete-orphan",
    )


class KnowledgeBaseAccessModel(ModelMixin):
    """Local ACL mapping a cloud employee to a customer knowledge base."""

    __tablename__ = "kb_knowledge_base_acl"
    __table_args__ = (
        UniqueConstraint("member_id", "knowledge_base_id", name="uq_kb_acl_member_knowledge_base"),
        {"comment": "客户知识库员工访问授权"},
    )

    member_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("kb_member.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
        comment="本地云端员工映射ID",
    )
    knowledge_base_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("ai_knowledge_base.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
        comment="本地知识库ID",
    )
    granted_by_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("sys_user.id", ondelete="SET NULL", onupdate="CASCADE"),
        default=None,
        nullable=True,
        index=True,
        comment="授权操作人ID",
    )

    member: Mapped[KbMemberModel] = relationship("KbMemberModel", back_populates="access_grants")
    knowledge_base: Mapped[KnowledgeBaseModel] = relationship("KnowledgeBaseModel", back_populates="access_grants")


class AiModelUsageModel(ModelMixin):
    """Non-sensitive model-usage projection received from the cloud panel."""

    __tablename__ = "ai_model_usage"
    __table_args__ = (
        UniqueConstraint("source_request_id", name="uq_ai_model_usage_source_request"),
        {"comment": "AI 模型 Token 用量投影"},
    )

    cloud_user_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True, comment="云端用户ID")
    username: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True, comment="云端用户名")
    source_request_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True, comment="云面板请求号")
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True, comment="模型请求发生时间")
    requested_model: Mapped[str] = mapped_column(String(255), nullable=False, index=True, comment="请求模型")
    upstream_model: Mapped[str] = mapped_column(String(255), nullable=False, comment="上游模型")
    provider_name: Mapped[str] = mapped_column(String(100), nullable=False, comment="供应商")
    protocol: Mapped[str] = mapped_column(String(32), nullable=False, comment="模型协议")
    purpose: Mapped[str] = mapped_column(String(32), nullable=False, server_default=text("'chat'"), comment="请求用途")
    status: Mapped[int] = mapped_column(Integer, nullable=False, index=True, comment="请求状态")
    response_code: Mapped[int] = mapped_column(Integer, nullable=False, comment="响应状态码")
    is_stream: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("0"), comment="是否流式")
    usage_reported: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("0"), comment="是否上报用量")
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"), comment="输入 Token 数")
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"), comment="输出 Token 数")
    cached_input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="缓存命中输入 Token 数")
    cache_creation_input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="缓存写入输入 Token 数")
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"), comment="耗时毫秒")
    input_cost_cny: Mapped[Decimal | None] = mapped_column(Numeric(24, 12), nullable=True, comment="输入费用，人民币元")
    output_cost_cny: Mapped[Decimal | None] = mapped_column(Numeric(24, 12), nullable=True, comment="输出费用，人民币元")
    total_cost_cny: Mapped[Decimal | None] = mapped_column(Numeric(24, 12), nullable=True, comment="总费用，人民币元")
    free_cost_cny: Mapped[Decimal] = mapped_column(
        Numeric(24, 12), nullable=False, server_default=text("0"), comment="免费额度消耗，人民币元"
    )
    paid_cost_cny: Mapped[Decimal] = mapped_column(
        Numeric(24, 12), nullable=False, server_default=text("0"), comment="付费额度消耗，人民币元"
    )
    billing_status: Mapped[str | None] = mapped_column(String(32), nullable=True, comment="云端结算状态")
