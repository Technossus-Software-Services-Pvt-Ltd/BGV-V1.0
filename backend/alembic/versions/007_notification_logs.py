"""add notification logs table

Revision ID: 007_notification_logs
Revises: 006_file_naming_rules
Create Date: 2026-05-31

"""
from alembic import op
import sqlalchemy as sa


revision = "007_notification_logs"
down_revision = "006_file_naming_rules"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notification_logs",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("candidate_id", sa.String(36), nullable=False),
        sa.Column("recipient_email", sa.String(255), nullable=False),
        sa.Column("subject", sa.String(500), nullable=False),
        sa.Column("body_html", sa.Text(), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="queued"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notification_logs")),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["batch_import_candidates.id"],
            name=op.f("fk_notification_logs_candidate_id"),
        ),
    )
    op.create_index(
        op.f("ix_notification_logs_candidate_id"),
        "notification_logs",
        ["candidate_id"],
    )
    op.create_index(
        op.f("ix_notification_logs_status"),
        "notification_logs",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_notification_logs_status"), table_name="notification_logs")
    op.drop_index(op.f("ix_notification_logs_candidate_id"), table_name="notification_logs")
    op.drop_table("notification_logs")
