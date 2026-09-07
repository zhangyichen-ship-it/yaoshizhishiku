"""Add the customer-side model usage projection."""

import sqlalchemy as sa

from alembic import op

revision = "20260905_model_usage"
down_revision = "20260905_remove_customer_chat"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("ai_model_usage"):
        return

    op.create_table(
        "ai_model_usage",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("uuid", sa.String(length=64), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("created_time", sa.DateTime(), nullable=False),
        sa.Column("updated_time", sa.DateTime(), nullable=False),
        sa.Column("deleted_time", sa.DateTime(), nullable=True),
        sa.Column("source_request_id", sa.String(length=64), nullable=False),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("requested_model", sa.String(length=255), nullable=False),
        sa.Column("upstream_model", sa.String(length=255), nullable=False),
        sa.Column("provider_name", sa.String(length=100), nullable=False),
        sa.Column("protocol", sa.String(length=32), nullable=False),
        sa.Column("purpose", sa.String(length=32), server_default="chat", nullable=False),
        sa.Column("status", sa.Integer(), nullable=False),
        sa.Column("response_code", sa.Integer(), nullable=False),
        sa.Column("is_stream", sa.Boolean(), server_default=sa.text("0"), nullable=False),
        sa.Column("usage_reported", sa.Boolean(), server_default=sa.text("0"), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("completion_tokens", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("cached_input_tokens", sa.Integer(), nullable=True),
        sa.Column("cache_creation_input_tokens", sa.Integer(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_request_id", name="uq_ai_model_usage_source_request"),
        comment="AI 模型 Token 用量投影",
    )
    for name, column in (
        ("ix_ai_model_usage_id", "id"),
        ("ix_ai_model_usage_uuid", "uuid"),
        ("ix_ai_model_usage_is_deleted", "is_deleted"),
        ("ix_ai_model_usage_created_time", "created_time"),
        ("ix_ai_model_usage_updated_time", "updated_time"),
        ("ix_ai_model_usage_deleted_time", "deleted_time"),
        ("ix_ai_model_usage_source_request_id", "source_request_id"),
        ("ix_ai_model_usage_occurred_at", "occurred_at"),
        ("ix_ai_model_usage_requested_model", "requested_model"),
        ("ix_ai_model_usage_status", "status"),
    ):
        op.create_index(name, "ai_model_usage", [column], unique=False)


def downgrade() -> None:
    if sa.inspect(op.get_bind()).has_table("ai_model_usage"):
        op.drop_table("ai_model_usage")
