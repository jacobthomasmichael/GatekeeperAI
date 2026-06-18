"""add visibility to app_submissions

Revision ID: c7d2a4f1e9b3
Revises: a3f9d1e8b2c0
Create Date: 2026-06-18 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "c7d2a4f1e9b3"
down_revision = "a3f9d1e8b2c0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "app_submissions",
        sa.Column("visibility", sa.String(10), nullable=False, server_default="private"),
    )
    op.add_column(
        "app_submissions",
        sa.Column("public_flagged_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("app_submissions", "public_flagged_at")
    op.drop_column("app_submissions", "visibility")
