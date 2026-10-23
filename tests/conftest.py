import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from mediaresearch.models import Base

TEST_DB = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://mr:mr@localhost:5432/mediaresearch_test"
)


@pytest.fixture
def session():
    engine = create_engine(TEST_DB)
    try:
        with engine.connect() as conn:
            conn.execute(text("select 1"))
    except OperationalError:
        pytest.skip(f"Нет тестовой БД ({TEST_DB})")
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s
    engine.dispose()
