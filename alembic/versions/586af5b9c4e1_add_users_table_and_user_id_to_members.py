"""add users table and user_id to members

Revision ID: 586af5b9c4e1
Revises: 0f79bcd1dcec
Create Date: 2026-02-12 01:11:07.488588

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '586af5b9c4e1'
down_revision: Union[str, Sequence[str], None] = '0f79bcd1dcec'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id VARCHAR NOT NULL PRIMARY KEY,
            ctk VARCHAR NOT NULL UNIQUE,
            name VARCHAR(255),
            email VARCHAR(255),
            created_at TIMESTAMP NOT NULL
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_users_ctk ON users (ctk)")

    op.execute("ALTER TABLE members ADD COLUMN IF NOT EXISTS user_id VARCHAR")
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE members ADD CONSTRAINT members_user_id_fkey
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL;
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$
    """)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('members_user_id_fkey', 'members', type_='foreignkey')
    op.drop_column('members', 'user_id')
    op.drop_table('users')
