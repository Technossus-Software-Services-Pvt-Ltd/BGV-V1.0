"""Add batch processing tables: batch_imports, batch_import_candidates, batch_logs, integration_configs

Revision ID: 004_batch_processing
Revises: 003_ownership_fields
Create Date: 2026-05-30

"""
from alembic import op
import sqlalchemy as sa

revision = "004_batch_processing"
down_revision = "003_ownership_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "batch_imports",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("batch_code", sa.String(100), unique=True, nullable=False, index=True),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("stored_filename", sa.String(255), nullable=False),
        sa.Column("file_path", sa.String(500), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, index=True),
        sa.Column("total_candidates", sa.Integer, default=0),
        sa.Column("processed_candidates", sa.Integer, default=0),
        sa.Column("failed_candidates", sa.Integer, default=0),
        sa.Column("skipped_candidates", sa.Integer, default=0),
        sa.Column("total_documents_found", sa.Integer, default=0),
        sa.Column("total_documents_processed", sa.Integer, default=0),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("correlation_id", sa.String(36), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "batch_import_candidates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("batch_import_id", sa.String(36), sa.ForeignKey("batch_imports.id"), nullable=False, index=True),
        sa.Column("candidate_id", sa.String(36), sa.ForeignKey("candidates.id"), nullable=True, index=True),
        sa.Column("row_number", sa.Integer, nullable=False),
        sa.Column("source_candidate_id", sa.String(100), nullable=False),
        sa.Column("source_name", sa.String(255), nullable=False),
        sa.Column("source_email", sa.String(255), nullable=True),
        sa.Column("source_phone", sa.String(50), nullable=True),
        sa.Column("source_dob", sa.String(20), nullable=True),
        sa.Column("source_gender", sa.String(20), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, index=True),
        sa.Column("documents_found", sa.Integer, default=0),
        sa.Column("documents_processed", sa.Integer, default=0),
        sa.Column("documents_failed", sa.Integer, default=0),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("gmail_emails_found", sa.Integer, default=0),
        sa.Column("drive_files_found", sa.Integer, default=0),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "batch_logs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("batch_import_id", sa.String(36), sa.ForeignKey("batch_imports.id"), nullable=False, index=True),
        sa.Column("batch_candidate_id", sa.String(36), sa.ForeignKey("batch_import_candidates.id"), nullable=True, index=True),
        sa.Column("level", sa.String(20), nullable=False),
        sa.Column("stage", sa.String(50), nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("details", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "integration_configs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("provider", sa.String(50), unique=True, nullable=False, index=True),
        sa.Column("is_enabled", sa.Boolean, default=False, nullable=False),
        sa.Column("credentials_json", sa.Text, nullable=True),
        sa.Column("config_json", sa.Text, nullable=True),
        sa.Column("last_validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("batch_logs")
    op.drop_table("batch_import_candidates")
    op.drop_table("batch_imports")
    op.drop_table("integration_configs")
