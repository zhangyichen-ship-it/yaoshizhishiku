"""Add encrypted customer-side cloud member-service binding."""

import sqlalchemy as sa

from alembic import op

revision = "20260904_control_plane_config"
down_revision = "20260904_remove_kb_menus"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("ai_control_plane_config") or not inspector.has_table("sys_user"):
        return

    op.create_table(
        "ai_control_plane_config",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("uuid", sa.String(length=64), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("created_time", sa.DateTime(), nullable=False),
        sa.Column("updated_time", sa.DateTime(), nullable=False),
        sa.Column("deleted_time", sa.DateTime(), nullable=True),
        sa.Column("api_url", sa.String(length=500), nullable=False),
        sa.Column("instance_id", sa.Integer(), nullable=False),
        sa.Column("encrypted_service_credential", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        comment="AI 云面板成员服务绑定配置",
    )
    op.create_index("ix_ai_control_plane_config_id", "ai_control_plane_config", ["id"], unique=False)
    op.create_index("ix_ai_control_plane_config_uuid", "ai_control_plane_config", ["uuid"], unique=True)
    op.create_index("ix_ai_control_plane_config_is_deleted", "ai_control_plane_config", ["is_deleted"], unique=False)
    op.create_index("ix_ai_control_plane_config_created_time", "ai_control_plane_config", ["created_time"], unique=False)
    op.create_index("ix_ai_control_plane_config_updated_time", "ai_control_plane_config", ["updated_time"], unique=False)
    op.create_index("ix_ai_control_plane_config_deleted_time", "ai_control_plane_config", ["deleted_time"], unique=False)


def downgrade() -> None:
    if sa.inspect(op.get_bind()).has_table("ai_control_plane_config"):
        op.drop_table("ai_control_plane_config")
