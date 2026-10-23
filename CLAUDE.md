# mediaresearch

Сервис мониторинга упоминаний брендов (СМИ, Telegram, ВК). Общение и документация — на русском.

- План и этапы: `docs/plan.md`. Решения: `docs/adr/`. Новое архитектурное решение → новый ADR.
- Персональные данные: следуй `docs/adr/0001-personal-data.md`. Никогда не сохраняй имена и профили
  пользователей; ID физлиц — только через `privacy.hash_author`.
- Новый источник = модуль в `src/mediaresearch/collectors/`, отдающий `RawDocument`,
  регистрация в `collectors/__init__.py`, парсер покрыт тестом на фикстуре из `tests/fixtures/`.
- Изменил `models.py` → миграция: `uv run alembic revision --autogenerate -m "..."`, проверь файл.
  `tests/test_migrations.py` упадёт, если модели и миграции разошлись.
- Веб: FastAPI + Jinja2 + htmx (`src/mediaresearch/web/`), выборки — в `web/queries.py`.
  Цвета тональности — CSS-переменные `--s-*` в `app.css`, проверены на дальтонизм; не менять на глаз.
- Проверки: `uv run pytest`, `uv run ruff check .`, `uv run ruff format .`.
