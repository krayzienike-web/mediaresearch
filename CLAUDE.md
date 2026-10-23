# mediaresearch

Сервис мониторинга упоминаний брендов (СМИ, Telegram, ВК). Общение и документация — на русском.

- План и этапы: `docs/plan.md`. Решения: `docs/adr/`. Новое архитектурное решение → новый ADR.
- Персональные данные: следуй `docs/adr/0001-personal-data.md`. Никогда не сохраняй имена и профили
  пользователей; ID физлиц — только через `privacy.hash_author`.
- Новый источник = модуль в `src/mediaresearch/collectors/`, отдающий `RawDocument`,
  регистрация в `collectors/__init__.py`, парсер покрыт тестом на фикстуре из `tests/fixtures/`.
- Проверки: `uv run pytest`, `uv run ruff check .`, `uv run ruff format .`.
