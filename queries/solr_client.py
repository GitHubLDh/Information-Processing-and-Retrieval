#!/usr/bin/env python3
"""Run Setup A/B queries against Solr, saving per-need JSON results and a TREC run file.

Usage:
    python3 queries/solr_client.py --queries queries/setup_a --setup A
    python3 queries/solr_client.py --queries queries/setup_b --setup B
"""

import argparse
import json
from pathlib import Path

import requests


def fetch_solr_results(params: dict, solr_uri: str, collection: str) -> dict:
    # Sent as a classic form-encoded POST, not Solr's JSON Request API --
    # queries using "v=$paramname" parameter dereferencing (e.g. Setup B's
    # nested parent/child queries) silently return nothing under the JSON
    # transport, even though the same params succeed here.
    response = requests.post(f"{solr_uri}/{collection}/select", data=params)
    response.raise_for_status()
    payload = response.json()
    status = payload.get("responseHeader", {}).get("status", 0)
    if status != 0:
        raise RuntimeError(f"Solr returned response status {status}: {payload}")
    return payload


def to_run_format(solr_response: dict, qid: str, overview_chars: int = 150) -> list[dict]:
    results = []
    seen_movie_ids = set()
    for rank, doc in enumerate(solr_response["response"]["docs"], start=1):
        movie_id = doc.get("movie_id")
        if movie_id is None:
            raise RuntimeError(f"{qid} result {rank} is missing movie_id; refusing to write an unstable run")
        if movie_id in seen_movie_ids:
            raise RuntimeError(f"{qid} returned movie {movie_id} more than once")
        seen_movie_ids.add(movie_id)
        expected_id = f"movie-{movie_id}"
        if doc.get("id") != expected_id:
            raise RuntimeError(f"{qid} result {rank} has id {doc.get('id')!r}, expected {expected_id!r}")
        results.append({
            "rank": rank,
            "movie_id": movie_id,
            "id": doc.get("id"),
            "title": doc.get("title"),
            "score": doc.get("score"),
            "overview": doc.get("overview", "")[:overview_chars],
            "year": doc.get("year"),
        })
    return results


def main(queries_dir: Path, runs_dir: Path, setup: str, solr_uri: str, collection: str, run_id: str):
    runs_dir.mkdir(parents=True, exist_ok=True)
    trec_rows = []
    for query_file in sorted(queries_dir.glob("Q*.json")):
        need_id = query_file.stem  # "Q1.json" -> "Q1"
        query_file_contents = json.loads(query_file.read_text())
        solr_response = fetch_solr_results(query_file_contents["params"], solr_uri, collection)
        results = to_run_format(solr_response, need_id)

        output = {
            "setup": setup,
            "qid": need_id,
            "need": query_file_contents.get("need"),
            "rationale": query_file_contents.get("rationale"),
            "endpoint": f"{solr_uri}/{collection}/select",
            "num_found": solr_response["response"]["numFound"],
            "query_params": query_file_contents["params"],
            "results": results,
        }
        out_path = runs_dir / f"{setup}_{need_id}.json"
        out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False))
        print(f"wrote {out_path} ({len(results)} results)")

        for item in results:
            trec_rows.append(f"{need_id} Q0 {item['movie_id']} {item['rank']} {item['score']} {run_id}")

    trec_path = runs_dir / f"{setup}.run"
    trec_path.write_text("\n".join(trec_rows) + "\n")
    print(f"TREC run: {trec_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--queries", type=Path, required=True, help="e.g. queries/setup_a or queries/setup_b")
    parser.add_argument("--setup", required=True, help="e.g. 'A' or 'B' -- used in output filenames")
    parser.add_argument("--runs", type=Path, default=Path("runs"))
    parser.add_argument("--uri", default="http://localhost:8983/solr")
    parser.add_argument("--collection", default="movies")
    parser.add_argument("--run-id", default=None, help="defaults to --setup")
    args = parser.parse_args()
    main(args.queries, args.runs, args.setup, args.uri, args.collection, args.run_id or args.setup)
