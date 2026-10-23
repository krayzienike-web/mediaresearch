"""Тональность: уверенность модели, ручная разметка, пометка «мусор»

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("mentions", sa.Column("sentiment_score", sa.Float()))
    op.add_column(
        "mentions",
        sa.Column("sentiment_manual", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column(
        "mentions",
        sa.Column("is_relevant", sa.Boolean(), server_default="true", nullable=False),
    )
    op.create_index("ix_mentions_sentiment", "mentions", ["sentiment"])


def downgrade() -> None:
    op.drop_index("ix_mentions_sentiment", "mentions")
    op.drop_column("mentions", "is_relevant")
    op.drop_column("mentions", "sentiment_manual")
    op.drop_column("mentions", "sentiment_score")
