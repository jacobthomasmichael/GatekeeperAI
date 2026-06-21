"""add passkeys table and make hashed_password nullable

Revision ID: f2a8c1d4e7b5
Revises: e1f3b8d2a5c9
Create Date: 2026-06-20 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'f2a8c1d4e7b5'
down_revision: Union[str, None] = 'e1f3b8d2a5c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('users', 'hashed_password', nullable=True)

    op.create_table(
        'passkeys',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('credential_id', sa.LargeBinary(), nullable=False),
        sa.Column('public_key', sa.LargeBinary(), nullable=False),
        sa.Column('sign_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('device_label', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_passkeys_credential_id', 'passkeys', ['credential_id'], unique=True)
    op.create_index('ix_passkeys_user_id', 'passkeys', ['user_id'])


def downgrade() -> None:
    op.drop_index('ix_passkeys_user_id', table_name='passkeys')
    op.drop_index('ix_passkeys_credential_id', table_name='passkeys')
    op.drop_table('passkeys')
    op.alter_column('users', 'hashed_password', nullable=False)
