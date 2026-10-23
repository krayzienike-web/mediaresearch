"""ВКонтакте через официальный API.

- newsfeed.search — поиск по всем открытым постам. Нужен пользовательский токен.
- wall.get — стены выбранных сообществ. Достаточно сервисного ключа приложения.

Как получить токены: docs/vk-token.md.
"""

import logging
import time
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta

import httpx

from mediaresearch.collectors.base import RawDocument, http_client
from mediaresearch.config import settings
from mediaresearch.models import AuthorKind
from mediaresearch.query import BrandRule

log = logging.getLogger(__name__)

API_URL = "https://api.vk.com/method/"
MIN_INTERVAL = 0.34  # ВК разрешает около 3 запросов в секунду на токен
TOO_MANY_REQUESTS = 6


class VkError(Exception):
    def __init__(self, code: int, message: str):
        super().__init__(f"VK API {code}: {message}")
        self.code = code


class VkApi:
    def __init__(self, token: str, client: httpx.Client):
        self.token = token
        self.client = client
        self._last_call = 0.0

    def call(self, method: str, **params) -> dict:
        for attempt in range(3):
            wait = MIN_INTERVAL - (time.monotonic() - self._last_call)
            if wait > 0:
                time.sleep(wait)
            self._last_call = time.monotonic()
            resp = self.client.post(
                API_URL + method,
                data={**params, "access_token": self.token, "v": settings.vk_api_version},
            )
            resp.raise_for_status()
            body = resp.json()
            if "error" not in body:
                return body["response"]
            err = body["error"]
            if err.get("error_code") == TOO_MANY_REQUESTS and attempt < 2:
                time.sleep(1 + attempt)
                continue
            raise VkError(err.get("error_code", 0), err.get("error_msg", ""))
        raise AssertionError("unreachable")


def post_to_document(item: dict, group_names: dict[int, str]) -> RawDocument:
    owner_id, from_id = item["owner_id"], item.get("from_id", item["owner_id"])
    is_user = from_id > 0

    def count(key):
        return (item.get(key) or {}).get("count")

    return RawDocument(
        source_type="vk",
        source_name=group_names.get(-owner_id, "ВКонтакте") if owner_id < 0 else "ВКонтакте",
        external_id=f"{owner_id}_{item['id']}",
        url=f"https://vk.com/wall{owner_id}_{item['id']}",
        published_at=datetime.fromtimestamp(item["date"], UTC),
        author_kind=AuthorKind.USER if is_user else AuthorKind.COMMUNITY,
        author_id=str(from_id) if is_user else None,
        text=item.get("text") or None,
        metrics={k: count(k) for k in ("views", "likes", "reposts", "comments")},
    )


def group_names_from(response: dict) -> dict[int, str]:
    # Берём только названия сообществ. Профили пользователей не сохраняем.
    return {g["id"]: g["name"] for g in response.get("groups", [])}


class VkCollector:
    name = "vk"

    def __init__(
        self,
        communities: list[str],
        lookback: timedelta = timedelta(days=1),
        max_pages: int = 5,
    ):
        self.communities = communities
        self.lookback = lookback
        self.max_pages = max_pages

    def collect(self, brands: list[BrandRule]) -> Iterable[RawDocument]:
        with http_client() as client:
            if settings.vk_user_token:
                yield from self._search(VkApi(settings.vk_user_token, client), brands)
            else:
                log.warning("VK_USER_TOKEN не задан: поиск ВК пропущен")
            token = settings.vk_service_token or settings.vk_user_token
            if token and self.communities:
                yield from self._walls(VkApi(token, client))

    def _search(self, api: VkApi, brands: list[BrandRule]) -> Iterable[RawDocument]:
        start_time = int((datetime.now(UTC) - self.lookback).timestamp())
        for brand in brands:
            for q in brand.search:
                start_from = None
                for _ in range(self.max_pages):
                    params = {"q": q, "count": 200, "start_time": start_time, "extended": 1}
                    if start_from:
                        params["start_from"] = start_from
                    try:
                        resp = api.call("newsfeed.search", **params)
                    except (VkError, httpx.HTTPError) as e:
                        log.warning("VK search %r: %s", q, e)
                        break
                    names = group_names_from(resp)
                    for item in resp.get("items", []):
                        yield post_to_document(item, names)
                    start_from = resp.get("next_from")
                    if not start_from:
                        break

    def _walls(self, api: VkApi) -> Iterable[RawDocument]:
        for domain in self.communities:
            try:
                resp = api.call("wall.get", domain=domain, count=100, extended=1)
            except (VkError, httpx.HTTPError) as e:
                log.warning("VK wall %s: %s", domain, e)
                continue
            names = group_names_from(resp)
            for item in resp.get("items", []):
                yield post_to_document(item, names)
