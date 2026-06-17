"""add ws_tickets table

Revision ID: 013_add_ws_tickets
Revises: 012_db_integrity_fixes
Create Date: 2026-06-11
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '013_add_ws_tickets'
down_revision: Union[str, None] = '012_db_integrity_fixes'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if 'ws_tickets' not in inspector.get_table_names():
        op.create_table(
            'ws_tickets',
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('ticket', sa.String(length=100), nullable=False),
            sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint('id', name=op.f('pk_ws_tickets'))
        )
        op.create_index(op.f('ix_ws_tickets_ticket'), 'ws_tickets', ['ticket'], unique=True)

def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if 'ws_tickets' in inspector.get_table_names():
        op.drop_index(op.f('ix_ws_tickets_ticket'), table_name='ws_tickets')
        op.drop_table('ws_tickets')
