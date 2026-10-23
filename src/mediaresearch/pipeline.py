import hashlib
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from mediaresearch.collectors.base import RawDocument
from mediaresearch.models import AuthorKind, Document, Mention
from mediaresearch.privacy import hash_author
from mediaresearch.query import BrandRule, tokenize


@dataclass
class Stats:
    seen: int = 0
    matched: int = 0
    new_mentions: int = 0


def content_hash(text: str) -> str:
    """Перепечатки с другой пунктуацией и регистром дают одинаковый хэш."""
    return hashlib.sha1(" ".join(tokenize(text)).encode()).hexdigest()


def process(docs: Iterable[RawDocument], brands: list[BrandRule], session: Session) -> Stats:
    stats = Stats()
    for raw in docs:
        stats.seen += 1
        full_text = raw.full_text
        hits = {b.slug: m for b in brands if (m := b.match(full_text))}
        if not hits:
            continue
        stats.matched += 1
        doc_id = _upsert_document(session, raw, full_text)
        for slug, matched in hits.items():
            res = session.execute(
                insert(Mention)
                .values(document_id=doc_id, brand_slug=slug, matched=matched)
                .on_conflict_do_nothing()
                .returning(Mention.id)
            )
            if res.scalar() is not None:
                stats.new_mentions += 1
    session.commit()
    return stats


def _upsert_document(session: Session, raw: RawDocument, full_text: str) -> int:
    values = dict(
        source_type=raw.source_type,
        source_name=raw.source_name,
        external_id=raw.external_id,
        url=raw.url,
        title=raw.title,
        text=raw.text,
        author_kind=raw.author_kind,
        author_hash=hash_author(raw.source_type, raw.author_id) if raw.author_id else None,
        published_at=raw.published_at,
        metrics=raw.metrics,
        content_hash=content_hash(full_text),
    )
    stmt = insert(Document).values(**values)
    # При повторной встрече обновляем только счётчики: просмотры и лайки растут.
    stmt = stmt.on_conflict_do_update(
        index_elements=["source_type", "external_id"],
        set_={"metrics": stmt.excluded.metrics},
    ).returning(Document.id)
    return session.execute(stmt).scalar_one()


def purge_user_texts(session: Session, retention_days: int) -> int:
    """Стирает тексты постов физлиц старше срока хранения. Ссылка и метрики остаются."""
    cutoff = datetime.now(UTC) - timedelta(days=retention_days)
    res = session.execute(
        update(Document)
        .where(
            Document.author_kind == AuthorKind.USER,
            Document.collected_at < cutoff,
            Document.text_purged_at.is_(None),
        )
        .values(text=None, title=None, text_purged_at=datetime.now(UTC))
    )
    session.commit()
    return res.rowcount
