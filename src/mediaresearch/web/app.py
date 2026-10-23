import io
import secrets
from datetime import date
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, sessionmaker

from mediaresearch.config import load_brands, settings
from mediaresearch.db import make_session_factory
from mediaresearch.models import Document, Mention, Sentiment
from mediaresearch.web import queries
from mediaresearch.web.queries import TZ, UNRATED, Filters

HERE = Path(__file__).parent
templates = Jinja2Templates(directory=HERE / "templates")

SENTIMENT_LABELS = {
    Sentiment.NEGATIVE: "Негатив",
    Sentiment.NEUTRAL: "Нейтрально",
    Sentiment.POSITIVE: "Позитив",
    UNRATED: "Без оценки",
}
SOURCE_LABELS = {
    "google_news": "Google Новости",
    "rss": "СМИ (RSS)",
    "telegram": "Telegram",
    "vk": "ВКонтакте",
}

templates.env.globals.update(
    SENTIMENT_LABELS=SENTIMENT_LABELS,
    SOURCE_LABELS=SOURCE_LABELS,
    SENTIMENTS=Sentiment.ALL,
)
templates.env.filters["local"] = lambda dt: dt.astimezone(TZ).strftime("%d.%m.%Y %H:%M")
templates.env.filters["pct"] = lambda v: "—" if v is None else f"{v:.0%}"


def _check_auth(credentials: HTTPBasicCredentials | None) -> None:
    if not settings.web_password:
        return
    ok = credentials is not None and all(
        (
            secrets.compare_digest(credentials.username.encode(), settings.web_username.encode()),
            secrets.compare_digest(credentials.password.encode(), settings.web_password.encode()),
        )
    )
    if not ok:
        raise HTTPException(401, headers={"WWW-Authenticate": "Basic"})


basic = HTTPBasic(auto_error=False)


def auth(credentials: Annotated[HTTPBasicCredentials | None, Depends(basic)]) -> None:
    _check_auth(credentials)


def get_filters(
    brand: str = "",
    source: str = "",
    sentiment: str = "",
    q: str = "",
    date_from: Annotated[date | None, Query()] = None,
    date_to: Annotated[date | None, Query()] = None,
    show_irrelevant: bool = False,
) -> Filters:
    return Filters(brand, source, sentiment, q.strip(), date_from, date_to, show_irrelevant)


def create_app(session_factory: sessionmaker[Session] | None = None) -> FastAPI:
    app = FastAPI(title="mediaresearch", dependencies=[Depends(auth)], docs_url=None)
    app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
    factory = session_factory or make_session_factory()

    def db():
        with factory() as session:
            yield session

    DB = Annotated[Session, Depends(db)]
    F = Annotated[Filters, Depends(get_filters)]

    def context(session: Session, f: Filters, **extra) -> dict:
        return {
            "f": f,
            "brands": {b.slug: b.name for b in load_brands()},
            "source_types": queries.source_types(session),
            **extra,
        }

    @app.get("/", response_class=HTMLResponse)
    def feed(request: Request, session: DB, f: F, page: int = 1):
        rows, total = queries.mentions_page(session, f, page)
        pages = max(1, -(-total // 50))
        return templates.TemplateResponse(
            request,
            "feed.html",
            context(session, f, rows=rows, total=total, page=page, pages=pages),
        )

    @app.get("/dashboard", response_class=HTMLResponse)
    def dashboard(request: Request, session: DB, f: F):
        if not f.date_from and not f.date_to:
            f = Filters.default_period(
                brand=f.brand, source=f.source, show_irrelevant=f.show_irrelevant
            )
        data = queries.dashboard(session, f)
        return templates.TemplateResponse(
            request,
            "dashboard.html",
            context(
                session,
                f,
                d=data,
                chart_days=[{**r, "day": r["day"].isoformat()} for r in data.days],
                negative_share=queries.negative_share,
            ),
        )

    def _mention(session: Session, mention_id: int) -> tuple[Mention, Document]:
        m = session.get(Mention, mention_id)
        if not m:
            raise HTTPException(404)
        return m, m.document

    def _card(request: Request, session: Session, mention_id: int):
        m, d = _mention(session, mention_id)
        brands = {b.slug: b.name for b in load_brands()}
        return templates.TemplateResponse(
            request, "_mention.html", {"m": m, "d": d, "brands": brands}
        )

    @app.post("/mentions/{mention_id}/sentiment", response_class=HTMLResponse)
    def set_sentiment(
        request: Request, session: DB, mention_id: int, sentiment: Annotated[str, Form()]
    ):
        if sentiment not in Sentiment.ALL:
            raise HTTPException(422, "Неизвестная тональность")
        m, _ = _mention(session, mention_id)
        m.sentiment, m.sentiment_manual, m.sentiment_score = sentiment, True, None
        session.commit()
        return _card(request, session, mention_id)

    @app.post("/mentions/{mention_id}/relevance", response_class=HTMLResponse)
    def toggle_relevance(request: Request, session: DB, mention_id: int):
        m, _ = _mention(session, mention_id)
        m.is_relevant = not m.is_relevant
        session.commit()
        return _card(request, session, mention_id)

    @app.get("/export.xlsx")
    def export(session: DB, f: F):
        from openpyxl import Workbook

        brands = {b.slug: b.name for b in load_brands()}
        wb = Workbook()
        ws = wb.active
        ws.title = "Упоминания"
        ws.append(
            [
                "Дата",
                "Бренд",
                "Тип источника",
                "Источник",
                "Заголовок",
                "Текст",
                "Тональность",
                "Просмотры",
                "Лайки",
                "Репосты",
                "Комментарии",
                "Ссылка",
            ]
        )
        for m, d in queries.all_mentions(session, f):
            mt = d.metrics or {}
            ws.append(
                [
                    d.published_at.astimezone(TZ).replace(tzinfo=None),
                    brands.get(m.brand_slug, m.brand_slug),
                    SOURCE_LABELS.get(d.source_type, d.source_type),
                    d.source_name,
                    d.title,
                    d.text,
                    SENTIMENT_LABELS.get(m.sentiment or UNRATED),
                    mt.get("views"),
                    mt.get("likes"),
                    mt.get("reposts"),
                    mt.get("comments"),
                    d.url,
                ]
            )
        for col, width in zip(
            "ABCDEFGHIJKL", (17, 14, 16, 22, 50, 80, 12, 10, 8, 8, 8, 40), strict=True
        ):
            ws.column_dimensions[col].width = width
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        return StreamingResponse(
            buf,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": 'attachment; filename="mentions.xlsx"'},
        )

    return app
