from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

import httpx

from mediaresearch.config import settings
from mediaresearch.query import BrandRule


@dataclass
class RawDocument:
    """То, что отдаёт сборщик. Сырой ID автора живёт только в памяти: в БД попадает хэш."""

    source_type: str
    source_name: str
    external_id: str
    url: str
    published_at: datetime
    author_kind: str
    title: str | None = None
    text: str | None = None
    author_id: str | None = None
    metrics: dict = field(default_factory=dict)

    @property
    def full_text(self) -> str:
        return "\n".join(p for p in (self.title, self.text) if p)


class Collector(Protocol):
    name: str

    def collect(self, brands: list[BrandRule]) -> Iterable[RawDocument]: ...


def http_client() -> httpx.Client:
    return httpx.Client(
        timeout=settings.http_timeout,
        headers={"User-Agent": settings.user_agent},
        follow_redirects=True,
    )
