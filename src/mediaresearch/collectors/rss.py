"""RSS-ленты СМИ: забираем всю ленту, а бренды ищет pipeline."""

import calendar
import logging
from collections.abc import Iterable
from datetime import UTC, datetime

import feedparser
import httpx
from bs4 import BeautifulSoup

from mediaresearch.collectors.base import RawDocument, http_client
from mediaresearch.models import AuthorKind
from mediaresearch.query import BrandRule

log = logging.getLogger(__name__)


def strip_html(html: str | None) -> str | None:
    if not html:
        return None
    return BeautifulSoup(html, "lxml").get_text(" ", strip=True) or None


def entry_datetime(entry) -> datetime:
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if parsed:
        return datetime.fromtimestamp(calendar.timegm(parsed), UTC)
    return datetime.now(UTC)


def parse_feed(content: bytes, source_name: str, source_type: str = "rss") -> list[RawDocument]:
    feed = feedparser.parse(content)
    docs = []
    for e in feed.entries:
        link = e.get("link")
        if not link:
            continue
        docs.append(
            RawDocument(
                source_type=source_type,
                source_name=source_name,
                external_id=e.get("id") or link,
                url=link,
                published_at=entry_datetime(e),
                author_kind=AuthorKind.MEDIA,
                title=strip_html(e.get("title")),
                text=strip_html(e.get("summary")),
            )
        )
    return docs


class RssCollector:
    name = "rss"

    def __init__(self, feeds: list[dict]):
        self.feeds = feeds

    def collect(self, brands: list[BrandRule]) -> Iterable[RawDocument]:
        with http_client() as client:
            for feed in self.feeds:
                try:
                    resp = client.get(feed["url"])
                    resp.raise_for_status()
                except httpx.HTTPError as e:
                    log.warning("RSS %s: %s", feed["name"], e)
                    continue
                yield from parse_feed(resp.content, feed["name"])
