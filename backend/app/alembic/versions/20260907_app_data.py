"""Add customer-side App Data resources, ACLs and audit records."""

import sqlalchemy as sa

from alembic import op

revision = "20260907_app_data"
down_revision = "20260906_model_usage_cost"
branch_labels = None
depends_on = None


def _indexes(bind: sa.Connection, table: str, definitions: tuple[tuple[str, str], ...]) -> None:
    existing = {item["name"] for item in sa.inspect(bind).get_indexes(table)}
    for name, column in definitions:
        if name not in existing:
            op.create_index(name, table, [column])


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("ai_app_resource"):
        op.create_table(
            "ai_app_resource",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("uuid", sa.String(length=64), nullable=False),
            sa.Column("is_deleted", sa.Boolean(), server_default=sa.false(), nullable=False),
            sa.Column("created_time", sa.DateTime(), nullable=False),
            sa.Column("updated_time", sa.DateTime(), nullable=False),
            sa.Column("deleted_time", sa.DateTime(), nullable=True),
            sa.Column("app_id", sa.String(length=150), nullable=False),
            sa.Column("resource_type", sa.String(length=128), nullable=False),
            sa.Column("data_scope", sa.String(length=16), nullable=False),
            sa.Column("access_policy", sa.String(length=32), nullable=False),
            sa.Column("owner_space_id", sa.String(length=128), nullable=True),
            sa.Column("payload_json", sa.Text(), nullable=False),
            sa.Column("external_ref", sa.Text(), nullable=True),
            sa.Column("schema_version", sa.String(length=32), server_default="1", nullable=False),
            sa.Column("version", sa.Integer(), server_default="1", nullable=False),
            sa.Column("idempotency_key", sa.String(length=128), nullable=True),
            sa.Column("created_by_subject_id", sa.String(length=128), nullable=False),
            sa.Column("updated_by_subject_id", sa.String(length=128), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("uuid", name="uq_ai_app_resource_uuid"),
            sa.UniqueConstraint("app_id", "idempotency_key", name="uq_ai_app_resource_app_idempotency"),
            comment="客户 App 业务资源",
        )
        _indexes(
            bind,
            "ai_app_resource",
            (
                ("ix_ai_app_resource_app_id", "app_id"),
                ("ix_ai_app_resource_resource_type", "resource_type"),
                ("ix_ai_app_resource_data_scope", "data_scope"),
                ("ix_ai_app_resource_access_policy", "access_policy"),
                ("ix_ai_app_resource_owner_space_id", "owner_space_id"),
                ("ix_ai_app_resource_idempotency_key", "idempotency_key"),
            ),
        )

    if not inspector.has_table("ai_app_resource_acl"):
        op.create_table(
            "ai_app_resource_acl",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("uuid", sa.String(length=64), nullable=False),
            sa.Column("is_deleted", sa.Boolean(), server_default=sa.false(), nullable=False),
            sa.Column("created_time", sa.DateTime(), nullable=False),
            sa.Column("updated_time", sa.DateTime(), nullable=False),
            sa.Column("deleted_time", sa.DateTime(), nullable=True),
            sa.Column("resource_id", sa.Integer(), nullable=False),
            sa.Column("subject_type", sa.String(length=16), nullable=False),
            sa.Column("subject_id", sa.String(length=128), nullable=False),
            sa.Column("permission", sa.String(length=16), nullable=False),
            sa.Column("granted_by_subject_id", sa.String(length=128), nullable=False),
            sa.ForeignKeyConstraint(["resource_id"], ["ai_app_resource.id"], ondelete="CASCADE", onupdate="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("uuid", name="uq_ai_app_resource_acl_uuid"),
            sa.UniqueConstraint(
                "resource_id",
                "subject_type",
                "subject_id",
                "permission",
                name="uq_ai_app_resource_acl_grant",
            ),
            comment="客户 App 资源 ACL",
        )
        _indexes(
            bind,
            "ai_app_resource_acl",
            (
                ("ix_ai_app_resource_acl_resource_id", "resource_id"),
                ("ix_ai_app_resource_acl_subject_type", "subject_type"),
                ("ix_ai_app_resource_acl_subject_id", "subject_id"),
            ),
        )

    if not inspector.has_table("ai_app_data_audit"):
        op.create_table(
            "ai_app_data_audit",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("uuid", sa.String(length=64), nullable=False),
            sa.Column("is_deleted", sa.Boolean(), server_default=sa.false(), nullable=False),
            sa.Column("created_time", sa.DateTime(), nullable=False),
            sa.Column("updated_time", sa.DateTime(), nullable=False),
            sa.Column("deleted_time", sa.DateTime(), nullable=True),
            sa.Column("request_id", sa.String(length=128), nullable=False),
            sa.Column("app_id", sa.String(length=150), nullable=False),
            sa.Column("resource_type", sa.String(length=128), nullable=False),
            sa.Column("resource_id", sa.String(length=64), nullable=True),
            sa.Column("actor_subject_id", sa.String(length=128), nullable=False),
            sa.Column("actor_membership_id", sa.String(length=128), nullable=True),
            sa.Column("action", sa.String(length=16), nullable=False),
            sa.Column("result", sa.String(length=16), nullable=False),
            sa.Column("reason_code", sa.String(length=64), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("uuid", name="uq_ai_app_data_audit_uuid"),
            comment="客户 App 数据审计",
        )
        _indexes(
            bind,
            "ai_app_data_audit",
            (
                ("ix_ai_app_data_audit_request_id", "request_id"),
                ("ix_ai_app_data_audit_app_id", "app_id"),
                ("ix_ai_app_data_audit_resource_type", "resource_type"),
                ("ix_ai_app_data_audit_resource_id", "resource_id"),
                ("ix_ai_app_data_audit_actor_subject_id", "actor_subject_id"),
                ("ix_ai_app_data_audit_actor_membership_id", "actor_membership_id"),
                ("ix_ai_app_data_audit_result", "result"),
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("ai_app_data_audit"):
        op.drop_table("ai_app_data_audit")
    if inspector.has_table("ai_app_resource_acl"):
        op.drop_table("ai_app_resource_acl")
    if inspector.has_table("ai_app_resource"):
        op.drop_table("ai_app_resource")
