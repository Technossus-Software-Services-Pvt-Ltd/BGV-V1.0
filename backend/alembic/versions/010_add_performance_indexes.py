"""Add compound indexes for common query patterns to improve performance.

These indexes cover:
- Document listing with date sort per candidate
- Document filtering by status with date sort
- Best-classification lookups (ORDER BY confidence DESC)
- Best-match validation lookups (ORDER BY ownership_score DESC)
- Batch candidate filtered listing
- Batch log streaming (ORDER BY created_at)
- Processing event timeline (ORDER BY created_at)
- Notification history per candidate

Revision ID: 010_performance_indexes
Revises: 009_parent_document_id
Create Date: 2026-06-09

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "010_performance_indexes"
down_revision: Union[str, None] = "009_parent_document_id"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Documents: listing sorted by date per candidate
    op.create_index(
        "ix_documents_candidate_id_created_at",
        "documents",
        ["candidate_id", "created_at"],
    )

    # Documents: filtering by status with date sort
    op.create_index(
        "ix_documents_processing_status_created_at",
        "documents",
        ["processing_status", "created_at"],
    )

    # AI Classifications: best-classification lookup per document
    op.create_index(
        "ix_ai_classifications_document_id_confidence",
        "ai_classifications",
        ["document_id", "confidence_score"],
    )

    # Validation Results: best-match validation per document
    op.create_index(
        "ix_validation_results_document_id_score",
        "validation_results",
        ["document_id", "ownership_score"],
    )

    # Batch Import Candidates: filtered listing by batch + status
    op.create_index(
        "ix_batch_import_candidates_batch_status",
        "batch_import_candidates",
        ["batch_import_id", "status"],
    )

    # Batch Logs: streaming ordered query
    op.create_index(
        "ix_batch_logs_batch_import_id_created_at",
        "batch_logs",
        ["batch_import_id", "created_at"],
    )

    # Processing Events: timeline query
    op.create_index(
        "ix_processing_events_document_id_created_at",
        "processing_events",
        ["document_id", "created_at"],
    )

    # Notification Logs: history per candidate ordered by date
    op.create_index(
        "ix_notification_logs_candidate_id_created_at",
        "notification_logs",
        ["candidate_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_notification_logs_candidate_id_created_at", table_name="notification_logs")
    op.drop_index("ix_processing_events_document_id_created_at", table_name="processing_events")
    op.drop_index("ix_batch_logs_batch_import_id_created_at", table_name="batch_logs")
    op.drop_index("ix_batch_import_candidates_batch_status", table_name="batch_import_candidates")
    op.drop_index("ix_validation_results_document_id_score", table_name="validation_results")
    op.drop_index("ix_ai_classifications_document_id_confidence", table_name="ai_classifications")
    op.drop_index("ix_documents_processing_status_created_at", table_name="documents")
    op.drop_index("ix_documents_candidate_id_created_at", table_name="documents")
