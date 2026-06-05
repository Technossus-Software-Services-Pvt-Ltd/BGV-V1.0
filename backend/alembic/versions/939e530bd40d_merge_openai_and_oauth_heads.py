"""merge_openai_and_oauth_heads

Revision ID: 939e530bd40d
Revises: 008_openai_owner_fields, 008_oauth_states
Create Date: 2026-06-05 08:14:49.875926

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '939e530bd40d'
down_revision: Union[str, None] = ('008_openai_owner_fields', '008_oauth_states')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
