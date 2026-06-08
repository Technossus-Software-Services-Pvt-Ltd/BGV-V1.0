"""Add parent_document_id to documents table for split document support.

Revision ID: 009_parent_document_id
Revises: 939e530bd40d
Create Date: 2026-06-05

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '009_parent_document_id'
down_revision: Union[str, None] = '939e530bd40d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('documents', sa.Column('parent_document_id', sa.String(36), nullable=True))
    op.create_index('ix_documents_parent_document_id', 'documents', ['parent_document_id'])
    op.create_foreign_key(
        'fk_documents_parent_document_id',
        'documents', 'documents',
        ['parent_document_id'], ['id'],
    )


def downgrade() -> None:
    op.drop_constraint('fk_documents_parent_document_id', 'documents', type_='foreignkey')
    op.drop_index('ix_documents_parent_document_id', table_name='documents')
    op.drop_column('documents', 'parent_document_id')
