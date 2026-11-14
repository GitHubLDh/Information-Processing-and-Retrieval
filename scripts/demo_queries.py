#!/usr/bin/env python3
"""Print a short A/B retrieval demo against the running Solr core.

Reads the current query definitions from queries/setup_a and queries/setup_b,
runs them directly against Solr, and prints the top results side by side. It does
not write run files.

Usage:
    python3 scripts/demo_queries.py
    python3 scripts/demo_queries.py --needs Q3 Q1 --top 3
"""

import argparse
import json
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
SETUP_DIRS = {
    "A": ROOT / "queries" / "setup_a",
    "B": ROOT / "queries" / "setup_b",
}


def post(solr: str, core: str, params: dict) -> dict:
    response = requests.post(
        f"{solr.rstrip('/')}/{core}/select",
        data=params,
        timeout=30,
    )
    # Solr's JSON is UTF-8. Do not let requests guess ISO-8859-1 from a missing
    # charset header; that is what corrupted the earlier saved B run files.
    response.encoding = "utf-8"
    response.raise_for_status()
    payload = response.json()
    status = payload.get("responseHeader", {}).get("status", 0)
    if status != 0:
        raise RuntimeError(f"Solr returned status {status}: {payload}")
    return payload


def print_counts(solr: str, core: str) -> None:
    print("Index counts")
    checks = (
        ("all documents", "*:*"),
        ("movie parents", "doc_type:movie"),
        ("review children", "doc_type:review"),
    )
    for label, query in checks:
        payload = post(solr, core, {"q": query, "rows": 0, "wt": "json"})
        print(f"  {label:<18} {payload['response']['numFound']:,}")


def print_results(label: str, payload: dict, top: int) -> None:
    response = payload["response"]
    print(f"\n{label}  (numFound={response['numFound']:,})")
    for rank, doc in enumerate(response["docs"][:top], start=1):
        title = doc.get("title") or "(no title)"
        year = doc.get("year") or "----"
        score = doc.get("score")
        score_text = f"{score:.3f}" if isinstance(score, (int, float)) else "n/a"
        print(
            f"  {rank:2}. {title} ({year})  "
            f"movie_id={doc.get('movie_id')}  score={score_text}"
        )


def load_query(setup: str, qid: str) -> dict:
    path = SETUP_DIRS[setup] / f"{qid}.json"
    if not path.exists():
        raise FileNotFoundError(f"Query file not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def run_need(solr: str, core: str, qid: str, top: int) -> None:
    query_b = load_query("B", qid)
    print(f"\n=== {qid}: {query_b.get('need', '')} ===")
    for setup in ("A", "B"):
        query = load_query(setup, qid)
        payload = post(solr, core, query["params"])
        print_results(f"Setup {setup}", payload, top)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--solr", default="http://localhost:8983/solr")
    parser.add_argument("--core", default="movies")
    parser.add_argument(
        "--needs",
        nargs="+",
        default=["Q3", "Q1"],
        help="query ids to compare (default: Q3 Q1)",
    )
    parser.add_argument("--top", type=int, default=5, help="results per setup")
    args = parser.parse_args()

    try:
        print_counts(args.solr, args.core)
        for qid in args.needs:
            run_need(args.solr, args.core, qid, args.top)
    except requests.RequestException as exc:
        print(f"Solr request failed: {exc}", file=sys.stderr)
        print("Start Solr with: bash solr/startup.sh", file=sys.stderr)
        return 1
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"Demo failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
