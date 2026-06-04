"""add_tenant_id_columns — add tenant_id FK to all data models

Revision ID: 0005
Revises: 0003, 6887a999c396
Create Date: 2026-06-03
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[tuple[str, str], None] = ("0003", "6887a999c396")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name if bind else "sqlite"

    # 1. Ensure legacy tenant exists (id=1) for backfill
    if dialect == "sqlite":
        op.execute("INSERT OR IGNORE INTO tenants (id, name, api_key, plan, active, agents_limit, tasks_monthly_limit, tokens_monthly_limit, cost_monthly_limit_usd, rpm_limit) VALUES (1, 'Legacy', 'legacy-api-key', 'starter', 1, 3, 1000, 10000000, 50.0, 60)")
    else:
        op.execute("""
            INSERT INTO tenants (id, name, api_key, plan, active, agents_limit, tasks_monthly_limit, tokens_monthly_limit, cost_monthly_limit_usd, rpm_limit)
            SELECT 1, 'Legacy', 'legacy-api-key', 'starter', TRUE, 3, 1000, 10000000, 50.0, 60
            WHERE NOT EXISTS (SELECT 1 FROM tenants WHERE id = 1)
        """)

    # 2. Add tenant_id to tasks
    with op.batch_alter_table("tasks") as batch_op:
        batch_op.add_column(sa.Column("tenant_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key("fk_tasks_tenant_id", "tenants", ["tenant_id"], ["id"])
        batch_op.create_index("ix_tasks_tenant_id", ["tenant_id"])
    op.execute("UPDATE tasks SET tenant_id = 1 WHERE tenant_id IS NULL")
    with op.batch_alter_table("tasks") as batch_op:
        batch_op.alter_column("tenant_id", nullable=False)

    # 3. Add tenant_id to agent_runs
    with op.batch_alter_table("agent_runs") as batch_op:
        batch_op.add_column(sa.Column("tenant_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key("fk_agent_runs_tenant_id", "tenants", ["tenant_id"], ["id"])
        batch_op.create_index("ix_agent_runs_tenant_id", ["tenant_id"])
    op.execute("UPDATE agent_runs SET tenant_id = 1 WHERE tenant_id IS NULL")
    with op.batch_alter_table("agent_runs") as batch_op:
        batch_op.alter_column("tenant_id", nullable=False)

    # 4. Add tenant_id to model_calls
    with op.batch_alter_table("model_calls") as batch_op:
        batch_op.add_column(sa.Column("tenant_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key("fk_model_calls_tenant_id", "tenants", ["tenant_id"], ["id"])
        batch_op.create_index("ix_model_calls_tenant_id", ["tenant_id"])
    op.execute("UPDATE model_calls SET tenant_id = 1 WHERE tenant_id IS NULL")
    with op.batch_alter_table("model_calls") as batch_op:
        batch_op.alter_column("tenant_id", nullable=False)

    # 5. Add tenant_id to memory_entries
    with op.batch_alter_table("memory_entries") as batch_op:
        batch_op.add_column(sa.Column("tenant_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key("fk_memory_entries_tenant_id", "tenants", ["tenant_id"], ["id"])
        batch_op.create_index("ix_memory_entries_tenant_id", ["tenant_id"])
    op.execute("UPDATE memory_entries SET tenant_id = 1 WHERE tenant_id IS NULL")
    with op.batch_alter_table("memory_entries") as batch_op:
        batch_op.alter_column("tenant_id", nullable=False)

    # 6. Add tenant_id to social_posts
    with op.batch_alter_table("social_posts") as batch_op:
        batch_op.add_column(sa.Column("tenant_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key("fk_social_posts_tenant_id", "tenants", ["tenant_id"], ["id"])
        batch_op.create_index("ix_social_posts_tenant_id", ["tenant_id"])
    op.execute("UPDATE social_posts SET tenant_id = 1 WHERE tenant_id IS NULL")
    with op.batch_alter_table("social_posts") as batch_op:
        batch_op.alter_column("tenant_id", nullable=False)

    # 7. Add tenant_id to social_engagements
    with op.batch_alter_table("social_engagements") as batch_op:
        batch_op.add_column(sa.Column("tenant_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key("fk_social_engagements_tenant_id", "tenants", ["tenant_id"], ["id"])
        batch_op.create_index("ix_social_engagements_tenant_id", ["tenant_id"])
    op.execute("UPDATE social_engagements SET tenant_id = 1 WHERE tenant_id IS NULL")
    with op.batch_alter_table("social_engagements") as batch_op:
        batch_op.alter_column("tenant_id", nullable=False)


def downgrade() -> None:
    """Remove tenant_id columns (reverse order)."""
    tables = [
        "social_engagements",
        "social_posts",
        "memory_entries",
        "model_calls",
        "agent_runs",
        "tasks",
    ]
    for table in tables:
        with op.batch_alter_table(table) as batch_op:
            batch_op.drop_index(f"ix_{table}_tenant_id")
            batch_op.drop_constraint(f"fk_{table}_tenant_id", type_="foreignkey")
            batch_op.drop_column("tenant_id")
