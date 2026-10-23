import pytest

from mediaresearch.query import BrandRule


@pytest.fixture
def sber():
    return BrandRule.from_config(
        {
            "slug": "sber",
            "match": {
                "include": ["сбербанк", "сбер онлайн", "sber*"],
                "exclude": ["сбербанк россии ветеран"],
            },
        }
    )


@pytest.mark.parametrize(
    "text",
    [
        "Клиенты Сбербанка пожаловались на сбой",
        "В СБЕРБАНКЕ ответили на вопросы",
        "Приложение Сбер Онлайн обновилось",
        "Компания SberDevices представила колонку",
    ],
)
def test_include(sber, text):
    assert sber.match(text)


@pytest.mark.parametrize(
    "text",
    [
        "Как копить сбережения",
        "Сбер и онлайн-кинотеатр",  # фраза должна идти подряд
        "Ветераны Сбербанка России ветеран года",  # сработало исключение
    ],
)
def test_no_match(sber, text):
    assert not sber.match(text)


def test_returns_matched_expressions(sber):
    assert sber.match("Сбербанк и Сбер Онлайн") == ["сбербанк", "сбер онлайн"]


def test_yo_normalized():
    rule = BrandRule.from_config({"slug": "x", "match": {"include": ["ёлка"]}})
    assert rule.match("Новогодняя елка у офиса")


def test_empty_include_rejected():
    with pytest.raises(ValueError):
        BrandRule.from_config({"slug": "x", "match": {}})
