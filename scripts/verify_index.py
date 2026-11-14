#!/usr/bin/env python3
"""Verify the running Solr `movies` index against the final collection.

Checks:
  - the collection manifest and collection.jsonl agree;
  - Solr's parent, child, and total document counts match the collection;
  - a sample movie and its review children are retrievable;
  - the `textFoldLower` analyzer folds accents, lowercases, removes stopwords,
    and applies KStem;
  - a fixed set of sanity queries returns results;
  - the display-only fields behave as designed (not full-text searchable).

Exit code 0 means every required check passed. Warnings are printed for known
schema behaviour that does not block the demo (e.g. exact docValues lookups on
fields marked indexed=false).

Usage:
    python3 scripts/verify_index.py
    python3 scripts/verify_index.py --solr http://localhost:8983/solr --core movies
"""

import argparse
import json
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_COLLECTION = ROOT / "data" / "final" / "collection.jsonl"
DEFAULT_MANIFEST = ROOT / "data" / "final" / "collection_manifest.json"

SAMPLE_MOVIE_ID = 11  # Star Wars (1977), has review children in the collection.

ANALYZER_SAMPLE = (
    "Amélie Poulain investigating the Café des Deux Moulins; "
    "running, runners, and the Matrix"
)


class Solr:
    def __init__(self, base_url: str, core: str):
        self.url = f"{base_url.rstrip('/')}/{core}"
        self.session = requests.Session()

    def get(self, path: str, params: dict | None = None) -> dict:
        response = self.session.get(f"{self.url}{path}", params=params or {}, timeout=30)
        response.raise_for_status()
        payload = response.json()
        if payload.get("responseHeader", {}).get("status", 0) != 0:
            raise RuntimeError(f"Solr error: {payload}")
        return payload

    def count(self, query: str) -> int:
        payload = self.get("/select", {"q": query, "rows": 0, "wt": "json"})
        return payload["response"]["numFound"]

    def search(self, query: str, rows: int, fields: str) -> dict:
        return self.get(
            "/select",
            {"q": query, "rows": rows, "fl": fields, "wt": "json"},
        )


class Report:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.warned = 0

    def check(self, name: str, ok: bool, detail: str = "") -> None:
        if ok:
            self.passed += 1
            print(f"PASS  {name:<38} {detail}")
        else:
            self.failed += 1
            print(f"FAIL  {name:<38} {detail}")

    def warn(self, name: str, detail: str = "") -> None:
        self.warned += 1
        print(f"WARN  {name:<38} {detail}")

    def summary(self) -> int:
        print()
        print(
            f"SUMMARY: {self.passed} passed, {self.failed} failed, "
            f"{self.warned} warning(s)"
        )
        return 0 if self.failed == 0 else 1


