"""blue-green app updates

Revision ID: a3f9d1e8b2c0
Revises: 5e46f25b5c13
Create Date: 2026-06-16 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "a3f9d1e8b2c0"
down_revision = "5e46f25b5c13"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # scans: scan_type, previous_scan_id, is_expedited
    op.add_column("scans", sa.Column("scan_type", sa.String(10), nullable=False, server_default="initial"))
    op.add_column("scans", sa.Column("previous_scan_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("scans.id"), nullable=True))
    op.add_column("scans", sa.Column("is_expedited", sa.Boolean(), nullable=False, server_default="false"))

    # app_submissions: stable port + container name for blue-green swaps
    op.add_column("app_submissions", sa.Column("stable_external_port", sa.Integer(), nullable=True))
    op.add_column("app_submissions", sa.Column("stable_container_name", sa.String(100), nullable=True))


def downgrade() -> None:
    op.drop_column("app_submissions", "stable_container_name")
    op.drop_column("app_submissions", "stable_external_port")
    op.drop_column("scans", "is_expedited")
    op.drop_column("scans", "previous_scan_id")
    op.drop_column("scans", "scan_type")
