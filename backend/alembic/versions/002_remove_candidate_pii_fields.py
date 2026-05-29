"""Remove date_of_birth, pan_number, aadhaar_last_four from candidates

Revision ID: 002_remove_pii
Revises: 001_initial
Create Date: 2026-05-29

"""
from alembic import op
import sqlalchemy as sa

revision = "002_remove_pii"
down_revision = "001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("candidates", "date_of_birth")
    op.drop_column("candidates", "pan_number")
    op.drop_column("candidates", "aadhaar_last_four")


def downgrade() -> None:
    op.add_column("candidates", sa.Column("aadhaar_last_four", sa.String(4), nullable=True))
    op.add_column("candidates", sa.Column("pan_number", sa.String(10), nullable=True))
    op.add_column("candidates", sa.Column("date_of_birth", sa.String(10), nullable=True))
