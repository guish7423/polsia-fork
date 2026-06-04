"""create mcp_tools, mcp_tool_calls, plugins tables

Revision ID: 0006
Revises: 0005
Create Date: 2026-06-03
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. mcp_tools
    op.create_table(
        "mcp_tools",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), server_default=""),
        sa.Column("endpoint", sa.String(1024), nullable=False),
        sa.Column("schema_json", sa.JSON(), server_default="{}"),
        sa.Column("auth_config", sa.JSON(), nullable=True),
        sa.Column("enabled", sa.Boolean(), server_default="true"),
        sa.Column("cache_ttl_seconds", sa.Integer(), server_default="0"),
        sa.Column("timeout_seconds", sa.Integer(), server_default="30"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name="fk_mcp_tools_tenant_id"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mcp_tools_tenant_id", "mcp_tools", ["tenant_id"])

    # 2. mcp_tool_calls (audit log)
    op.create_table(
        "mcp_tool_calls",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tool_id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("agent_run_id", sa.Integer(), nullable=True),
        sa.Column("input_params", sa.JSON(), server_default="{}"),
        sa.Column("output_summary", sa.Text(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), server_default="0"),
        sa.Column("success", sa.Boolean(), server_default="true"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("cost_usd", sa.Float(), server_default="0.0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tool_id"], ["mcp_tools.id"], name="fk_mcp_tool_calls_tool_id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name="fk_mcp_tool_calls_tenant_id"),
        sa.ForeignKeyConstraint(["agent_run_id"], ["agent_runs.id"], name="fk_mcp_tool_calls_agent_run_id", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mcp_tool_calls_tool_id", "mcp_tool_calls", ["tool_id"])
    op.create_index("ix_mcp_tool_calls_tenant_id", "mcp_tool_calls", ["tenant_id"])

    # 3. plugins
    op.create_table(
        "plugins",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), server_default=""),
        sa.Column("version", sa.String(50), server_default="1.0"),
        sa.Column("webhook_url", sa.String(1024), nullable=False),
        sa.Column("manifest", sa.JSON(), server_default="{}"),
        sa.Column("enabled", sa.Boolean(), server_default="true"),
        sa.Column("config", sa.JSON(), nullable=True),
        sa.Column("last_called_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name="fk_plugins_tenant_id"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_plugins_tenant_id", "plugins", ["tenant_id"])


def downgrade() -> None:
    op.drop_table("plugins")
    op.drop_table("mcp_tool_calls")
    op.drop_table("mcp_tools")
