"""Поиск Google News через RSS: ключи не нужны.

Работает так же, как поиск ВК, — от запросов бренда, поэтому хорошо подходит,
чтобы обкатать «поисковую» ветку сбора до получения токена ВК.
"""

import logging
from collections.abc import Iterable
from urllib.parse import quote_plus

import feedparser
import httpx

from mediaresearch.collectors.base import RawDocument, http_client
from mediaresearch.collectors.rss import entry_datetime, strip_html
from mediaresearch.models import AuthorKind
from mediaresearch.query import BrandRule

log = logging.getLogger(__name__)

SEARCH_URL = "https://news.google.com/rss/search?q={q}&hl=ru&gl=RU&ceid=RU:ru"


def parse_search(content: bytes) -> list[RawDocument]:
    docs = []
    for e in feedparser.parse(content).entries:
        source = e.get("source", {}).get("title") or "Google News"
        title = strip_html(e.get("title")) or ""
        # Google дописывает издание в конец заголовка: «Заголовок - РБК».
        suffix = f" - {source}"
        if title.endswith(suffix):
            title = title[: -len(suffix)]
        docs.append(
            RawDocument(
                source_type="google_news",
                source_name=source,
                external_id=e.get("id") or e.link,
                # Ссылка ведёт на редирект Google, а не на сайт издания. Для MVP этого хватает.
                url=e.link,
                published_at=entry_datetime(e),
                author_kind=AuthorKind.MEDIA,
                title=title,
            )
        )
    return docs


class GoogleNewsCollector:
    name = "google_news"

    def collect(self, brands: list[BrandRule]) -> Iterable[RawDocument]:
        with http_client() as client:
            for brand in brands:
                for q in brand.search:
                    # when:1d — только за последние сутки, чтобы не тянуть архив.
                    url = SEARCH_URL.format(q=quote_plus(f"{q} when:1d"))
                    try:
                        resp = client.get(url)
                        resp.raise_for_status()
                    except httpx.HTTPError as e:
                        log.warning("Google News %r: %s", q, e)
                        continue
                    yield from parse_search(resp.content)
