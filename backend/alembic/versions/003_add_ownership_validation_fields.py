"""Add ownership validation fields: candidate dob/gender, classification extracted_gender, validation_results new columns

Revision ID: 003_ownership_fields
Revises: 002_remove_pii
Create Date: 2026-05-30

"""
from alembic import op
import sqlalchemy as sa

revision = "003_ownership_fields"
down_revision = "002_remove_pii"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # candidates: add dob and gender
    op.add_column("candidates", sa.Column("dob", sa.String(20), nullable=True))
    op.add_column("candidates", sa.Column("gender", sa.String(20), nullable=True))

    # ai_classifications: add extracted_gender
    op.add_column("ai_classifications", sa.Column("extracted_gender", sa.String(20), nullable=True))

    # validation_results: add new scoring/matching columns
    op.add_column("validation_results", sa.Column("ownership_score", sa.Float(), nullable=True))
    op.add_column("validation_results", sa.Column("confidence", sa.String(20), nullable=True))
    op.add_column("validation_results", sa.Column("name_match_level", sa.String(20), nullable=True))
    op.add_column("validation_results", sa.Column("name_matched_tokens", sa.Float(), nullable=True))
    op.add_column("validation_results", sa.Column("name_total_tokens", sa.Float(), nullable=True))
    op.add_column("validation_results", sa.Column("dob_partial", sa.Boolean(), nullable=True))
    op.add_column("validation_results", sa.Column("gender_match", sa.Boolean(), nullable=True))
    op.add_column("validation_results", sa.Column("multi_person_detected", sa.Boolean(), server_default="false"))
    op.add_column("validation_results", sa.Column("requires_manual_review", sa.Boolean(), server_default="false"))
    op.add_column("validation_results", sa.Column("manual_review_reasons_json", sa.Text(), nullable=True))


def downgrade() -> None:
    # validation_results
    op.drop_column("validation_results", "manual_review_reasons_json")
    op.drop_column("validation_results", "requires_manual_review")
    op.drop_column("validation_results", "multi_person_detected")
    op.drop_column("validation_results", "gender_match")
    op.drop_column("validation_results", "dob_partial")
    op.drop_column("validation_results", "name_total_tokens")
    op.drop_column("validation_results", "name_matched_tokens")
    op.drop_column("validation_results", "name_match_level")
    op.drop_column("validation_results", "confidence")
    op.drop_column("validation_results", "ownership_score")

    # ai_classifications
    op.drop_column("ai_classifications", "extracted_gender")

    # candidates
    op.drop_column("candidates", "gender")
    op.drop_column("candidates", "dob")
