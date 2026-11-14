"""rate limit events (shared rate limiting for serverless deployments)

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rate_limit_events",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_rate_key_created", "rate_limit_events", ["key", "created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_rate_key_created", table_name="rate_limit_events")
    op.drop_table("rate_limit_events")
