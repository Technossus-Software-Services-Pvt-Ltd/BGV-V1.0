"""add file naming rules table

Revision ID: 006_file_naming_rules
Revises: 005_required_document_checklist
Create Date: 2026-05-30

"""
from alembic import op
import sqlalchemy as sa


revision = "006_file_naming_rules"
down_revision = "005_required_document_checklist"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "file_naming_rules",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("folder_structure_pattern", sa.String(length=255), nullable=False),
        sa.Column("file_rename_pattern", sa.String(length=255), nullable=False),
        sa.Column("example_output", sa.String(length=500), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_file_naming_rules")),
    )
    op.create_index(
        op.f("ix_file_naming_rules_is_active"),
        "file_naming_rules",
        ["is_active"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_file_naming_rules_is_active"), table_name="file_naming_rules")
    op.drop_table("file_naming_rules")
