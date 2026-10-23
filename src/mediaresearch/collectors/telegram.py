"""Публичные Telegram-каналы через веб-превью t.me/s/<канал>: без аккаунта и ключей.

Превью отдаёт около 20 последних постов. Для частого опроса этого достаточно.
Глубокую историю и комментарии позже будем брать через MTProto (Telethon).
"""

import logging
from collections.abc import Iterable
from datetime import UTC, datetime

import httpx
from bs4 import BeautifulSoup

from mediaresearch.collectors.base import RawDocument, http_client
from mediaresearch.models import AuthorKind
from mediaresearch.query import BrandRule

log = logging.getLogger(__name__)


def parse_count(raw: str | None) -> int | None:
    """«1.2K» → 1200, «3M» → 3000000."""
    if not raw:
        return None
    raw = raw.strip().upper().replace(",", ".")
    mult = {"K": 1_000, "M": 1_000_000}.get(raw[-1:], 1)
    try:
        return int(float(raw.rstrip("KM")) * mult)
    except ValueError:
        return None


def parse_channel(html: str, channel: str) -> list[RawDocument]:
    soup = BeautifulSoup(html, "lxml")
    title_el = soup.select_one(".tgme_channel_info_header_title")
    source_name = title_el.get_text(strip=True) if title_el else channel
    docs = []
    for msg in soup.select(".tgme_widget_message[data-post]"):
        text_el = msg.select_one(".tgme_widget_message_text")
        time_el = msg.select_one(".tgme_widget_message_date time[datetime]")
        if not text_el or not time_el:
            continue  # пост без текста (только медиа) нам не интересен
        post = msg["data-post"]
        views = msg.select_one(".tgme_widget_message_views")
        docs.append(
            RawDocument(
                source_type="telegram",
                source_name=source_name,
                external_id=post,
                url=f"https://t.me/{post}",
                published_at=datetime.fromisoformat(time_el["datetime"]).astimezone(UTC),
                author_kind=AuthorKind.CHANNEL,
                text=text_el.get_text("\n", strip=True),
                metrics={"views": parse_count(views.get_text() if views else None)},
            )
        )
    return docs


class TelegramCollector:
    name = "telegram"

    def __init__(self, channels: list[str]):
        self.channels = channels

    def collect(self, brands: list[BrandRule]) -> Iterable[RawDocument]:
        with http_client() as client:
            for ch in self.channels:
                try:
                    resp = client.get(f"https://t.me/s/{ch}")
                    resp.raise_for_status()
                except httpx.HTTPError as e:
                    log.warning("Telegram %s: %s", ch, e)
                    continue
                yield from parse_channel(resp.text, ch)
