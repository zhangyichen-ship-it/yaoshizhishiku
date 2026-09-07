"""Add CNY cost fields to the customer-side model usage projection."""

import sqlalchemy as sa

from alembic import op

revision = "20260906_model_usage_cost"
down_revision = "20260906_model_usage_user"
branch_labels = None
depends_on = None


_COST_COLUMNS = (
    ("input_cost_cny", sa.Numeric(precision=24, scale=12), True),
    ("output_cost_cny", sa.Numeric(precision=24, scale=12), True),
    ("total_cost_cny", sa.Numeric(precision=24, scale=12), True),
    ("free_cost_cny", sa.Numeric(precision=24, scale=12), False),
    ("paid_cost_cny", sa.Numeric(precision=24, scale=12), False),
    ("billing_status", sa.String(length=32), True),
)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("ai_model_usage"):
        return

    columns = {column["name"] for column in inspector.get_columns("ai_model_usage")}
    for name, column_type, nullable in _COST_COLUMNS:
        if name in columns:
            continue
        kwargs = {"nullable": nullable}
        if name in {"free_cost_cny", "paid_cost_cny"}:
            kwargs["server_default"] = sa.text("0")
        op.add_column("ai_model_usage", sa.Column(name, column_type, **kwargs))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("ai_model_usage"):
        return
    columns = {column["name"] for column in inspector.get_columns("ai_model_usage")}
    for name, _column_type, _nullable in reversed(_COST_COLUMNS):
        if name in columns:
            op.drop_column("ai_model_usage", name)

