"""Правила сопоставления текста с брендом.

Синтаксис ключевого выражения (одна строка в `include` / `exclude`):
  сбербанк         — слово с учётом морфологии (сбербанка, сбербанку, ...)
  сбер онлайн      — фраза: слова подряд, каждое с учётом морфологии
  сбербанк*        — префикс: любое слово, начинающееся на «сбербанк»

Бренд найден, если сработало хотя бы одно выражение из `include`
и ни одно из `exclude`.
"""

import re
from dataclasses import dataclass, field
from functools import lru_cache

import pymorphy3

_TOKEN_RE = re.compile(r"\w+", re.UNICODE)
_morph = pymorphy3.MorphAnalyzer()


def _norm(word: str) -> str:
    return word.lower().replace("ё", "е")


@lru_cache(maxsize=200_000)
def lemmas(word: str) -> frozenset[str]:
    """Все возможные начальные формы слова: так не теряем совпадения из-за омонимии."""
    return frozenset(_norm(p.normal_form) for p in _morph.parse(word))


def tokenize(text: str) -> list[str]:
    return [_norm(t) for t in _TOKEN_RE.findall(text)]


@dataclass(frozen=True)
class Term:
    value: str
    prefix: bool
    lemma_set: frozenset[str] = frozenset()

    @classmethod
    def parse(cls, raw: str) -> "Term":
        raw = _norm(raw)
        if raw.endswith("*"):
            return cls(raw[:-1], prefix=True)
        return cls(raw, prefix=False, lemma_set=lemmas(raw))

    def matches(self, token: str) -> bool:
        if self.prefix:
            return token.startswith(self.value)
        return token == self.value or not self.lemma_set.isdisjoint(lemmas(token))


@dataclass(frozen=True)
class Phrase:
    source: str
    terms: tuple[Term, ...]

    @classmethod
    def parse(cls, raw: str) -> "Phrase":
        words = [w for w in re.split(r"\s+", raw.strip().strip('"')) if w]
        terms = tuple(Term.parse(w) for w in words)
        if not terms:
            raise ValueError(f"Пустое выражение: {raw!r}")
        return cls(raw, terms)

    def find(self, tokens: list[str]) -> bool:
        n = len(self.terms)
        for i in range(len(tokens) - n + 1):
            if all(t.matches(tokens[i + j]) for j, t in enumerate(self.terms)):
                return True
        return False


@dataclass
class BrandRule:
    slug: str
    name: str
    include: list[Phrase]
    exclude: list[Phrase] = field(default_factory=list)
    search: list[str] = field(default_factory=list)

    @classmethod
    def from_config(cls, cfg: dict) -> "BrandRule":
        match = cfg.get("match", {})
        include = [Phrase.parse(s) for s in match.get("include", [])]
        if not include:
            raise ValueError(f"У бренда {cfg.get('slug')!r} пустой match.include")
        return cls(
            slug=cfg["slug"],
            name=cfg.get("name", cfg["slug"]),
            include=include,
            exclude=[Phrase.parse(s) for s in match.get("exclude", [])],
            search=list(cfg.get("search", [])),
        )

    def match(self, text: str) -> list[str]:
        """Возвращает сработавшие include-выражения или [], если бренд не найден."""
        tokens = tokenize(text)
        hits = [p.source for p in self.include if p.find(tokens)]
        if not hits or any(p.find(tokens) for p in self.exclude):
            return []
        return hits
