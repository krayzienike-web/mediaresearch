import json
from pathlib import Path

import pytest
from sqlalchemy import select, update

from mediaresearch.collectors.vk import group_names_from, post_to_document
from mediaresearch.config import load_brands
from mediaresearch.models import Document, Mention
from mediaresearch.pipeline import process
from mediaresearch.query import BrandRule
from mediaresearch.sentiment import analyze_pending, brand_fragment, normalize_label

FIXTURES = Path(__file__).parent / "fixtures"
BRANDS = load_brands()
SBER = BrandRule.from_config({"slug": "sber", "match": {"include": ["сбербанк"]}})


class FakeAnalyzer:
    """Негатив, если в тексте есть «ужас», иначе нейтрально. Запоминает, что ему дали."""

    def __init__(self):
        self.seen: list[str] = []

    def predict(self, texts):
        self.seen.extend(texts)
        return [("negative", 0.9) if "ужас" in t else ("neutral", 0.6) for t in texts]


def test_fragment_keeps_only_brand_sentences():
    text = "Конкурент провалил отчётность, это ужас. Сбербанк показал рост. Погода хорошая."
    assert brand_fragment(text, SBER) == "Сбербанк показал рост."


def test_fragment_falls_back_to_text_start():
    assert brand_fragment("Просто текст", SBER) == "Просто текст"
    assert brand_fragment("x" * 5000, None) == "x" * 1500


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("negative", "negative"),
        ("NEUTRAL", "neutral"),
        ("Positive", "positive"),
        ("neg", "negative"),
    ],
)
def test_normalize_label(label, expected):
    assert normalize_label(label) == expected


def test_normalize_label_rejects_unknown():
    with pytest.raises(ValueError):
        normalize_label("LABEL_0")


def _seed(session):
    resp = json.loads((FIXTURES / "vk_newsfeed_search.json").read_text())["response"]
    docs = [post_to_document(i, group_names_from(resp)) for i in resp["items"]]
    process(docs, BRANDS, session)


def test_analyze_pending(session):
    _seed(session)
    analyzer = FakeAnalyzer()

    assert analyze_pending(session, analyzer, BRANDS, batch=1) == 2
    got = {
        m.document.external_id: (m.sentiment, m.sentiment_score)
        for m in session.scalars(select(Mention))
    }
    assert got == {"123456_555": ("negative", 0.9), "-98765_777": ("neutral", 0.6)}

    # Повторный запуск ничего не трогает
    assert analyze_pending(session, analyzer, BRANDS) == 0


def test_manual_and_purged_are_skipped(session):
    _seed(session)
    session.execute(
        update(Mention)
        .where(
            Mention.document_id
            == select(Document.id).where(Document.author_kind == "user").scalar_subquery()
        )
        .values(sentiment="positive", sentiment_manual=True)
    )
    session.execute(update(Document).where(Document.author_kind == "community").values(text=None))
    session.commit()

    assert analyze_pending(session, FakeAnalyzer(), BRANDS) == 0
    manual = session.scalar(select(Mention).where(Mention.sentiment_manual))
    assert manual.sentiment == "positive"


def test_transformers_analyzer_on_tiny_local_model(tmp_path):
    """Прогон настоящего кода с torch/transformers на крошечной случайной модели (без интернета)."""
    pytest.importorskip("torch")
    from transformers import BertConfig, BertForSequenceClassification, BertTokenizerFast

    from mediaresearch.sentiment import TransformersAnalyzer

    vocab = ["[PAD]", "[UNK]", "[CLS]", "[SEP]", "[MASK]", "сбер", "ужас", "хорошо"]
    (tmp_path / "vocab.txt").write_text("\n".join(vocab))
    BertTokenizerFast(vocab_file=str(tmp_path / "vocab.txt")).save_pretrained(tmp_path)
    config = BertConfig(
        vocab_size=len(vocab),
        hidden_size=16,
        num_hidden_layers=1,
        num_attention_heads=2,
        intermediate_size=32,
        num_labels=3,
        id2label={0: "negative", 1: "neutral", 2: "positive"},
        label2id={"negative": 0, "neutral": 1, "positive": 2},
    )
    BertForSequenceClassification(config).save_pretrained(tmp_path)

    result = TransformersAnalyzer(str(tmp_path), batch_size=2).predict(
        ["сбер ужас", "сбер", "хорошо"]
    )
    assert len(result) == 3
    for label, score in result:
        assert label in {"negative", "neutral", "positive"}
        assert 1 / 3 <= score <= 1
