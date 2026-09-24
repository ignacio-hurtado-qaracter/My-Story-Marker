"""The forbidden-term normaliser (spec 009; `docs/definitions.md`, invariant 7).

Text and term go through the **same** fold, so a comparison is always between keys:

1. **Case and accents.** Each character is NFKD-decomposed, combining marks are dropped and
   the rest case-folded (`Estúpido` → `estupido`, `ñ` → `n`). Every output character keeps
   the index of the character it came from, so a match reports its span in the original.
2. **Tokens.** Words are runs of letters, digits, `@` and `$`. A chain of single characters
   joined by one separator (`t.o.n.t.o`, `t-o-n-t-o`, `t*o*n*t*o`) is one token; joined by
   spaces it must be at least three long (`t o n t o`), so ordinary Spanish `y a` is safe.
3. **Leetspeak**, only inside a token that has a letter: `0→o 1→i 3→e 4→a 5→s 7→t @→a $→s`.
   A pure number (`1500`) is left alone.
4. **Repeated letters.** A run of three or more of the same letter becomes one
   (`tontooo` → `tonto`). Such a token is *stretched*: only a stretched token is also
   compared with every double letter squeezed, so `perrrro` matches `perro` but plain
   `pero` never does.
5. **Plurals.** Each token has singular candidates: itself, minus `-s`, minus `-es`, and
   `-ces → -z` (`luces` → `luz`). A text token matches a term token when their candidate
   sets intersect; candidates shorter than three letters are ignored.
6. **Whole words and phrases.** A term of *n* words matches *n* consecutive text tokens;
   its words joined (`hijodeputa`) also match as one token. A term is never found inside a
   longer word (`culo` is not in `ridículo`).
"""

from __future__ import annotations

import itertools
import re
import unicodedata
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Final, Literal

Level = Literal["global", "novel", "lexicon"]

_TOKEN: Final[re.Pattern[str]] = re.compile(r"(?:[^\W_]|[@$])+")
_PUNCT_SEPARATORS: Final[frozenset[str]] = frozenset("-_.*·'")
_LEET: Final[dict[str, str]] = {
    "0": "o",
    "1": "i",
    "3": "e",
    "4": "a",
    "5": "s",
    "7": "t",
    "@": "a",
    "$": "s",
}
_STRETCH: Final[re.Pattern[str]] = re.compile(r"(.)\1{2,}")
_DOUBLE: Final[re.Pattern[str]] = re.compile(r"(.)\1+")
_MIN_CANDIDATE: Final[int] = 3
_MAX_PHRASE_VARIANTS: Final[int] = 512


@dataclass(frozen=True, slots=True)
class Term:
    """One forbidden term and the level it comes from."""

    text: str
    level: Level = "global"


@dataclass(frozen=True, slots=True)
class Match:
    """A forbidden term found in a text. `span` indexes the original text."""

    term: str
    level: Level
    span: tuple[int, int]
    surface: str


@dataclass(frozen=True, slots=True)
class _Token:
    key: str
    start: int
    end: int
    stretched: bool
    candidates: frozenset[str] = field(default_factory=frozenset)
    squeezed: frozenset[str] = field(default_factory=frozenset)


def _fold(text: str) -> tuple[str, list[int]]:
    """Lower-case and strip accents, keeping the original index of every output char."""
    chars: list[str] = []
    origin: list[int] = []
    for index, char in enumerate(text):
        for part in unicodedata.normalize("NFKD", char):
            if unicodedata.combining(part):
                continue
            for folded in part.casefold():
                chars.append(folded)
                origin.append(index)
    return "".join(chars), origin


def _joinable(gap: str, *, spaces_only: list[bool]) -> bool:
    stripped = gap.strip()
    if stripped == "" and 1 <= len(gap) <= 2:
        spaces_only.append(True)
        return True
    if len(stripped) == 1 and stripped in _PUNCT_SEPARATORS and len(gap) <= 3:
        spaces_only.append(False)
        return True
    return False


def _raw_tokens(folded: str) -> list[tuple[str, int, int]]:
    """Tokens of the folded text, with single-character chains merged."""
    raw = [(m.group(0), m.start(), m.end()) for m in _TOKEN.finditer(folded)]
    merged: list[tuple[str, int, int]] = []
    i = 0
    while i < len(raw):
        word, start, end = raw[i]
        if len(word) == 1:
            j = i
            gaps: list[bool] = []
            while (
                j + 1 < len(raw)
                and len(raw[j + 1][0]) == 1
                and _joinable(folded[raw[j][2] : raw[j + 1][1]], spaces_only=gaps)
            ):
                j += 1
            length = j - i + 1
            needed = 3 if any(gaps) else 2
            if length >= needed:
                merged.append(("".join(t[0] for t in raw[i : j + 1]), start, raw[j][2]))
                i = j + 1
                continue
        merged.append((word, start, end))
        i += 1
    return merged


