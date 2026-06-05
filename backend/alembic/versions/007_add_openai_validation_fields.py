"""add openai validation fields

Revision ID: 007_add_openai_validation_fields
Revises: 006_file_naming_rules
Create Date: 2026-06-04

"""
from alembic import op
import sqlalchemy as sa


revision = "007_add_openai_validation_fields"
down_revision = "006_file_naming_rules"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("validation_results", sa.Column("openai_fallback_used", sa.Boolean(), nullable=True))
    op.add_column("validation_results", sa.Column("openai_confidence", sa.Float(), nullable=True))
    op.add_column("validation_results", sa.Column("openai_reasoning", sa.Text(), nullable=True))
    op.add_column("validation_results", sa.Column("openai_model_used", sa.String(100), nullable=True))
    op.add_column("validation_results", sa.Column("openai_prompt_tokens", sa.Integer(), nullable=True))
    op.add_column("validation_results", sa.Column("openai_completion_tokens", sa.Integer(), nullable=True))
    op.add_column("validation_results", sa.Column("openai_total_tokens", sa.Integer(), nullable=True))
    op.add_column("validation_results", sa.Column("openai_cost_usd", sa.Float(), nullable=True))
    op.add_column("validation_results", sa.Column("openai_duration_ms", sa.Integer(), nullable=True))
    op.add_column("validation_results", sa.Column("openai_key_evidence_json", sa.Text(), nullable=True))
    op.add_column("validation_results", sa.Column("openai_concerns_json", sa.Text(), nullable=True))
    op.add_column("validation_results", sa.Column("openai_error", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("validation_results", "openai_fallback_used")
    op.drop_column("validation_results", "openai_confidence")
    op.drop_column("validation_results", "openai_reasoning")
    op.drop_column("validation_results", "openai_model_used")
    op.drop_column("validation_results", "openai_prompt_tokens")
    op.drop_column("validation_results", "openai_completion_tokens")
    op.drop_column("validation_results", "openai_total_tokens")
    op.drop_column("validation_results", "openai_cost_usd")
    op.drop_column("validation_results", "openai_duration_ms")
    op.drop_column("validation_results", "openai_key_evidence_json")
    op.drop_column("validation_results", "openai_concerns_json")
    op.drop_column("validation_results", "openai_error")
