"""Add the local persisted vector-model configuration."""

import sqlalchemy as sa

from alembic import op

revision = "20260904_embedding_config"
down_revision = "20260903_customer_kb_member_acl"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("ai_embedding_config") or not inspector.has_table("sys_user"):
        return

    op.create_table(
        "ai_embedding_config",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("uuid", sa.String(length=64), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("created_time", sa.DateTime(), nullable=False),
        sa.Column("updated_time", sa.DateTime(), nullable=False),
        sa.Column("deleted_time", sa.DateTime(), nullable=True),
        sa.Column("created_id", sa.Integer(), nullable=True),
        sa.Column("updated_id", sa.Integer(), nullable=True),
        sa.Column("deleted_id", sa.Integer(), nullable=True),
        sa.Column("provider", sa.String(length=16), server_default="local", nullable=False),
        sa.Column("model", sa.String(length=200), nullable=False),
        sa.Column("base_url", sa.String(length=500), server_default="", nullable=False),
        sa.ForeignKeyConstraint(["created_id"], ["sys_user.id"], ondelete="SET NULL", onupdate="CASCADE"),
        sa.ForeignKeyConstraint(["updated_id"], ["sys_user.id"], ondelete="SET NULL", onupdate="CASCADE"),
        sa.ForeignKeyConstraint(["deleted_id"], ["sys_user.id"], ondelete="SET NULL", onupdate="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        comment="AI 向量模型配置",
    )
    op.create_index("ix_ai_embedding_config_id", "ai_embedding_config", ["id"], unique=False)
    op.create_index("ix_ai_embedding_config_uuid", "ai_embedding_config", ["uuid"], unique=True)
    op.create_index("ix_ai_embedding_config_is_deleted", "ai_embedding_config", ["is_deleted"], unique=False)
    op.create_index("ix_ai_embedding_config_created_time", "ai_embedding_config", ["created_time"], unique=False)
    op.create_index("ix_ai_embedding_config_updated_time", "ai_embedding_config", ["updated_time"], unique=False)
    op.create_index("ix_ai_embedding_config_deleted_time", "ai_embedding_config", ["deleted_time"], unique=False)
    op.create_index("ix_ai_embedding_config_created_id", "ai_embedding_config", ["created_id"], unique=False)
    op.create_index("ix_ai_embedding_config_updated_id", "ai_embedding_config", ["updated_id"], unique=False)
    op.create_index("ix_ai_embedding_config_deleted_id", "ai_embedding_config", ["deleted_id"], unique=False)


def downgrade() -> None:
    if sa.inspect(op.get_bind()).has_table("ai_embedding_config"):
        op.drop_table("ai_embedding_config")
