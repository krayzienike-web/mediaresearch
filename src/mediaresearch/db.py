from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session, sessionmaker

from mediaresearch.config import ROOT, settings

# Ревизия, соответствующая схеме, которую раньше создавал create_all (до миграций).
PRE_ALEMBIC_REVISION = "0001"


def make_engine(url: str | None = None):
    return create_engine(url or settings.database_url, pool_pre_ping=True)


def make_session_factory(url: str | None = None) -> sessionmaker[Session]:
    return sessionmaker(make_engine(url), expire_on_commit=False)


def alembic_config(url: str | None = None) -> Config:
    cfg = Config(ROOT / "alembic.ini")
    cfg.set_main_option("sqlalchemy.url", url or settings.database_url)
    return cfg


def init_db(url: str | None = None) -> None:
    """Создаёт или обновляет схему до последней миграции."""
    cfg = alembic_config(url)
    tables = set(inspect(make_engine(url)).get_table_names())
    if "documents" in tables and "alembic_version" not in tables:
        # База создана старой версией без миграций: помечаем её как начальную схему.
        command.stamp(cfg, PRE_ALEMBIC_REVISION)
    command.upgrade(cfg, "head")
