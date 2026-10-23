# mediaresearch

Мониторинг упоминаний брендов в СМИ и соцсетях для внутренней PR-службы.
Ориентиры — Медиалогия и СКАН, но под одну компанию (~20 брендов).

**Сейчас умеет:** собирать публикации из Google News (поиск), RSS-лент СМИ,
публичных Telegram-каналов и ВКонтакте (поиск и стены сообществ); находить
упоминания брендов с учётом русской морфологии и исключений; хранить их в
PostgreSQL без персональных данных авторов.

## Быстрый старт

Нужны Python 3.12+, [uv](https://docs.astral.sh/uv/) и Docker.

```bash
cp .env.example .env          # впишите AUTHOR_HASH_SALT
docker compose up -d          # PostgreSQL
uv sync
uv run mr init-db
uv run mr collect             # один проход по всем включённым источникам
uv run mr mentions            # последние упоминания
uv run mr stats               # сводка по брендам и источникам
```

Сбор по расписанию: `uv run mr collect --every 15`. Один источник: `--only telegram`.

## Настройка

- `config/brands.yaml` — бренды, поисковые строки и правила сопоставления (синтаксис описан в файле).
- `config/sources.yaml` — RSS-ленты, Telegram-каналы, сообщества ВК.
- `.env` — БД, соль для хэширования, токены ВК ([как получить](docs/vk-token.md)).

## Разработка

```bash
createdb mediaresearch_test   # или TEST_DATABASE_URL=...; без БД тесты pipeline пропускаются
uv run pytest
uv run ruff check . && uv run ruff format .
```

## Документация

- [План проекта](docs/plan.md)
- [ADR 0001 — персональные данные](docs/adr/0001-personal-data.md)
- [ADR 0002 — стек](docs/adr/0002-stack.md)
- [Токены ВКонтакте](docs/vk-token.md)
