import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

from mediaresearch.models import Base

TEST_DB = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://mr:mr@localhost:5432/mediaresearch_test"
)


@pytest.fixture
def clean_engine():
    """Пустая тестовая БД без таблиц."""
    engine = create_engine(TEST_DB)
    try:
        with engine.connect() as conn:
            conn.execute(text("select 1"))
    except OperationalError:
        pytest.skip(f"Нет тестовой БД ({TEST_DB})")
    Base.metadata.drop_all(engine)
    with engine.begin() as conn:
        conn.execute(text("drop table if exists alembic_version"))
    yield engine
    engine.dispose()


@pytest.fixture
def engine(clean_engine):
    Base.metadata.create_all(clean_engine)
    return clean_engine


@pytest.fixture
def session_factory(engine):
    return sessionmaker(engine, expire_on_commit=False)


@pytest.fixture
def session(session_factory):
    with session_factory() as s:
        yield s
