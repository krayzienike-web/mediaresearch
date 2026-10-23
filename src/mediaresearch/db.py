from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from mediaresearch.config import settings
from mediaresearch.models import Base


def make_engine(url: str | None = None):
    return create_engine(url or settings.database_url, pool_pre_ping=True)


def make_session_factory(url: str | None = None) -> sessionmaker[Session]:
    return sessionmaker(make_engine(url), expire_on_commit=False)


def init_db(url: str | None = None) -> None:
    # Для MVP хватает create_all. Alembic подключим, когда схема начнёт меняться на живых данных.
    Base.metadata.create_all(make_engine(url))
