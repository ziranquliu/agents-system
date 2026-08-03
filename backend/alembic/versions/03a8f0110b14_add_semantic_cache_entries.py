"""add semantic_cache_entries table

Revision ID: 03a8f0110b14
Revises: 03a8f0110b13
Create Date: 2026-08-03
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "03a8f0110b14"
down_revision: Union[str, None] = "03a8f0110b13"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "semantic_cache_entries",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("query_text", sa.Text(), nullable=False),
        sa.Column("query_embedding", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=True),
        sa.Column(
            "threshold", sa.Float(), nullable=False, server_default="0.92"
        ),
        sa.Column(
            "ttl_seconds", sa.Integer(), nullable=False, server_default="3600"
        ),
        sa.Column("hit_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("semantic_cache_entries")