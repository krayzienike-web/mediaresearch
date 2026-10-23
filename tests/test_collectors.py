import json
from pathlib import Path

from mediaresearch.collectors.google_news import parse_search
from mediaresearch.collectors.rss import parse_feed
from mediaresearch.collectors.telegram import parse_channel, parse_count
from mediaresearch.collectors.vk import group_names_from, post_to_document
from mediaresearch.models import AuthorKind

FIXTURES = Path(__file__).parent / "fixtures"


def test_google_news_strips_source_from_title():
    docs = parse_search((FIXTURES / "google_news.xml").read_bytes())
    assert [d.title for d in docs] == [
        "Сбербанк снизил ставки по ипотеке",
        "Акции Сбера выросли на открытии торгов",
    ]
    assert docs[0].source_name == "РБК"
    assert docs[0].external_id == "CBMiAAA"
    assert docs[0].published_at.hour == 9


def test_rss_strips_html():
    docs = parse_feed((FIXTURES / "rss.xml").read_bytes(), "ТАСС")
    assert len(docs) == 3
    assert docs[0].text == "Ритейлер «Магнит» расширяет присутствие в регионе."
    assert docs[0].published_at.hour == 9  # 12:00 МСК → 09:00 UTC
    assert docs[1].external_id == "https://tass.ru/nauka/1000002"  # без guid берём ссылку


def test_telegram_skips_media_only_posts():
    docs = parse_channel((FIXTURES / "telegram.html").read_text(), "rbc_news")
    assert len(docs) == 1
    d = docs[0]
    assert d.source_name == "РБК"
    assert d.url == "https://t.me/rbc_news/90001"
    assert d.text.startswith("Сбербанк объявил")
    assert d.metrics == {"views": 12_500}


def test_parse_count():
    assert parse_count("800") == 800
    assert parse_count("1.2K") == 1200
    assert parse_count("3M") == 3_000_000
    assert parse_count(None) is None


def test_vk_user_post_keeps_no_profile_data():
    resp = json.loads((FIXTURES / "vk_newsfeed_search.json").read_text())["response"]
    names = group_names_from(resp)
    user_post, group_post = (post_to_document(i, names) for i in resp["items"])

    assert user_post.author_kind == AuthorKind.USER
    assert user_post.author_id == "123456"
    assert user_post.source_name == "ВКонтакте"
    assert "Иван" not in repr(user_post)
    assert user_post.url == "https://vk.com/wall123456_555"

    assert group_post.author_kind == AuthorKind.COMMUNITY
    assert group_post.author_id is None
    assert group_post.source_name == "Банки сегодня"
    assert group_post.metrics == {"views": 25000, "likes": 120, "reposts": 15, "comments": 40}