def _singulars(word: str) -> set[str]:
    found = {word}
    if len(word) > _MIN_CANDIDATE:
        if word.endswith("ces"):
            found.add(word[:-3] + "z")
        if word.endswith("ies"):
            found.add(word[:-3] + "y")
        if word.endswith("es"):
            found.add(word[:-2])
        if word.endswith("s"):
            found.add(word[:-1])
    return {w for w in found if len(w) >= _MIN_CANDIDATE or w == word}


def _squeeze(word: str) -> str:
    return _DOUBLE.sub(r"\1", word)


def _make_token(word: str, start: int, end: int) -> _Token:
    if any(c.isalpha() for c in word):
        word = "".join(_LEET.get(c, c) for c in word)
    stretched = _STRETCH.search(word) is not None
    key = _STRETCH.sub(r"\1", word)
    candidates = frozenset(_singulars(key))
    squeezed = frozenset(_squeeze(c) for c in candidates) if stretched else frozenset()
    return _Token(key, start, end, stretched, candidates, squeezed)


def _tokens(text: str) -> tuple[list[_Token], list[int]]:
    folded, origin = _fold(text)
    return [_make_token(w, s, e) for w, s, e in _raw_tokens(folded)], origin


def normalise(text: str) -> str:
    """The text as the matcher sees it: folded, leet-decoded, space-separated tokens."""
    tokens, _ = _tokens(text)
    return " ".join(token.key for token in tokens)


@dataclass(frozen=True, slots=True)
class _TermSpec:
    term: Term
    words: tuple[_Token, ...]
    joined: _Token | None


def _spec(term: Term) -> _TermSpec | None:
    words, _ = _tokens(term.text)
    if not words:
        return None
    joined = None
    if len(words) > 1:
        whole = "".join(w.key for w in words)
        joined = _make_token(whole, 0, 0)
    return _TermSpec(term, tuple(words), joined)


def term_variants(term: str) -> set[str]:
    """Every normalised key the term matches as (singulars, the joined phrase)."""
    spec = _spec(Term(term))
    if spec is None:
        return set()
    variants: set[str] = set()
    for combo in itertools.islice(
        itertools.product(*(sorted(w.candidates) for w in spec.words)), _MAX_PHRASE_VARIANTS
    ):
        variants.add(" ".join(combo))
    if spec.joined is not None:
        variants.update(spec.joined.candidates)
    return variants


def _token_matches(text_token: _Token, term_token: _Token) -> bool:
    if text_token.candidates & term_token.candidates:
        return True
    if text_token.stretched:
        term_squeezed = {_squeeze(c) for c in term_token.candidates}
        return bool(text_token.squeezed & term_squeezed)
    return False


def _as_term(item: Term | str) -> Term:
    return item if isinstance(item, Term) else Term(item)


def find_forbidden(text: str, terms: Iterable[Term | str]) -> list[Match]:
    """Every occurrence of every term in `text`, ordered by position."""
    tokens, origin = _tokens(text)
    specs = [s for s in (_spec(_as_term(t)) for t in terms) if s is not None]
    found: dict[tuple[str, int, int], Match] = {}

    def add(spec: _TermSpec, first: _Token, last: _Token) -> None:
        start, end = origin[first.start], origin[last.end - 1] + 1
        key = (spec.term.text, start, end)
        if key not in found:
            found[key] = Match(spec.term.text, spec.term.level, (start, end), text[start:end])

    for spec in specs:
        size = len(spec.words)
        for i in range(len(tokens) - size + 1):
            window: Sequence[_Token] = tokens[i : i + size]
            if all(_token_matches(t, w) for t, w in zip(window, spec.words, strict=True)):
                add(spec, window[0], window[-1])
        if spec.joined is not None:
            for token in tokens:
                if _token_matches(token, spec.joined):
                    add(spec, token, token)
    return sorted(found.values(), key=lambda m: (m.span, m.term))


__all__ = ["Level", "Match", "Term", "find_forbidden", "normalise", "term_variants"]
