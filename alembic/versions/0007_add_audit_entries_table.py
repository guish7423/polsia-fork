"""add audit_entries table for SHA256 hash-chain audit log

Revision ID: 0007
Revises: bb081f05c49a
Create Date: 2026-06-04
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "bb081f05c49a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "audit_entries",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("entry_type", sa.String(32), nullable=False),
        sa.Column("entry_id", sa.String(64), nullable=False),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("payload", sa.Text(), nullable=True),
        sa.Column("previous_hash", sa.String(64), nullable=False),
        sa.Column("hash", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name="fk_audit_entries_tenant_id"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("hash", name="uq_audit_entries_hash"),
    )
    op.create_index("ix_audit_entries_tenant_id", "audit_entries", ["tenant_id"])
    op.create_index(
        "ix_audit_entries_tenant_type",
        "audit_entries",
        ["tenant_id", "entry_type"],
    )
    op.create_index(
        "ix_audit_entries_created_at",
        "audit_entries",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_table("audit_entries")
