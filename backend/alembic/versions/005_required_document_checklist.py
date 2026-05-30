"""add required document checklist table

Revision ID: 005_required_document_checklist
Revises: 004_batch_processing, 004_auth_users_sessions
Create Date: 2026-05-30

"""
from alembic import op
import sqlalchemy as sa


revision = "005_required_document_checklist"
down_revision = ("004_batch_processing", "004_auth_users_sessions")
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "required_document_rules",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("document_name", sa.String(255), nullable=False),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("is_mandatory", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("accepted_formats_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_required_document_rules")),
    )
    op.create_index(
        op.f("ix_required_document_rules_category"),
        "required_document_rules",
        ["category"],
        unique=False,
    )
    op.create_index(
        op.f("ix_required_document_rules_sort_order"),
        "required_document_rules",
        ["sort_order"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_required_document_rules_sort_order"), table_name="required_document_rules")
    op.drop_index(op.f("ix_required_document_rules_category"), table_name="required_document_rules")
    op.drop_table("required_document_rules")
