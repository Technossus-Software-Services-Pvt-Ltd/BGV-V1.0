"""Add composite unique constraint on document_pages and soft delete on documents

Revision ID: 012_db_integrity_fixes
Revises: 011_add_file_hash_dedup
Create Date: 2026-06-09
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "012_db_integrity_fixes"
down_revision = "011_add_file_hash_dedup"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Composite unique constraint: prevents duplicate page records
    op.create_unique_constraint(
        "uq_document_pages_document_id_page_number",
        "document_pages",
        ["document_id", "page_number"],
    )

    # 2. Soft delete column on documents
    op.add_column(
        "documents",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_documents_deleted_at",
        "documents",
        ["deleted_at"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_documents_deleted_at", table_name="documents")
    op.drop_column("documents", "deleted_at")
    op.drop_constraint(
        "uq_document_pages_document_id_page_number",
        "document_pages",
        type_="unique",
    )
