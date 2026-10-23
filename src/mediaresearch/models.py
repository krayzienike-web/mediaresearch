from datetime import UTC, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class AuthorKind:
    MEDIA = "media"  # редакция СМИ
    CHANNEL = "channel"  # публичный Telegram-канал
    COMMUNITY = "community"  # сообщество ВК
    USER = "user"  # физлицо: только хэш ID, текст стирается по сроку хранения


class Sentiment:
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    ALL = (NEGATIVE, NEUTRAL, POSITIVE)  # порядок шкалы в интерфейсе


class Document(Base):
    """Публикация из любого источника. Хранится, только если упоминает хотя бы один бренд."""

    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint("source_type", "external_id"),
        Index("ix_documents_published_at", "published_at"),
        Index("ix_documents_content_hash", "content_hash"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    source_type: Mapped[str] = mapped_column(String(32))  # google_news, rss, telegram, vk
    source_name: Mapped[str] = mapped_column(String(255))  # издание, канал или сообщество
    external_id: Mapped[str] = mapped_column(String(512))
    url: Mapped[str] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(Text)
    text: Mapped[str | None] = mapped_column(Text)
    author_kind: Mapped[str] = mapped_column(String(16))
    author_hash: Mapped[str | None] = mapped_column(String(64))
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    # Счётчики на момент последнего сбора: views, likes, reposts, comments.
    metrics: Mapped[dict] = mapped_column(JSONB, default=dict)
    # Хэш нормализованного текста: одинаковые перепечатки получают один хэш.
    content_hash: Mapped[str] = mapped_column(String(40))
    text_purged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    mentions: Mapped[list["Mention"]] = relationship(back_populates="document")


class Mention(Base):
    """Факт упоминания бренда в документе."""

    __tablename__ = "mentions"
    __table_args__ = (UniqueConstraint("document_id", "brand_slug"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    brand_slug: Mapped[str] = mapped_column(String(64), index=True)
    matched: Mapped[list[str]] = mapped_column(ARRAY(Text))
    sentiment: Mapped[str | None] = mapped_column(String(16), index=True)  # см. Sentiment
    sentiment_score: Mapped[float | None] = mapped_column(Float)  # уверенность модели
    # Тональность поправил человек: модель её больше не перезаписывает.
    sentiment_manual: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    # Пометка «мусор» из интерфейса. Скрываем из ленты, но храним: пригодится для обучения.
    is_relevant: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    document: Mapped[Document] = relationship(back_populates="mentions")
