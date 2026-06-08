"""add oauth_states table

Revision ID: 008
Revises: 007
Create Date: 2026-06-02
"""
from alembic import op
import sqlalchemy as sa

revision = "008_oauth_states"
down_revision = "007_notification_logs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "oauth_states",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("state", sa.String(100), unique=True, nullable=False, index=True),
        sa.Column("redirect_uri", sa.String(500), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("oauth_states")
