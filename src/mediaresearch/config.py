from pathlib import Path

import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict

from mediaresearch.query import BrandRule

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    database_url: str = "postgresql+psycopg://mr:mr@localhost:5432/mediaresearch"
    # Соль для хэширования ID авторов-физлиц (см. docs/adr/0001-personal-data.md).
    # Обязательно поменяйте и не теряйте: при смене соли хэши перестанут совпадать.
    author_hash_salt: str = "change-me"
    # Через сколько дней стираем тексты постов пользователей (остаются ссылка и метрики).
    user_text_retention_days: int = 90

    vk_user_token: str = ""
    vk_service_token: str = ""
    vk_api_version: str = "5.199"

    # Часовой пояс для отображения дат и разбивки по дням.
    timezone: str = "Europe/Moscow"

    sentiment_model: str = "cointegrated/rubert-tiny-sentiment-balanced"

    # Если задан пароль, веб-интерфейс спрашивает логин и пароль (нужно на сервере).
    web_username: str = "admin"
    web_password: str = ""

    http_timeout: float = 20.0
    user_agent: str = "Mozilla/5.0 (compatible; mediaresearch/0.1)"

    brands_file: Path = ROOT / "config" / "brands.yaml"
    sources_file: Path = ROOT / "config" / "sources.yaml"


settings = Settings()


def load_yaml(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_brands(path: Path | None = None) -> list[BrandRule]:
    data = load_yaml(path or settings.brands_file)
    return [BrandRule.from_config(b) for b in data.get("brands", [])]


def load_sources(path: Path | None = None) -> dict:
    return load_yaml(path or settings.sources_file)
