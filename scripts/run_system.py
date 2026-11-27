#!/usr/bin/env python3
"""Run a registered search system over Q*.json needs and save TREC + JSON runs.

Usage:
    python3 scripts/run_system.py --system m3_lexical --queries queries/m3 --run-id M3_BASE
    python3 scripts/run_system.py --system m2_b --queries queries/setup_b --run-id CHECK
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from search import Result, registry, write_run  # noqa: E402
from search.solr import DEFAULT_COLLECTION, DEFAULT_SOLR_URI  # noqa: E402


def validate_config(need: dict) -> None:
    """Keep the need statement and its explicit Solr parameters in sync."""
    qid = need.get("qid")
    if not qid or not need.get("need"):
        raise ValueError("query config needs qid and need")
    params = need.get("params")
    if params is None:
        return
    if "text" in params and params["text"] != need["need"]:
        raise ValueError(f"{qid}: params.text must equal need")
    if "fq" in params:
        expected = ["doc_type:movie", *need.get("filters", [])]
        if params["fq"] != expected:
            raise ValueError(f"{qid}: params.fq must be doc_type:movie plus the need filters")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--system", required=True, help="registered system name, e.g. m3_lexical")
    parser.add_argument("--queries", type=Path, required=True, help="directory of Q*.json configs")
    parser.add_argument("--runs", type=Path, default=Path("runs"))
    parser.add_argument("--run-id", default=None, help="defaults to --system")
    parser.add_argument("--uri", default=DEFAULT_SOLR_URI)
    parser.add_argument("--collection", default=DEFAULT_COLLECTION)
    args = parser.parse_args()

    if not registry.is_implemented(args.system):
        parser.error(
            f"system {args.system!r} has no backend yet; "
            f"registered: {', '.join(registry.system_names())}"
        )

    query_files = sorted(args.queries.glob("Q*.json"))
    if not query_files:
        parser.error(f"no Q*.json query configs in {args.queries}")

    run_id = args.run_id or args.system
    args.runs.mkdir(parents=True, exist_ok=True)
    rankings: dict[str, list[Result]] = {}

    for query_file in query_files:
        need = json.loads(query_file.read_text(encoding="utf-8"))
        validate_config(need)
        qid = need["qid"]

        started = time.perf_counter()
        response = registry.search_response(
            need, args.system, uri=args.uri, collection=args.collection
        )
        latency_ms = (time.perf_counter() - started) * 1000
        results = response.results
        rankings[qid] = results

        output = {
            "system": args.system,
            "setup": args.system,
            "qid": qid,
            "need": need["need"],
            "endpoint": f"{args.uri.rstrip('/')}/{args.collection}/select",
            "num_found": response.num_found,
            "query_params": response.query_params,
            "latency_ms": round(latency_ms, 3),
            "results": [
                {
                    "rank": rank,
                    "movie_id": result.movie_id,
                    "title": result.title,
                    "score": result.score,
                    "overview": result.snippet,
                    "year": result.year,
                }
                for rank, result in enumerate(results, start=1)
            ],
        }
        out_path = args.runs / f"{run_id}_{qid}.json"
        out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"wrote {out_path} ({len(results)} results, {latency_ms:.1f} ms)")

    trec_path = args.runs / f"{run_id}.run"
    write_run(rankings, trec_path, run_id)
    print(f"TREC run: {trec_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
