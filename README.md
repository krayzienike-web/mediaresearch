# mediaresearch

Мониторинг упоминаний брендов в СМИ и соцсетях для внутренней PR-службы.
Ориентиры — Медиалогия и СКАН, но под одну компанию (~20 брендов).

**Сейчас умеет:**
- собирать публикации из Google News (поиск), RSS-лент СМИ, публичных Telegram-каналов
  и ВКонтакте (поиск и стены сообществ);
- находить упоминания брендов с учётом русской морфологии и исключений;
- оценивать тональность локальной моделью (без внешних API);
- веб-интерфейс: лента с фильтрами и ручной правкой тональности, дашборд, выгрузка в Excel;
- хранить всё в PostgreSQL без персональных данных авторов.

## Быстрый старт

**Подробная инструкция для новичков: [docs/getting-started.md](docs/getting-started.md).**

Кратко (нужны [uv](https://docs.astral.sh/uv/) и Docker):

```bash
cp .env.example .env          # впишите AUTHOR_HASH_SALT
docker compose up -d          # PostgreSQL
uv sync                       # без модели тональности: uv sync --no-group ml
uv run mr init-db             # таблицы и миграции
uv run mr collect             # сбор + тональность
uv run mr web                 # http://localhost:8000
```

Сбор по расписанию: `uv run mr collect --every 15`. Все команды: `uv run mr --help`.

## Настройка

- `config/brands.yaml` — бренды, поисковые строки и правила сопоставления (синтаксис описан в файле).
- `config/sources.yaml` — RSS-ленты, Telegram-каналы, сообщества ВК.
- `.env` — БД, соль для хэширования, токены ВК ([как получить](docs/vk-token.md)), пароль веб-интерфейса.

## Разработка

```bash
docker compose exec postgres createdb -U mr mediaresearch_test   # БД для тестов (один раз)
uv run pytest
uv run ruff check . && uv run ruff format .
uv run mr web --reload        # интерфейс с перезапуском при правках
uv run alembic revision --autogenerate -m "что изменилось"   # после правки models.py
```

## Документация

- [Запуск с нуля](docs/getting-started.md)
- [План проекта](docs/plan.md)
- [ADR 0001 — персональные данные](docs/adr/0001-personal-data.md)
- [ADR 0002 — стек](docs/adr/0002-stack.md)
- [ADR 0003 — тональность](docs/adr/0003-sentiment.md)
- [Токены ВКонтакте](docs/vk-token.md)
