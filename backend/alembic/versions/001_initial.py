"""initial schema

Revision ID: 001_initial
Revises:
Create Date: 2024-01-15 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Candidates table
    op.create_table(
        "candidates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("candidate_id", sa.String(100), unique=True, nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("date_of_birth", sa.String(10), nullable=True),
        sa.Column("pan_number", sa.String(10), nullable=True),
        sa.Column("aadhaar_last_four", sa.String(4), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("correlation_id", sa.String(36), nullable=True, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    # Upload batches table
    op.create_table(
        "upload_batches",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("candidate_id", sa.String(36), sa.ForeignKey("candidates.id"), nullable=False, index=True),
        sa.Column("batch_reference", sa.String(100), unique=True, nullable=False, index=True),
        sa.Column("total_files", sa.Integer(), default=0),
        sa.Column("processed_files", sa.Integer(), default=0),
        sa.Column("failed_files", sa.Integer(), default=0),
        sa.Column("processing_status", sa.String(50), nullable=False),
        sa.Column("correlation_id", sa.String(36), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    # Documents table
    op.create_table(
        "documents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("candidate_id", sa.String(36), sa.ForeignKey("candidates.id"), nullable=False, index=True),
        sa.Column("upload_batch_id", sa.String(36), sa.ForeignKey("upload_batches.id"), nullable=False, index=True),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("stored_filename", sa.String(255), unique=True, nullable=False),
        sa.Column("file_path", sa.String(500), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("total_pages", sa.Integer(), default=1),
        sa.Column("processing_status", sa.String(50), nullable=False, index=True),
        sa.Column("is_multi_page", sa.Boolean(), default=False),
        sa.Column("correlation_id", sa.String(36), nullable=False, index=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    # Document pages table
    op.create_table(
        "document_pages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("document_id", sa.String(36), sa.ForeignKey("documents.id"), nullable=False, index=True),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("stored_filename", sa.String(255), nullable=False),
        sa.Column("file_path", sa.String(500), nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("orientation_corrected", sa.Boolean(), default=False),
        sa.Column("processing_status", sa.String(50), nullable=False),
        sa.Column("correlation_id", sa.String(36), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    # OCR results table
    op.create_table(
        "ocr_results",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("document_id", sa.String(36), sa.ForeignKey("documents.id"), nullable=False, index=True),
        sa.Column("page_id", sa.String(36), sa.ForeignKey("document_pages.id"), nullable=True, index=True),
        sa.Column("ocr_engine", sa.String(50), nullable=False),
        sa.Column("extracted_text", sa.Text(), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("word_count", sa.Integer(), default=0),
        sa.Column("language_detected", sa.String(10), nullable=True),
        sa.Column("orientation_angle", sa.Float(), default=0.0),
        sa.Column("processing_duration_ms", sa.Integer(), nullable=True),
        sa.Column("raw_output_json", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("correlation_id", sa.String(36), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    # AI classifications table
    op.create_table(
        "ai_classifications",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("document_id", sa.String(36), sa.ForeignKey("documents.id"), nullable=False, index=True),
        sa.Column("page_id", sa.String(36), sa.ForeignKey("document_pages.id"), nullable=True, index=True),
        sa.Column("document_type", sa.String(50), nullable=False, index=True),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("ai_reasoning", sa.Text(), nullable=True),
        sa.Column("extracted_name", sa.String(255), nullable=True),
        sa.Column("extracted_dob", sa.String(20), nullable=True),
        sa.Column("extracted_id_number", sa.String(100), nullable=True),
        sa.Column("extracted_fields_json", sa.Text(), nullable=True),
        sa.Column("model_used", sa.String(100), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column("processing_duration_ms", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("correlation_id", sa.String(36), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    # Validation results table
    op.create_table(
        "validation_results",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("document_id", sa.String(36), sa.ForeignKey("documents.id"), nullable=False, index=True),
        sa.Column("candidate_id", sa.String(36), sa.ForeignKey("candidates.id"), nullable=False, index=True),
        sa.Column("validation_status", sa.String(50), nullable=False),
        sa.Column("name_match", sa.Boolean(), nullable=True),
        sa.Column("name_match_score", sa.Float(), nullable=True),
        sa.Column("dob_match", sa.Boolean(), nullable=True),
        sa.Column("id_number_match", sa.Boolean(), nullable=True),
        sa.Column("ownership_confirmed", sa.Boolean(), default=False),
        sa.Column("validation_reasoning", sa.Text(), nullable=True),
        sa.Column("mismatches_json", sa.Text(), nullable=True),
        sa.Column("processing_duration_ms", sa.Float(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("correlation_id", sa.String(36), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    # Audit logs table
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("correlation_id", sa.String(36), nullable=False, index=True),
        sa.Column("candidate_id", sa.String(36), nullable=True, index=True),
        sa.Column("document_id", sa.String(36), nullable=True, index=True),
        sa.Column("page_id", sa.String(36), nullable=True),
        sa.Column("action", sa.String(100), nullable=False, index=True),
        sa.Column("log_level", sa.String(20), nullable=False),
        sa.Column("processing_stage", sa.String(100), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("details_json", sa.Text(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("error_details", sa.Text(), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    # Processing events table
    op.create_table(
        "processing_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("correlation_id", sa.String(36), nullable=False, index=True),
        sa.Column("document_id", sa.String(36), nullable=False, index=True),
        sa.Column("page_id", sa.String(36), nullable=True),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("stage", sa.String(100), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("error_details", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("processing_events")
    op.drop_table("audit_logs")
    op.drop_table("validation_results")
    op.drop_table("ai_classifications")
    op.drop_table("ocr_results")
    op.drop_table("document_pages")
    op.drop_table("documents")
    op.drop_table("upload_batches")
    op.drop_table("candidates")
