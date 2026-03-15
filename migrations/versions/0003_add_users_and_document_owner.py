"""add users table and document owner

Revision ID: 0003_users_and_document_owner
Revises: 0002_document_file_data
Create Date: 2026-03-14
"""

import sqlalchemy as sa
from alembic import op

revision = "0003_users_and_document_owner"
down_revision = "0002_document_file_data"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    with op.batch_alter_table("documents") as batch_op:
        batch_op.add_column(sa.Column("owner_user_id", sa.String(length=36), nullable=True))
        batch_op.create_index("ix_documents_owner_user_id", ["owner_user_id"], unique=False)
        batch_op.create_foreign_key(
            "fk_documents_owner_user_id_users",
            "users",
            ["owner_user_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("documents") as batch_op:
        batch_op.drop_constraint("fk_documents_owner_user_id_users", type_="foreignkey")
        batch_op.drop_index("ix_documents_owner_user_id")
        batch_op.drop_column("owner_user_id")

    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
