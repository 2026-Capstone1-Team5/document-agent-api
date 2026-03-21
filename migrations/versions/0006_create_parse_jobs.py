"""create parse jobs table

Revision ID: 0006_create_parse_jobs
Revises: 0005_user_api_keys
Create Date: 2026-03-21
"""

import sqlalchemy as sa
from alembic import op

revision = "0006_create_parse_jobs"
down_revision = "0005_user_api_keys"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "parse_jobs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "owner_user_id",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("source_object_key", sa.String(length=512), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column(
            "document_id",
            sa.String(length=36),
            sa.ForeignKey("documents.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_parse_jobs_owner_user_id", "parse_jobs", ["owner_user_id"], unique=False)
    op.create_index("ix_parse_jobs_status", "parse_jobs", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_parse_jobs_status", table_name="parse_jobs")
    op.drop_index("ix_parse_jobs_owner_user_id", table_name="parse_jobs")
    op.drop_table("parse_jobs")

