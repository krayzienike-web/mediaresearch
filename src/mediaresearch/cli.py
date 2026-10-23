import logging
import time
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table
from sqlalchemy import func, select

from mediaresearch import pipeline, sentiment
from mediaresearch.collectors import build_collectors
from mediaresearch.config import load_brands, load_sources, settings
from mediaresearch.db import init_db, make_session_factory
from mediaresearch.models import Document, Mention

app = typer.Typer(help="Мониторинг упоминаний брендов", no_args_is_help=True)
console = Console()


@app.callback()
def main(verbose: Annotated[bool, typer.Option("-v", "--verbose")] = False):
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


@app.command("init-db")
def init_db_cmd():
    """Создать или обновить таблицы в БД (миграции)."""
    init_db()
    console.print("[green]Схема БД актуальна[/]")


_analyzer: sentiment.Analyzer | None = None


def _run_sentiment() -> None:
    global _analyzer
    if _analyzer is None:
        _analyzer = sentiment.TransformersAnalyzer()
    started = time.monotonic()
    with make_session_factory()() as session:
        n = sentiment.analyze_pending(session, _analyzer, load_brands())
    console.print(f"[bold]тональность[/]: оценено {n} ({time.monotonic() - started:.1f} с)")


def _collect_once(only: list[str] | None, with_sentiment: bool) -> None:
    brands = load_brands()
    collectors = build_collectors(load_sources())
    if only:
        collectors = {k: v for k, v in collectors.items() if k in only}
    Session = make_session_factory()
    for name, collector in collectors.items():
        started = time.monotonic()
        with Session() as session:
            stats = pipeline.process(collector.collect(brands), brands, session)
        console.print(
            f"[bold]{name}[/]: просмотрено {stats.seen}, с брендами {stats.matched}, "
            f"новых упоминаний {stats.new_mentions} ({time.monotonic() - started:.1f} с)"
        )
    if with_sentiment:
        _run_sentiment()


@app.command()
def collect(
    only: Annotated[
        list[str] | None, typer.Option("--only", help="google_news, rss, telegram, vk")
    ] = None,
    every: Annotated[int, typer.Option(help="Повторять каждые N минут (0 — один раз)")] = 0,
    with_sentiment: Annotated[
        bool, typer.Option("--sentiment/--no-sentiment", help="Сразу оценить тональность")
    ] = True,
):
    """Собрать публикации из включённых источников."""
    if with_sentiment and not sentiment.ml_available():
        console.print("[yellow]Модель тональности не установлена (uv sync), пропускаю оценку[/]")
        with_sentiment = False
    while True:
        _collect_once(only, with_sentiment)
        if not every:
            break
        time.sleep(every * 60)


@app.command()
def mentions(
    brand: Annotated[str | None, typer.Option(help="slug бренда")] = None,
    limit: int = 30,
):
    """Последние упоминания."""
    q = select(Mention, Document).join(Document).order_by(Document.published_at.desc()).limit(limit)
    if brand:
        q = q.where(Mention.brand_slug == brand)
    table = Table("Дата", "Бренд", "Источник", "Текст", "Ссылка")
    with make_session_factory()() as session:
        for m, d in session.execute(q):
            snippet = (d.title or d.text or "—").replace("\n", " ")[:90]
            table.add_row(
                d.published_at.strftime("%d.%m %H:%M"), m.brand_slug, d.source_name, snippet, d.url
            )
    console.print(table)


@app.command()
def stats():
    """Сводка: упоминания по брендам и источникам."""
    q = (
        select(Mention.brand_slug, Document.source_type, func.count())
        .join(Document)
        .group_by(Mention.brand_slug, Document.source_type)
        .order_by(Mention.brand_slug)
    )
    table = Table("Бренд", "Источник", "Упоминаний")
    with make_session_factory()() as session:
        for slug, src, n in session.execute(q):
            table.add_row(slug, src, str(n))
    console.print(table)


@app.command("sentiment")
def sentiment_cmd():
    """Оценить тональность упоминаний, у которых её ещё нет."""
    _run_sentiment()


@app.command()
def web(
    host: Annotated[str, typer.Option(help="0.0.0.0 — доступ из сети")] = "127.0.0.1",
    port: int = 8000,
    reload: Annotated[bool, typer.Option(help="Перезапуск при изменении кода")] = False,
):
    """Запустить веб-интерфейс."""
    import uvicorn

    console.print(f"Откройте http://{'localhost' if host == '127.0.0.1' else host}:{port}")
    uvicorn.run(
        "mediaresearch.web.app:create_app", factory=True, host=host, port=port, reload=reload
    )


@app.command()
def purge():
    """Стереть тексты постов физлиц старше срока хранения."""
    with make_session_factory()() as session:
        n = pipeline.purge_user_texts(session, settings.user_text_retention_days)
    console.print(f"Очищено текстов: {n}")


if __name__ == "__main__":
    app()
