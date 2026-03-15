"""move document payloads to object storage references

Revision ID: 0004_document_object_storage
Revises: 0003_users_and_document_owner
Create Date: 2026-03-15
"""

import sqlalchemy as sa
from alembic import op

revision = "0004_document_object_storage"
down_revision = "0003_users_and_document_owner"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("documents") as batch_op:
        batch_op.add_column(sa.Column("source_object_key", sa.String(length=512), nullable=True))

    with op.batch_alter_table("document_results") as batch_op:
        batch_op.alter_column("markdown", existing_type=sa.Text(), nullable=True)
        batch_op.alter_column("canonical_json", existing_type=sa.JSON(), nullable=True)
        batch_op.add_column(sa.Column("markdown_object_key", sa.String(length=512), nullable=True))
        batch_op.add_column(
            sa.Column("canonical_json_object_key", sa.String(length=512), nullable=True)
        )


def downgrade() -> None:
    # Rows created after this migration may store payloads only in object storage,
    # leaving inline columns NULL. Backfill before restoring NOT NULL constraints.
    op.execute(sa.text("UPDATE document_results SET markdown = '' WHERE markdown IS NULL"))
    op.execute(
        sa.text("UPDATE document_results SET canonical_json = '{}' WHERE canonical_json IS NULL")
    )

    with op.batch_alter_table("document_results") as batch_op:
        batch_op.drop_column("canonical_json_object_key")
        batch_op.drop_column("markdown_object_key")
        batch_op.alter_column("canonical_json", existing_type=sa.JSON(), nullable=False)
        batch_op.alter_column("markdown", existing_type=sa.Text(), nullable=False)

    with op.batch_alter_table("documents") as batch_op:
        batch_op.drop_column("source_object_key")
