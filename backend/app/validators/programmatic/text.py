"""Shared text helpers of the programmatic validators (spec 008).

Normalisation is casefold + accents stripped + every non-letter turned into a space, so
"Lucía," and "lucia" normalise to the same word. Fact matching (``fact_rendered``):

- a value of at most three words matches as a normalised phrase on word boundaries;
- a longer value (a memory, a mandatory element) matches when at least half of its **key
  terms** appear in the text. Key terms are the content words of at least five letters
  that are not stopwords, plus the capitalised words of at least three letters (proper
  nouns such as "Roma"). A value with no key term falls back to the phrase rule.

This is deliberately simple: it proves the prose *mentions* the fact; whether it integrates
it naturally is the judge's job (D11).
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping, Sequence
from typing import Final

_WORD: Final = re.compile(r"[^\W\d_]+", re.UNICODE)

#: Common Spanish function words and very frequent words (normalised, no accents).
_STOP_TEXT: Final = """
    a al algo algun alguna algunas alguno algunos ante antes aqui asi aun aunque ayer bajo
    bien cada casi como con contra cual cuales cuando cuanto de del desde donde dos el ella
    ellas ello ellos en entonces entre era eran eres es esa esas ese eso esos esta estaba
    estaban estar estas este esto estos fue fueron ha habia habian hace hacia han hasta hay
    la las le les lo los mas me mi mientras mis mucho muchos muy nada ni no nos nosotros o
    otra otras otro otros para pero poco por porque pues que quien se sea ser si sin sino
    sobre son su sus tal tambien tan tanto te tenia tiene todo todos toda todas tras tu tus
    un una unas uno unos ya yo solo siempre nunca luego despues ahora donde dentro fuera
    hacer habia habria sido siendo sera seria estaba estuvo tenia tenian tener puede podia
    otra mismo misma mismos mismas cosas cosa veces tiempo parte
    """
STOPWORDS: Final[frozenset[str]] = frozenset(_STOP_TEXT.split())


def strip_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


def normalise(text: str) -> str:
    """Casefold, strip accents, keep letters only (single spaces)."""
    return " ".join(_WORD.findall(strip_accents(text.casefold())))


def words(text: str) -> list[str]:
    """The letter tokens of `text`, as written."""
    return _WORD.findall(text)


def edit_distance(a: str, b: str) -> int:
    """Levenshtein distance (small strings only)."""
    if a == b:
        return 0
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        current = [i]
        for j, cb in enumerate(b, start=1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (ca != cb)))
        previous = current
    return previous[-1]


def key_terms(value: str) -> set[str]:
    """Content words (≥ 5 letters, not stopwords) and capitalised words (≥ 3 letters)."""
    terms: set[str] = set()
    for token in words(value):
        norm = normalise(token)
        if norm in STOPWORDS:
            continue
        if len(norm) >= 5 or (len(norm) >= 3 and token[0].isupper()):
            terms.add(norm)
    return terms


def phrase_in(phrase: str, normalised_text: str) -> bool:
    target = normalise(phrase)
    if not target:
        return False
    return f" {target} " in f" {normalised_text} "


def fact_terms(value: str) -> tuple[str, set[str]]:
    """``("phrase", {phrase})`` for short values, ``("terms", key_terms)`` for long ones."""
    if len(words(value)) <= 3:
        return ("phrase", {normalise(value)})
    terms = key_terms(value)
    if not terms:
        return ("phrase", {normalise(value)})
    return ("terms", terms)


def fact_rendered(value: str, text: str, *, normalised: str | None = None) -> bool:
    """Whether `text` renders the fact `value` under the rules of the module docstring."""
    norm_text = normalised if normalised is not None else normalise(text)
    mode, terms = fact_terms(value)
    if mode == "phrase":
        return any(phrase_in(term, norm_text) for term in terms if term)
    present = set(norm_text.split())
    return len(terms & present) * 2 >= len(terms)


def _slug(text: str) -> str:
    return "-".join(normalise(text).split())


def memory_title(fact_key: str, fact_value: str, brief: Mapping[str, object] | None) -> str:
    """The title of the memory behind fact `memory.<slug>`, from the brief when possible.

    Falls back to the fact value up to its first ``:``, ``—`` or ``.``.
    """
    suffix = fact_key.split(".", 1)[1] if "." in fact_key else fact_key
    memories = brief.get("memories") if brief is not None else None
    if isinstance(memories, Sequence) and not isinstance(memories, str):
        for memory in memories:
            if not isinstance(memory, Mapping):
                continue
            title = memory.get("title")
            if not isinstance(title, str) or not title:
                continue
            slug = _slug(title)
            if slug == _slug(suffix) or suffix.startswith(slug) or title in fact_value:
                return title
    head = re.split(r"[:—.]", fact_value, maxsplit=1)[0].strip()
    return head or fact_value


def as_mapping(value: object) -> Mapping[str, object] | None:
    return value if isinstance(value, Mapping) else None


__all__ = [
    "STOPWORDS",
    "as_mapping",
    "edit_distance",
    "fact_rendered",
    "fact_terms",
    "key_terms",
    "memory_title",
    "normalise",
    "phrase_in",
    "strip_accents",
    "words",
]
