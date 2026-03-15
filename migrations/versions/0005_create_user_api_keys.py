"""create user api keys table

Revision ID: 0005_user_api_keys
Revises: 0004_document_object_storage
Create Date: 2026-03-15
"""

import sqlalchemy as sa
from alembic import op

revision = "0005_user_api_keys"
down_revision = "0004_document_object_storage"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_api_keys",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("key_prefix", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_user_api_keys_user_id", "user_api_keys", ["user_id"], unique=False)
    op.create_index("ix_user_api_keys_key_hash", "user_api_keys", ["key_hash"], unique=True)
    op.create_index(
        "ix_user_api_keys_user_id_name",
        "user_api_keys",
        ["user_id", "name"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_user_api_keys_user_id_name", table_name="user_api_keys")
    op.drop_index("ix_user_api_keys_key_hash", table_name="user_api_keys")
    op.drop_index("ix_user_api_keys_user_id", table_name="user_api_keys")
    op.drop_table("user_api_keys")