def load_collection(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def analyzer_tokens(solr: Solr, field_type: str, text: str) -> list[str]:
    payload = solr.get(
        "/analysis/field",
        {
            "analysis.fieldtype": field_type,
            "analysis.fieldvalue": text,
            "wt": "json",
        },
    )
    stages = payload["analysis"]["field_types"][field_type]["index"]
    final_stage = stages[-1]
    if not isinstance(final_stage, list):
        return []
    return [token["text"] for token in final_stage]


def main(solr_url: str, core: str, collection_path: Path, manifest_path: Path) -> int:
    report = Report()

    print(f"Solr:       {solr_url.rstrip('/')}/{core}")
    print(f"Collection: {collection_path}")
    print(f"Manifest:   {manifest_path}")
    print()

    try:
        solr = Solr(solr_url, core)
        solr.count("*:*")
    except requests.RequestException as exc:
        print(f"FAIL  Solr is not reachable at {solr.url}: {exc}")
        print("      Start it with: bash solr/startup.sh")
        return 1

    collection = load_collection(collection_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    movie_count = len(collection)
    review_count = sum(len(doc.get("reviews", [])) for doc in collection)
    expected_total = movie_count + review_count

    # --- Collection and manifest -------------------------------------------
    report.check(
        "manifest document count",
        manifest["output"]["documents"] == movie_count,
        f"{manifest['output']['documents']} == {movie_count}",
    )
    report.check(
        "collection line count",
        movie_count == 6104,
        f"{movie_count} movies",
    )
    report.check(
        "collection review count",
        review_count == 12057,
        f"{review_count} reviews",
    )

    # --- Solr document counts ----------------------------------------------
    total = solr.count("*:*")
    parents = solr.count("doc_type:movie")
    children = solr.count("doc_type:review")

    report.check("Solr total documents", total == expected_total, f"{total} == {expected_total}")
    report.check("Solr movie parents", parents == movie_count, f"{parents} == {movie_count}")
    report.check("Solr review children", children == review_count, f"{children} == {review_count}")

    # --- Sample parent and its children ------------------------------------
    sample = next(
        (doc for doc in collection if doc["movie_id"] == SAMPLE_MOVIE_ID),
        next((doc for doc in collection if doc.get("reviews")), collection[0]),
    )
    sample_id = sample["movie_id"]
    expected_children = len(sample.get("reviews", []))

    parent_payload = solr.search(
        f"movie_id:{sample_id}",
        1,
        "id,doc_type,movie_id,title,plot,overview,genres,cast.name,crew_names,wikipedia.title",
    )
    parent_docs = parent_payload["response"]["docs"]
    parent_ok = (
        parent_payload["response"]["numFound"] == 1
        and len(parent_docs) == 1
        and parent_docs[0].get("id") == f"movie-{sample_id}"
        and parent_docs[0].get("doc_type") == "movie"
        and parent_docs[0].get("title")
        and parent_docs[0].get("plot")
        and parent_docs[0].get("cast.name")
        and parent_docs[0].get("crew_names")
    )
    report.check(
        f"sample parent movie_id:{sample_id}",
        parent_ok,
        f"{parent_docs[0].get('title') if parent_docs else 'not found'}",
    )

    child_payload = solr.search(
        f'{{!child of="doc_type:movie"}}id:movie-{sample_id}',
        expected_children + 5,
        "id,doc_type,review_text",
    )
    child_docs = child_payload["response"]["docs"]
    child_ok = (
        child_payload["response"]["numFound"] == expected_children
        and all(doc.get("doc_type") == "review" for doc in child_docs)
        and all(doc.get("id", "").startswith(f"movie-{sample_id}-review-") for doc in child_docs)
        and all(doc.get("review_text") for doc in child_docs)
    )
    report.check(
        "sample review children",
        child_ok,
        f"{child_payload['response']['numFound']} == {expected_children}",
    )

    no_review_sample = next((doc for doc in collection if not doc.get("reviews")), None)
    if no_review_sample:
        no_review_id = no_review_sample["movie_id"]
        no_review_parent = solr.count(f"movie_id:{no_review_id}")
        no_review_children = solr.count(
            f'{{!child of="doc_type:movie"}}id:movie-{no_review_id}'
        )
        report.check(
            f"parent without children movie_id:{no_review_id}",
            no_review_parent == 1 and no_review_children == 0,
            f"parent={no_review_parent}, children={no_review_children}",
        )

    # --- Analyzer chain -----------------------------------------------------
    tokens = analyzer_tokens(solr, "textFoldLower", ANALYZER_SAMPLE)
    token_set = set(tokens)
    report.check(
        "analyzer accent folding",
        "amelie" in token_set and "cafe" in token_set,
        "Amélie -> amelie, Café -> cafe",
    )
    report.check(
        "analyzer lowercasing",
        "matrix" in token_set and "Matrix" not in token_set,
        "Matrix -> matrix",
    )
    report.check(
        "analyzer stopwords",
        "the" not in token_set and "and" not in token_set,
        "the/and removed",
    )
    report.check(
        "analyzer KStem",
        "investigate" in token_set and "runner" in token_set,
        "investigating -> investigate, runners -> runner",
    )

    # --- Sanity queries -----------------------------------------------------
    sanity = [
        ("title exact phrase", 'title:"star wars"', lambda n: n > 0),
        ("cast name", 'cast.name:"robert de niro"', lambda n: n > 0),
        ("plot term", "plot:astronaut", lambda n: n > 0),
        (
            "nested review parent join",
            '{!parent which="doc_type:movie" score=max}review_text:clever',
            lambda n: n > 0,
        ),
        ("genre + year filter", "genres:comedy AND year:[2000 TO 2010]", lambda n: n > 0),
        ("runtime range", "runtime:[90 TO 120]", lambda n: n > 0),
        ("status filter", "status:Released", lambda n: n > 0),
        ("language filter", "original_language:en", lambda n: n > 0),
    ]
    for name, query, predicate in sanity:
        count = solr.count(query)
        report.check(name, predicate(count), f"{count} matches")

    # --- Display-only fields ------------------------------------------------
    crew_job_field = solr.get("/schema/fields/crew_roles.job")["field"]
    cast_order_field = solr.get("/schema/fields/cast.order")["field"]
    report.check(
        "crew_roles.job not in inverted index",
        crew_job_field.get("indexed") is False,
        "indexed=false",
    )
    report.check(
        "cast.order not in inverted index",
        cast_order_field.get("indexed") is False,
        "indexed=false",
    )

    exact_job = solr.count("crew_roles.job:Producer")
    lowercase_job = solr.count("crew_roles.job:producer")
    plural_job = solr.count("crew_roles.job:producers")
    report.check(
        "crew_roles.job is case-sensitive",
        exact_job == 0 or lowercase_job == 0,
        f"Producer={exact_job}, producer={lowercase_job}",
    )
    report.check(
        "crew_roles.job has no stemming",
        plural_job == 0,
        f"producers={plural_job}",
    )
    if exact_job > 0:
        report.warn(
            "crew_roles.job exact lookup works",
            "docValues still resolve exact terms; not full-text searchable",
        )

    cast_order = solr.count("cast.order:0")
    if cast_order > 0:
        report.warn(
            "cast.order exact lookup works",
            f"cast.order:0 -> {cast_order}; docValues, not a text index",
        )

    return report.summary()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--solr", default="http://localhost:8983/solr")
    parser.add_argument("--core", default="movies")
    parser.add_argument("--collection", type=Path, default=DEFAULT_COLLECTION)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()
    sys.exit(main(args.solr, args.core, args.collection, args.manifest))
