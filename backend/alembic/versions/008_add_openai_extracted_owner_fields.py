"""Add OpenAI extracted owner fields for candidate comparison

Revision ID: 008
Revises: 007
Create Date: 2026-06-04
"""
from alembic import op
import sqlalchemy as sa

revision = "008_openai_owner_fields"
down_revision = "007_add_openai_validation_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("validation_results", sa.Column("openai_extracted_owner_name", sa.String(255), nullable=True))
    op.add_column("validation_results", sa.Column("openai_extracted_owner_dob", sa.String(50), nullable=True))
    op.add_column("validation_results", sa.Column("openai_name_match_score", sa.Float, nullable=True))


def downgrade() -> None:
    op.drop_column("validation_results", "openai_name_match_score")
    op.drop_column("validation_results", "openai_extracted_owner_dob")
    op.drop_column("validation_results", "openai_extracted_owner_name")
