"""index stable_container_name for per-app auth lookup

Revision ID: e1f3b8d2a5c9
Revises: c7d2a4f1e9b3
Create Date: 2026-06-19 00:00:00.000000
"""
from alembic import op

revision = "e1f3b8d2a5c9"
down_revision = "c7d2a4f1e9b3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_app_submissions_stable_container_name",
        "app_submissions",
        ["stable_container_name"],
    )


def downgrade() -> None:
    op.drop_index("ix_app_submissions_stable_container_name", table_name="app_submissions")
