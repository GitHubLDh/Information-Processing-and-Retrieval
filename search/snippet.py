"""Short, query-aware snippets for the search page."""

from __future__ import annotations

import re

_WORD_RE = re.compile(r"[^\W_]+(?:['’-][^\W_]+)*", re.UNICODE)
_MIN_TERM_LENGTH = 3


def _clean(text: str | None) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _query_terms(query: str) -> list[str]:
    terms: list[str] = []
    seen: set[str] = set()
    for raw in _WORD_RE.findall(query or ""):
        term = raw.strip("'’-")
        if len(term) < _MIN_TERM_LENGTH or term.casefold() in seen:
            continue
        seen.add(term.casefold())
        terms.append(term)
    return terms


def _leading(text: str, length: int) -> str:
    if len(text) <= length:
        return text
    return text[:length].rstrip() + "…"


def _window(text: str, terms: list[str], length: int) -> tuple[str, bool]:
    text = _clean(text)
    if not text:
        return "", False

    earliest = None
    for term in terms:
        match = re.search(rf"(?<!\w){re.escape(term)}(?!\w)", text, re.IGNORECASE)
        if match and (earliest is None or match.start() < earliest.start()):
            earliest = match

    if earliest is None:
        return _leading(text, length), False

    before = 1 if earliest.start() > 0 else 0
    after = 1 if earliest.end() < len(text) else 0
    body_length = max(1, length - before - after)
    start = max(0, earliest.start() - body_length // 2)
    end = min(len(text), start + body_length)
    if end - start < body_length:
        start = max(0, end - body_length)
        end = min(len(text), start + body_length)

    body = text[start:end].strip()
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(text) else ""
    return prefix + body + suffix, True


def make_snippet(
    text: str | None,
    query: str,
    length: int = 240,
    *,
    fallback: str | None = "",
) -> str:
    """Return a ~``length``-character excerpt centred on a query term.

    When ``text`` has no query term, the ``fallback`` text is used instead
    (the caller passes the Solr ``overview``). Both inputs are whitespace
    normalised; no relevance judgement or hidden document text is used.
    """
    if length < 20:
        raise ValueError("length must be at least 20 characters")

    terms = _query_terms(query)
    primary, found = _window(text or "", terms, length)
    if found or not fallback:
        return primary

    secondary, _ = _window(fallback, terms, length)
    return secondary or primary
