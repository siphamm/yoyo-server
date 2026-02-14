"""add user_trips table

Revision ID: 3aedffe93b0f
Revises: aaf26d6d6209
Create Date: 2026-02-15 02:43:04.352280

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3aedffe93b0f'
down_revision: Union[str, Sequence[str], None] = 'aaf26d6d6209'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'user_trips',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('trip_id', sa.Integer(), sa.ForeignKey('trips.id', ondelete='CASCADE'), nullable=False),
        sa.Column('last_visited_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('user_id', 'trip_id'),
    )


def downgrade() -> None:
    op.drop_table('user_trips')
