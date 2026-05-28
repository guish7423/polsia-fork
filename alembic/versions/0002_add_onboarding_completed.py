"""Add onboarding_completed column to subscriptions"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "subscriptions",
        sa.Column("onboarding_completed", sa.Boolean(), server_default="false"),
    )


def downgrade() -> None:
    op.drop_column("subscriptions", "onboarding_completed")
