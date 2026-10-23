import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import select, update

from mediaresearch.collectors.rss import parse_feed
from mediaresearch.collectors.vk import group_names_from, post_to_document
from mediaresearch.config import load_brands
from mediaresearch.models import Document, Mention
from mediaresearch.pipeline import content_hash, process, purge_user_texts
from mediaresearch.privacy import hash_author

FIXTURES = Path(__file__).parent / "fixtures"
BRANDS = load_brands()


def vk_docs():
    resp = json.loads((FIXTURES / "vk_newsfeed_search.json").read_text())["response"]
    return [post_to_document(i, group_names_from(resp)) for i in resp["items"]]


def test_stores_only_matched_documents(session):
    docs = parse_feed((FIXTURES / "rss.xml").read_bytes(), "ТАСС")
    stats = process(docs, BRANDS, session)

    # Ритейлер найден; неодимовый магнит отсечён исключением; погода без брендов.
    assert (stats.seen, stats.matched, stats.new_mentions) == (3, 1, 1)
    mention = session.scalars(select(Mention)).one()
    assert mention.brand_slug == "magnit"


def test_reprocessing_updates_metrics_without_duplicates(session):
    docs = vk_docs()
    process(docs, BRANDS, session)
    docs[1].metrics = {**docs[1].metrics, "views": 30000}
    stats = process(docs, BRANDS, session)

    assert stats.new_mentions == 0
    doc = session.scalar(select(Document).where(Document.external_id == "-98765_777"))
    assert doc.metrics["views"] == 30000


def test_user_author_is_hashed(session):
    process(vk_docs(), BRANDS, session)
    user_doc = session.scalar(select(Document).where(Document.author_kind == "user"))
    assert user_doc.author_hash == hash_author("vk", "123456")
    assert "123456" not in user_doc.author_hash


def test_purge_clears_old_user_texts_only(session):
    process(vk_docs(), BRANDS, session)
    session.execute(update(Document).values(collected_at=datetime.now(UTC) - timedelta(days=100)))
    session.commit()

    assert purge_user_texts(session, retention_days=90) == 1
    user_doc, group_doc = (
        session.scalar(select(Document).where(Document.author_kind == k))
        for k in ("user", "community")
    )
    assert user_doc.text is None and user_doc.url  # ссылка остаётся
    assert group_doc.text


def test_content_hash_ignores_punctuation_and_case():
    assert content_hash("Сбер, запустил   СЕРВИС!") == content_hash("сбер запустил сервис")
