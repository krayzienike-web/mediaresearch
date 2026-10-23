"""Начальная схема: документы и упоминания

Revision ID: 0001
Revises:
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "documents",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("source_type", sa.String(32), nullable=False),
        sa.Column("source_name", sa.String(255), nullable=False),
        sa.Column("external_id", sa.String(512), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("title", sa.Text()),
        sa.Column("text", sa.Text()),
        sa.Column("author_kind", sa.String(16), nullable=False),
        sa.Column("author_hash", sa.String(64)),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metrics", postgresql.JSONB(), nullable=False),
        sa.Column("content_hash", sa.String(40), nullable=False),
        sa.Column("text_purged_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("source_type", "external_id"),
    )
    op.create_index("ix_documents_published_at", "documents", ["published_at"])
    op.create_index("ix_documents_content_hash", "documents", ["content_hash"])

    op.create_table(
        "mentions",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "document_id",
            sa.BigInteger(),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("brand_slug", sa.String(64), nullable=False),
        sa.Column("matched", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("sentiment", sa.String(16)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("document_id", "brand_slug"),
    )
    op.create_index("ix_mentions_brand_slug", "mentions", ["brand_slug"])


def downgrade() -> None:
    op.drop_table("mentions")
    op.drop_table("documents")
