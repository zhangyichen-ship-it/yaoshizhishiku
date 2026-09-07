"""Add cloud user identity to the customer-side model usage projection."""

import sqlalchemy as sa

from alembic import op

revision = "20260906_model_usage_user"
down_revision = "20260905_model_usage"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("ai_model_usage"):
        return

    columns = {column["name"] for column in inspector.get_columns("ai_model_usage")}
    if "cloud_user_id" not in columns:
        op.add_column(
            "ai_model_usage",
            sa.Column("cloud_user_id", sa.String(length=64), nullable=True, comment="云端用户ID"),
        )
    if "username" not in columns:
        op.add_column(
            "ai_model_usage",
            sa.Column("username", sa.String(length=64), nullable=True, comment="云端用户名"),
        )

    indexes = {index["name"] for index in sa.inspect(bind).get_indexes("ai_model_usage")}
    for name, column in (
        ("ix_ai_model_usage_cloud_user_id", "cloud_user_id"),
        ("ix_ai_model_usage_username", "username"),
    ):
        if name not in indexes:
            op.create_index(name, "ai_model_usage", [column], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("ai_model_usage"):
        return

    indexes = {index["name"] for index in inspector.get_indexes("ai_model_usage")}
    for name in ("ix_ai_model_usage_cloud_user_id", "ix_ai_model_usage_username"):
        if name in indexes:
            op.drop_index(name, table_name="ai_model_usage")

    columns = {column["name"] for column in sa.inspect(bind).get_columns("ai_model_usage")}
    for column in ("cloud_user_id", "username"):
        if column in columns:
            op.drop_column("ai_model_usage", column)
