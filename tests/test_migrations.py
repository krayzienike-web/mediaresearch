from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect, text

from mediaresearch.db import init_db
from mediaresearch.models import Base
from tests.conftest import TEST_DB


def test_migrations_match_models(clean_engine):
    init_db(TEST_DB)
    with clean_engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    assert diff == []


def test_upgrades_database_created_before_migrations(clean_engine):
    # Схема как у первой версии (create_all без новых колонок)
    from importlib import import_module

    initial = import_module("migrations.versions.0001_initial")
    from alembic.operations import Operations

    with clean_engine.begin() as conn:
        initial.op = Operations(MigrationContext.configure(conn))
        initial.upgrade()
        conn.execute(
            text(
                "insert into documents (source_type, source_name, external_id, url, author_kind,"
                " published_at, collected_at, metrics, content_hash)"
                " values ('rss', 'x', '1', 'u', 'media', now(), now(), '{}', 'h')"
            )
        )

    init_db(TEST_DB)

    cols = {c["name"] for c in inspect(clean_engine).get_columns("mentions")}
    assert {"sentiment_score", "sentiment_manual", "is_relevant"} <= cols
    with clean_engine.connect() as conn:
        assert conn.scalar(text("select count(*) from documents")) == 1
