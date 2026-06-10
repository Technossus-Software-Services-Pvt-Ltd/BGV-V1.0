"""Add file_hash column for duplicate document detection

Revision ID: 011_add_file_hash_dedup
Revises: 010_add_performance_indexes
Create Date: 2026-06-09
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "011_add_file_hash_dedup"
down_revision = "010_performance_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("file_hash", sa.String(64), nullable=True))
    op.create_index(
        "ix_documents_candidate_file_hash",
        "documents",
        ["candidate_id", "file_hash"],
    )


def downgrade() -> None:
    op.drop_index("ix_documents_candidate_file_hash", table_name="documents")
    op.drop_column("documents", "file_hash")
