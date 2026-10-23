"""Выборки для веб-интерфейса. Отделены от FastAPI, чтобы их было легко тестировать."""

from dataclasses import dataclass, fields
from datetime import date, datetime, time, timedelta
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from sqlalchemy import Select, and_, func, select
from sqlalchemy.orm import Session

from mediaresearch.config import settings
from mediaresearch.models import Document, Mention, Sentiment

TZ = ZoneInfo(settings.timezone)
UNRATED = "unrated"


@dataclass
class Filters:
    brand: str = ""
    source: str = ""
    sentiment: str = ""  # positive | neutral | negative | unrated | ""
    q: str = ""
    date_from: date | None = None
    date_to: date | None = None
    show_irrelevant: bool = False

    @classmethod
    def default_period(cls, days: int = 30, **kw) -> "Filters":
        today = datetime.now(TZ).date()
        return cls(date_from=today - timedelta(days=days - 1), date_to=today, **kw)

    def query_string(self, **override) -> str:
        """Параметры фильтра для ссылок (пагинация, экспорт)."""
        params = {f.name: getattr(self, f.name) for f in fields(self)} | override
        return urlencode(
            {k: ("1" if v is True else v) for k, v in params.items() if v not in ("", None, False)}
        )


def _apply(stmt: Select, f: Filters) -> Select:
    conds = []
    if f.brand:
        conds.append(Mention.brand_slug == f.brand)
    if f.source:
        conds.append(Document.source_type == f.source)
    if f.sentiment == UNRATED:
        conds.append(Mention.sentiment.is_(None))
    elif f.sentiment:
        conds.append(Mention.sentiment == f.sentiment)
    if f.q:
        body = func.concat_ws(" ", Document.title, Document.text)
        conds.append(
            func.to_tsvector("russian", body).op("@@")(func.websearch_to_tsquery("russian", f.q))
        )
    if f.date_from:
        conds.append(Document.published_at >= datetime.combine(f.date_from, time.min, TZ))
    if f.date_to:
        conds.append(
            Document.published_at < datetime.combine(f.date_to + timedelta(days=1), time.min, TZ)
        )
    if not f.show_irrelevant:
        conds.append(Mention.is_relevant.is_(True))
    return stmt.where(and_(*conds)) if conds else stmt


def mentions_page(
    session: Session, f: Filters, page: int = 1, per_page: int = 50
) -> tuple[list[tuple[Mention, Document]], int]:
    base = _apply(select(Mention, Document).join(Document), f)
    total = session.scalar(select(func.count()).select_from(base.subquery()))
    rows = session.execute(
        base.order_by(Document.published_at.desc(), Mention.id.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    ).all()
    return [tuple(r) for r in rows], total or 0


def all_mentions(session: Session, f: Filters, limit: int = 50_000):
    stmt = _apply(select(Mention, Document).join(Document), f)
    return session.execute(stmt.order_by(Document.published_at.desc()).limit(limit)).all()


def _sentiment_counts():
    """Колонки: всего и по каждой тональности."""
    cols = [func.count().label("total")]
    for s in Sentiment.ALL:
        cols.append(func.count().filter(Mention.sentiment == s).label(s))
    cols.append(func.count().filter(Mention.sentiment.is_(None)).label(UNRATED))
    return cols


@dataclass
class Dashboard:
    totals: dict
    days: list[dict]
    sources: list[dict]
    brands: list[dict]


def dashboard(session: Session, f: Filters) -> Dashboard:
    base = select(*_sentiment_counts()).select_from(Mention).join(Document)

    totals = session.execute(_apply(base, f)).mappings().one()

    day = func.date(func.timezone(settings.timezone, Document.published_at)).label("day")
    by_day = {
        r["day"]: dict(r)
        for r in session.execute(_apply(base.add_columns(day).group_by(day), f)).mappings()
    }
    days = []
    if f.date_from and f.date_to:
        d = f.date_from
        while d <= f.date_to:
            row = by_day.get(d, {})
            days.append({"day": d, **{k: row.get(k, 0) for k in totals}})
            d += timedelta(days=1)
    else:
        days = [by_day[k] for k in sorted(by_day)]

    src = (Document.source_type, Document.source_name)
    sources = session.execute(
        _apply(base.add_columns(*src).group_by(*src), f).order_by(func.count().desc()).limit(15)
    ).mappings()

    brands = session.execute(
        _apply(base.add_columns(Mention.brand_slug).group_by(Mention.brand_slug), f).order_by(
            func.count().desc()
        )
    ).mappings()

    return Dashboard(
        totals=dict(totals),
        days=days,
        sources=[dict(r) for r in sources],
        brands=[dict(r) for r in brands],
    )


def source_types(session: Session) -> list[str]:
    stmt = select(Document.source_type).distinct().order_by(Document.source_type)
    return list(session.scalars(stmt))


def negative_share(row: dict) -> float | None:
    rated = sum(row.get(s, 0) for s in Sentiment.ALL)
    return row.get(Sentiment.NEGATIVE, 0) / rated if rated else None
