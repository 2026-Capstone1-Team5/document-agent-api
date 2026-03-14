"""add file data to documents

Revision ID: 0002_document_file_data
Revises: 0001_documents
Create Date: 2026-03-14
"""

import sqlalchemy as sa
from alembic import op

revision = "0002_document_file_data"
down_revision = "0001_documents"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("documents") as batch_op:
        batch_op.add_column(sa.Column("file_data", sa.LargeBinary(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("documents") as batch_op:
        batch_op.drop_column("file_data")
