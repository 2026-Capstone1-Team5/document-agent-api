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
    # This downgrade is intentionally blocked when object-storage-backed rows exist,
    # because restoring inline NOT NULL columns would otherwise lose real payloads.
    bind = op.get_bind()
    object_storage_backed_row_count = bind.execute(
        sa.text(
            """
            SELECT COUNT(*)
            FROM document_results
            WHERE markdown_object_key IS NOT NULL
               OR canonical_json_object_key IS NOT NULL
               OR markdown IS NULL
               OR canonical_json IS NULL
            """
        )
    ).scalar_one()
    if object_storage_backed_row_count > 0:
        raise RuntimeError(
            "Cannot downgrade 0004_document_object_storage while object-storage-backed "
            "rows exist in document_results. Restore inline payloads first."
        )

    with op.batch_alter_table("document_results") as batch_op:
        batch_op.drop_column("canonical_json_object_key")
        batch_op.drop_column("markdown_object_key")
        batch_op.alter_column("canonical_json", existing_type=sa.JSON(), nullable=False)
        batch_op.alter_column("markdown", existing_type=sa.Text(), nullable=False)

    with op.batch_alter_table("documents") as batch_op:
        batch_op.drop_column("source_object_key")
