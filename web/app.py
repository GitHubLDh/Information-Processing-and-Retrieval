#!/usr/bin/env python3
"""Small Flask demo over the shared M2/M3 retrieval registry.

Run from the repository root with ``python3 web/app.py``. Solr settings can be
overridden with ``PRI_SOLR_URI``, ``PRI_SOLR_COLLECTION`` and ``PRI_WEB_PORT``.
"""

from __future__ import annotations

import json
import os
import sys
import time
from functools import lru_cache
from pathlib import Path

import requests
from flask import Flask, render_template, request

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from search import lexical, registry  # noqa: E402
from search.solr import DEFAULT_COLLECTION, DEFAULT_SOLR_URI  # noqa: E402
from search.snippet import make_snippet  # noqa: E402

app = Flask(__name__)

SOLR_URI = os.getenv("PRI_SOLR_URI", DEFAULT_SOLR_URI)
COLLECTION = os.getenv("PRI_SOLR_COLLECTION", DEFAULT_COLLECTION)
PORT = int(os.getenv("PRI_WEB_PORT", "5000"))
COLLECTION_PATH = ROOT / "data" / "final" / "collection.jsonl"

SYSTEM_LABELS = {
    "m2_a": "M2-A · plot only",
    "m2_b": "M2-B · plot + overview rerank",
    "m3_lexical": "M3-lexical · frozen Setup B",
    "semantic": "Semantic (P2)",
    "hybrid": "Hybrid (P3)",
}
SOURCE_LABELS = {"story": "Plot / story", "reviews": "Review text"}


@lru_cache(maxsize=1)
def load_lookups() -> dict[int, dict[str, str]]:
    """Load display-only plot and Wikipedia URL fields by movie id.

    The Solr ``fl`` list is frozen by the M2 runs, so the page reads these
    fields from the final collection instead of changing retrieval requests.
    A missing collection degrades to Solr's own overview as the snippet.
    """
    lookups: dict[int, dict[str, str]] = {}
    try:
        with COLLECTION_PATH.open(encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                doc = json.loads(line)
                wiki = doc.get("wikipedia") or {}
                lookups[int(doc["movie_id"])] = {
                    "plot": doc.get("plot") or "",
                    "wikipedia_url": wiki.get("url") or "",
                }
    except (OSError, ValueError):
        return {}
    return lookups


@lru_cache(maxsize=1)
def example_needs() -> list[dict[str, str]]:
    examples: list[dict[str, str]] = []
    for path in sorted((ROOT / "queries" / "m3").glob("Q*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        examples.append(
            {
                "qid": data["qid"],
                "need": data["need"],
                "source": data.get("source", "story"),
            }
        )
    return examples


def base_context(**extra: object) -> dict[str, object]:
    context: dict[str, object] = {
        "systems": [
            {
                "name": name,
                "label": SYSTEM_LABELS.get(name, name),
                "implemented": registry.is_implemented(name),
            }
            for name in registry.system_names()
        ],
        "source_labels": SOURCE_LABELS,
        "examples": example_needs(),
        "q": "",
        "selected_system": "m2_b",
        "selected_source": "story",
        "results": None,
        "num_found": None,
        "latency_ms": None,
        "error": None,
        "message": None,
    }
    context.update(extra)
    return context


def build_need(text: str, system: str, source: str) -> dict[str, object]:
    """Turn the free-text form input into the registry's need dictionary.

    M2-A/M2-B build their params through the same frozen builders as the
    runner. M3-lexical uses the current M3 baseline: Setup B's parameters,
    including the top-20 overview rerank for story needs.
    """
    need: dict[str, object] = {
        "qid": "WEB",
        "need": text,
        "source": source,
        "filters": [],
    }
    if system == "m3_lexical":
        need["params"] = dict(lexical.query_params(need, "B"))
    return need


@app.get("/")
def index() -> str:
    return render_template("index.html", **base_context())


@app.get("/search")
def search() -> tuple[str, int] | str:
    q = request.args.get("q", "").strip()
    system = request.args.get("system", "m2_b")
    source = request.args.get("source", "story")
    if source not in SOURCE_LABELS:
        source = "story"

    context = base_context(q=q, selected_system=system, selected_source=source)

    if not q:
        context["error"] = "Enter a movie description to search."
        return render_template("index.html", **context)

    if system not in registry.system_names():
        available = ", ".join(registry.system_names())
        context["error"] = f"Unknown system {system!r}. Available systems: {available}."
        return render_template("index.html", **context), 400

    if not registry.is_implemented(system):
        context["message"] = (
            f"{system!r} is registered but has no backend yet (pending P2/P3). "
            "Try M2-A, M2-B or M3-lexical in the meantime."
        )
        return render_template("index.html", **context)

    need = build_need(q, system, source)
    started = time.perf_counter()
    try:
        response = registry.search_response(
            need, system, uri=SOLR_URI, collection=COLLECTION
        )
    except requests.RequestException as exc:
        context["error"] = f"Could not reach Solr at {SOLR_URI}/{COLLECTION}: {exc}"
        return render_template("index.html", **context), 502
    except (ValueError, RuntimeError, KeyError) as exc:
        context["error"] = f"Search failed: {exc}"
        return render_template("index.html", **context), 400
    latency_ms = (time.perf_counter() - started) * 1000

    lookups = load_lookups()
    results = []
    for rank, result in enumerate(response.results, start=1):
        info = lookups.get(result.movie_id, {})
        results.append(
            {
                "rank": rank,
                "movie_id": result.movie_id,
                "title": result.title or f"Movie {result.movie_id}",
                "year": result.year,
                "score": result.score,
                "snippet": make_snippet(
                    info.get("plot", ""), q, 240, fallback=result.snippet
                ),
                "matched_field": result.matched_field,
                "wikipedia_url": info.get("wikipedia_url", ""),
            }
        )

    context.update(
        results=results,
        num_found=response.num_found,
        latency_ms=round(latency_ms, 1),
    )
    return render_template("index.html", **context)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=PORT, debug=False)
