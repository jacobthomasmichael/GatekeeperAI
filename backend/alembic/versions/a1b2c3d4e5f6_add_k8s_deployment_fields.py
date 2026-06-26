"""add k8s_namespace and k8s_deployment_name to deployments

Revision ID: a1b2c3d4e5f6
Revises: b3c9e2f1a4d8
Create Date: 2026-06-26 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'b3c9e2f1a4d8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('deployments', sa.Column('k8s_namespace', sa.String(253), nullable=True))
    op.add_column('deployments', sa.Column('k8s_deployment_name', sa.String(253), nullable=True))


def downgrade() -> None:
    op.drop_column('deployments', 'k8s_deployment_name')
    op.drop_column('deployments', 'k8s_namespace')
