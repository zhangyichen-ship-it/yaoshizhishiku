"""Remove customer-console dictionary and parameter menus."""

import sqlalchemy as sa

from alembic import op

revision = "20260904_remove_kb_menus"
down_revision = "20260904_embedding_config"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())
    if "platform_menu" not in table_names:
        return

    menu = sa.table(
        "platform_menu",
        sa.column("id", sa.Integer()),
        sa.column("parent_id", sa.Integer()),
        sa.column("route_name", sa.String()),
    )
    rows = bind.execute(sa.select(menu.c.id, menu.c.parent_id, menu.c.route_name)).mappings().all()
    parent_by_id = {row["id"]: row["parent_id"] for row in rows}
    delete_ids = {row["id"] for row in rows if row["route_name"] in {"Dict", "Params"}}

    changed = True
    while changed:
        changed = False
        for menu_id, parent_id in parent_by_id.items():
            if parent_id in delete_ids and menu_id not in delete_ids:
                delete_ids.add(menu_id)
                changed = True

    if not delete_ids:
        return

    if "sys_role_menus" in table_names:
        role_menus = sa.table("sys_role_menus", sa.column("menu_id", sa.Integer()))
        op.execute(sa.delete(role_menus).where(role_menus.c.menu_id.in_(delete_ids)))

    # Delete descendants first so this also works when a database enforces the
    # self-referencing menu foreign key without relying on ON DELETE behavior.
    remaining = set(delete_ids)
    while remaining:
        leaf_ids = {
            menu_id
            for menu_id in remaining
            if not any(parent_by_id.get(child_id) == menu_id for child_id in remaining)
        }
        if not leaf_ids:
            leaf_ids = remaining
        op.execute(sa.delete(menu).where(menu.c.id.in_(leaf_ids)))
        remaining.difference_update(leaf_ids)


def downgrade() -> None:
    # Removed seed records are intentionally not recreated on downgrade.
    pass
