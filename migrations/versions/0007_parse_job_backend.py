"""add parser backend to parse jobs

Revision ID: 0007_parse_job_backend
Revises: 0006_create_parse_jobs
Create Date: 2026-03-22
"""

import sqlalchemy as sa
from alembic import op

revision = "0007_parse_job_backend"
down_revision = "0006_create_parse_jobs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "parse_jobs",
        sa.Column(
            "parser_backend",
            sa.String(length=32),
            nullable=False,
            server_default="markitdown",
        ),
    )
    op.alter_column("parse_jobs", "parser_backend", server_default=None)


def downgrade() -> None:
    op.drop_column("parse_jobs", "parser_backend")
