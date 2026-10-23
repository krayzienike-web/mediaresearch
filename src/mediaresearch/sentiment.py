"""Тональность упоминаний.

Оцениваем не весь текст, а предложения, где встречается бренд: в длинной новости
негатив про конкурента не должен окрашивать упоминание нашего бренда.

Модель по умолчанию — cointegrated/rubert-tiny-sentiment-balanced: маленькая (~50 МБ),
работает на CPU, три класса. Ставится отдельно: `uv sync --extra ml`.
"""

import logging
import re
from collections.abc import Sequence
from typing import Protocol

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from mediaresearch.config import settings
from mediaresearch.models import Document, Mention, Sentiment
from mediaresearch.query import BrandRule

log = logging.getLogger(__name__)

_SENTENCE_RE = re.compile(r"(?<=[.!?…])\s+|\n+")
MAX_FRAGMENT_CHARS = 1500


class Analyzer(Protocol):
    def predict(self, texts: Sequence[str]) -> list[tuple[str, float]]:
        """Для каждого текста: (positive|neutral|negative, уверенность 0..1)."""
        ...


def brand_fragment(text: str, brand: BrandRule | None) -> str:
    """Предложения с упоминанием бренда. Не нашли или бренда нет в конфиге — начало текста."""
    if brand:
        hits = [s for s in _SENTENCE_RE.split(text) if s.strip() and brand.match(s)]
        if hits:
            return " ".join(hits)[:MAX_FRAGMENT_CHARS]
    return text[:MAX_FRAGMENT_CHARS]


def normalize_label(label: str) -> str:
    low = label.lower()
    for value in (Sentiment.NEGATIVE, Sentiment.NEUTRAL, Sentiment.POSITIVE):
        if low.startswith(value[:3]):
            return value
    raise ValueError(f"Модель вернула неизвестный класс {label!r}")


class TransformersAnalyzer:
    def __init__(self, model_name: str | None = None, batch_size: int = 32):
        try:
            import torch
            from transformers import AutoModelForSequenceClassification, AutoTokenizer
        except ImportError as e:
            raise RuntimeError(
                "Модель тональности не установлена. Выполните: uv sync --extra ml"
            ) from e
        name = model_name or settings.sentiment_model
        log.info("Загружаю модель тональности %s", name)
        self.torch = torch
        self.tokenizer = AutoTokenizer.from_pretrained(name)
        self.model = AutoModelForSequenceClassification.from_pretrained(name).eval()
        self.labels = {i: normalize_label(label) for i, label in self.model.config.id2label.items()}
        self.batch_size = batch_size

    def predict(self, texts: Sequence[str]) -> list[tuple[str, float]]:
        out: list[tuple[str, float]] = []
        for i in range(0, len(texts), self.batch_size):
            batch = list(texts[i : i + self.batch_size])
            enc = self.tokenizer(
                batch, padding=True, truncation=True, max_length=512, return_tensors="pt"
            )
            with self.torch.no_grad():
                probs = self.torch.softmax(self.model(**enc).logits, dim=-1)
            scores, idx = probs.max(dim=-1)
            out.extend(
                (self.labels[j], round(s, 4))
                for j, s in zip(idx.tolist(), scores.tolist(), strict=True)
            )
        return out


def ml_available() -> bool:
    try:
        import torch  # noqa: F401
        import transformers  # noqa: F401
    except ImportError:
        return False
    return True


def analyze_pending(
    session: Session, analyzer: Analyzer, brands: list[BrandRule], batch: int = 256
) -> int:
    """Проставляет тональность упоминаниям без неё. Ручную разметку не трогает."""
    by_slug = {b.slug: b for b in brands}
    body = func.concat_ws("\n", Document.title, Document.text)
    done = 0
    last_id = 0
    while True:
        rows = session.execute(
            select(Mention, body)
            .join(Document)
            .where(
                Mention.sentiment.is_(None),
                Mention.id > last_id,
                func.coalesce(Document.text, Document.title).is_not(None),
            )
            .order_by(Mention.id)
            .limit(batch)
        ).all()
        if not rows:
            return done
        texts = [brand_fragment(text, by_slug.get(m.brand_slug)) for m, text in rows]
        for (mention, _), (label, score) in zip(rows, analyzer.predict(texts), strict=True):
            mention.sentiment = label
            mention.sentiment_score = score
        session.commit()
        done += len(rows)
        last_id = rows[-1][0].id
