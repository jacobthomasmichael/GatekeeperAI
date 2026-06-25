"""add sso_configuration table, sso columns on users, allowed_groups on app_submissions

Revision ID: b3c9e2f1a4d8
Revises: f2a8c1d4e7b5
Create Date: 2026-06-25 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, ARRAY

revision: str = 'b3c9e2f1a4d8'
down_revision: Union[str, None] = 'f2a8c1d4e7b5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'sso_configuration',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('provider_name', sa.String(length=100), nullable=False),
        sa.Column('discovery_url', sa.String(length=512), nullable=False),
        sa.Column('client_id', sa.String(length=255), nullable=False),
        sa.Column('encrypted_client_secret', sa.Text(), nullable=False),
        sa.Column('group_claim_key', sa.String(length=100), nullable=False, server_default='groups'),
        sa.Column('default_role', sa.String(length=20), nullable=False, server_default='ic'),
        sa.Column('role_mappings', JSONB(), nullable=True),
        sa.Column('is_enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )

    op.add_column('users', sa.Column('sso_subject', sa.String(length=255), nullable=True))
    op.create_index('ix_users_sso_subject', 'users', ['sso_subject'])
    op.add_column('users', sa.Column('sso_groups', ARRAY(sa.String()), nullable=True))

    op.add_column('app_submissions', sa.Column('allowed_groups', ARRAY(sa.String()), nullable=True))


def downgrade() -> None:
    op.drop_column('app_submissions', 'allowed_groups')
    op.drop_column('users', 'sso_groups')
    op.drop_index('ix_users_sso_subject', table_name='users')
    op.drop_column('users', 'sso_subject')
    op.drop_table('sso_configuration')
