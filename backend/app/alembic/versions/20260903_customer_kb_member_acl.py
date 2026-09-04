"""Add customer KB employee projection and local knowledge ACL tables."""

import sqlalchemy as sa

from alembic import op

revision = "20260903_customer_kb_member_acl"
down_revision = None
branch_labels = None
depends_on = None


def _create_member_table() -> None:
    op.create_table(
        "kb_member",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("uuid", sa.String(length=64), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("created_time", sa.DateTime(), nullable=False),
        sa.Column("updated_time", sa.DateTime(), nullable=False),
        sa.Column("deleted_time", sa.DateTime(), nullable=True),
        sa.Column("cloud_user_id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=32), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=True),
        sa.Column("cloud_status", sa.Integer(), nullable=False),
        sa.Column("cloud_knowledge_enabled", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("local_role", sa.String(length=16), nullable=False, server_default=sa.text("'member'")),
        sa.Column("last_synced_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cloud_user_id", name="uq_kb_member_cloud_user"),
        sa.UniqueConstraint("username", name="uq_kb_member_username"),
        comment="客户知识库云端员工最小映射",
    )
    op.create_index("ix_kb_member_id", "kb_member", ["id"], unique=False)
    op.create_index("ix_kb_member_uuid", "kb_member", ["uuid"], unique=True)
    op.create_index("ix_kb_member_is_deleted", "kb_member", ["is_deleted"], unique=False)
    op.create_index("ix_kb_member_created_time", "kb_member", ["created_time"], unique=False)
    op.create_index("ix_kb_member_updated_time", "kb_member", ["updated_time"], unique=False)
    op.create_index("ix_kb_member_deleted_time", "kb_member", ["deleted_time"], unique=False)
    op.create_index("ix_kb_member_cloud_user_id", "kb_member", ["cloud_user_id"], unique=False)
    op.create_index("ix_kb_member_cloud_status", "kb_member", ["cloud_status"], unique=False)
    op.create_index("ix_kb_member_cloud_knowledge_enabled", "kb_member", ["cloud_knowledge_enabled"], unique=False)


def _create_acl_table() -> None:
    op.create_table(
        "kb_knowledge_base_acl",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("uuid", sa.String(length=64), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("created_time", sa.DateTime(), nullable=False),
        sa.Column("updated_time", sa.DateTime(), nullable=False),
        sa.Column("deleted_time", sa.DateTime(), nullable=True),
        sa.Column("member_id", sa.Integer(), nullable=False),
        sa.Column("knowledge_base_id", sa.Integer(), nullable=False),
        sa.Column("granted_by_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["granted_by_id"], ["sys_user.id"], ondelete="SET NULL", onupdate="CASCADE"),
        sa.ForeignKeyConstraint(["knowledge_base_id"], ["ai_knowledge_base.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["member_id"], ["kb_member.id"], ondelete="CASCADE", onupdate="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("member_id", "knowledge_base_id", name="uq_kb_acl_member_knowledge_base"),
        comment="客户知识库员工访问授权",
    )
    op.create_index("ix_kb_knowledge_base_acl_id", "kb_knowledge_base_acl", ["id"], unique=False)
    op.create_index("ix_kb_knowledge_base_acl_uuid", "kb_knowledge_base_acl", ["uuid"], unique=True)
    op.create_index("ix_kb_knowledge_base_acl_is_deleted", "kb_knowledge_base_acl", ["is_deleted"], unique=False)
    op.create_index("ix_kb_knowledge_base_acl_created_time", "kb_knowledge_base_acl", ["created_time"], unique=False)
    op.create_index("ix_kb_knowledge_base_acl_updated_time", "kb_knowledge_base_acl", ["updated_time"], unique=False)
    op.create_index("ix_kb_knowledge_base_acl_deleted_time", "kb_knowledge_base_acl", ["deleted_time"], unique=False)
    op.create_index("ix_kb_knowledge_base_acl_member_id", "kb_knowledge_base_acl", ["member_id"], unique=False)
    op.create_index(
        "ix_kb_knowledge_base_acl_knowledge_base_id",
        "kb_knowledge_base_acl",
        ["knowledge_base_id"],
        unique=False,
    )
    op.create_index("ix_kb_knowledge_base_acl_granted_by_id", "kb_knowledge_base_acl", ["granted_by_id"], unique=False)


def upgrade() -> None:
    bind = op.get_bind()
    table_names = set(sa.inspect(bind).get_table_names())
    if "kb_member" not in table_names:
        _create_member_table()

    # Startup applies Alembic before ORM create_all.  On a fresh AI database,
    # defer this FK-dependent table to create_all; existing AI deployments can
    # create it directly here.
    table_names = set(sa.inspect(bind).get_table_names())
    if (
        "kb_knowledge_base_acl" not in table_names
        and "ai_knowledge_base" in table_names
        and "sys_user" in table_names
    ):
        _create_acl_table()


def downgrade() -> None:
    bind = op.get_bind()
    table_names = set(sa.inspect(bind).get_table_names())
    if "kb_knowledge_base_acl" in table_names:
        op.drop_table("kb_knowledge_base_acl")
    if "kb_member" in table_names:
        op.drop_table("kb_member")
