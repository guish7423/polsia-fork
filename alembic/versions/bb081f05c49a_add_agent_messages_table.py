"""add agent_messages table

Revision ID: bb081f05c49a
Revises: 0006
Create Date: 2026-06-03 23:35:40.356716

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bb081f05c49a'
down_revision: Union[str, Sequence[str], None] = '0006'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('agent_messages',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('sender_type', sa.String(length=64), nullable=False),
        sa.Column('recipient_type', sa.String(length=64), nullable=True),
        sa.Column('target_message_id', sa.Integer(), nullable=True),
        sa.Column('message_type', sa.String(length=32), nullable=False),
        sa.Column('title', sa.String(length=256), nullable=False),
        sa.Column('body', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('priority', sa.Integer(), nullable=False),
        sa.Column('ttl_seconds', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('delivered_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_agent_messages_tenant_id'), 'agent_messages', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_agent_messages_sender_type'), 'agent_messages', ['sender_type'], unique=False)
    op.create_index(op.f('ix_agent_messages_recipient_type'), 'agent_messages', ['recipient_type'], unique=False)
    op.create_index(op.f('ix_agent_messages_status'), 'agent_messages', ['status'], unique=False)
    op.create_index(op.f('ix_agent_messages_created_at'), 'agent_messages', ['created_at'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_agent_messages_created_at'), table_name='agent_messages')
    op.drop_index(op.f('ix_agent_messages_status'), table_name='agent_messages')
    op.drop_index(op.f('ix_agent_messages_recipient_type'), table_name='agent_messages')
    op.drop_index(op.f('ix_agent_messages_sender_type'), table_name='agent_messages')
    op.drop_index(op.f('ix_agent_messages_tenant_id'), table_name='agent_messages')
    op.drop_table('agent_messages')
