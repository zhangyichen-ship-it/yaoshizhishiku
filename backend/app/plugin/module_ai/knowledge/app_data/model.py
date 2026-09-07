from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import ModelMixin


class AppResourceModel(ModelMixin):
    """One customer-side App resource; deployment boundary replaces tenant_id in V1."""

    __tablename__ = "ai_app_resource"
    __table_args__ = (
        UniqueConstraint("app_id", "idempotency_key", name="uq_ai_app_resource_app_idempotency"),
        {"comment": "客户 App 业务资源"},
    )

    app_id: Mapped[str] = mapped_column(String(150), nullable=False, index=True, comment="App 稳定ID")
    resource_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True, comment="资源类型")
    data_scope: Mapped[str] = mapped_column(String(16), nullable=False, index=True, comment="数据作用域")
    access_policy: Mapped[str] = mapped_column(String(32), nullable=False, index=True, comment="访问策略")
    owner_space_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True, comment="USER 数据所有者 Space")
    payload_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}", comment="业务数据JSON")
    external_ref: Mapped[str | None] = mapped_column(Text, nullable=True, comment="文件或向量等外部引用")
    schema_version: Mapped[str] = mapped_column(String(32), nullable=False, default="1", comment="业务Schema版本")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, comment="并发版本")
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True, comment="写入幂等键")
    created_by_subject_id: Mapped[str] = mapped_column(String(128), nullable=False, comment="创建者主体")
    updated_by_subject_id: Mapped[str] = mapped_column(String(128), nullable=False, comment="最后修改者主体")


class AppResourceAclModel(ModelMixin):
    """V1 ACL supports USER and ROLE subjects only."""

    __tablename__ = "ai_app_resource_acl"
    __table_args__ = (
        UniqueConstraint("resource_id", "subject_type", "subject_id", "permission", name="uq_ai_app_resource_acl_grant"),
        {"comment": "客户 App 资源 ACL"},
    )

    resource_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("ai_app_resource.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
        comment="资源ID",
    )
    subject_type: Mapped[str] = mapped_column(String(16), nullable=False, index=True, comment="主体类型")
    subject_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True, comment="主体ID")
    permission: Mapped[str] = mapped_column(String(16), nullable=False, comment="权限")
    granted_by_subject_id: Mapped[str] = mapped_column(String(128), nullable=False, comment="授权者主体")


class AppDataAuditModel(ModelMixin):
    """Append-only audit projection for customer App Data operations."""

    __tablename__ = "ai_app_data_audit"
    __table_args__ = {"comment": "客户 App 数据审计"}

    request_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True, comment="请求ID")
    app_id: Mapped[str] = mapped_column(String(150), nullable=False, index=True, comment="App 稳定ID")
    resource_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True, comment="资源类型")
    resource_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True, comment="资源UUID")
    actor_subject_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True, comment="操作者主体")
    actor_membership_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True, comment="操作者成员关系")
    action: Mapped[str] = mapped_column(String(16), nullable=False, comment="动作")
    result: Mapped[str] = mapped_column(String(16), nullable=False, index=True, comment="结果")
    reason_code: Mapped[str] = mapped_column(String(64), nullable=False, comment="原因码")
