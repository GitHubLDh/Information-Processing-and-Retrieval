"""Run the frozen Setup B query files and write per-query JSON and TREC runs.

Usage:
    python scripts/run_setup_b.py
    python scripts/run_setup_b.py --endpoint http://localhost:8983/solr/movies/select
"""

import argparse
import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_QUERIES = ROOT / "queries" / "setup_b"
DEFAULT_OUTPUT = ROOT / "runs"
DEFAULT_ENDPOINT = "http://localhost:8983/solr/movies/select"


def query_solr(endpoint, params):
    body = urlencode([tuple(item) for item in params]).encode("utf-8")
    request = Request(
        endpoint,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=90) as response:
            payload = json.loads(response.read().decode("utf-8"))
            status = payload.get("responseHeader", {}).get("status", 0)
            if status != 0:
                raise RuntimeError(f"Solr returned response status {status}: {payload}")
            return payload
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Solr returned HTTP {error.code}: {detail}") from error
    except URLError as error:
        raise RuntimeError(f"Could not reach Solr at {endpoint}: {error}") from error


def run_query_file(query_file, endpoint, output_dir):
    config = json.loads(query_file.read_text(encoding="utf-8"))
    params = config["params"]
    response = query_solr(endpoint, params)
    solr_docs = response.get("response", {}).get("docs", [])

    results = []
    seen_movie_ids = set()
    for rank, doc in enumerate(solr_docs, start=1):
        movie_id = doc.get("movie_id")
        if movie_id is None:
            raise RuntimeError(
                f"{config['qid']} result {rank} is missing movie_id; refusing to write an unstable run ID"
            )
        if movie_id in seen_movie_ids:
            raise RuntimeError(f"{config['qid']} returned parent movie {movie_id} more than once")
        seen_movie_ids.add(movie_id)
        expected_solr_id = f"movie-{movie_id}"
        if doc.get("id") != expected_solr_id:
            raise RuntimeError(
                f"{config['qid']} result {rank} has Solr id {doc.get('id')!r}; expected {expected_solr_id!r}"
            )
        results.append({
            "rank": rank,
            "id": movie_id,
            "movie_id": movie_id,
            "solr_id": doc.get("id"),
            "title": doc.get("title"),
            "score": doc.get("score"),
        })

    output = {
        "setup": "B",
        "qid": config["qid"],
        "need": config["need"],
        "rationale": config["rationale"],
        "endpoint": endpoint,
        "num_found": response.get("response", {}).get("numFound"),
        "query_params": [{"name": key, "value": value} for key, value in params],
        "results": results,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    result_path = output_dir / f"B_{config['qid']}.json"
    result_path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return config["qid"], result_path, results


def main():
    parser = argparse.ArgumentParser(description="Run the frozen movie Setup B queries.")
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    parser.add_argument("--queries", type=Path, default=DEFAULT_QUERIES)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--run-id", default="setup_b")
    args = parser.parse_args()

    query_files = sorted(args.queries.glob("Q*.json"))
    if not query_files:
        parser.error(f"No Q*.json query files found in {args.queries}")

    trec_rows = []
    for query_file in query_files:
        qid, result_path, results = run_query_file(query_file, args.endpoint, args.output_dir)
        print(f"{qid}: {len(results)} saved results -> {result_path}")
        for item in results:
            trec_rows.append(
                f"{qid} Q0 {item['movie_id']} {item['rank']} {item['score']} {args.run_id}"
            )

    trec_path = args.output_dir / "B.run"
    trec_path.write_text("\n".join(trec_rows) + "\n", encoding="utf-8")
    print(f"TREC run: {trec_path}")


if __name__ == "__main__":
    main()
