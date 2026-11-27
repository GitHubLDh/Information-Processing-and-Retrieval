#!/usr/bin/env python3
"""Run the rubric-based query rewriting experiment and compare with M3_BASE.

The rewrite clauses come only from the information-need rubric vocabulary in
``eval/common.py`` (plus short phrases paraphrasing that vocabulary). No judged
document text and no relevance grades are used to construct them; qrels are
loaded only after the runs, to measure the result.

Usage:
    python3 scripts/rewrite_experiment.py --write-configs \
        --uri http://127.0.0.1:18984/solr
    python3 scripts/rewrite_experiment.py --mode rubric \
        --uri http://127.0.0.1:18984/solr
"""

from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import sys
import tempfile
import time
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for candidate in (ROOT, ROOT / "scripts", ROOT / "eval"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

import common  # noqa: E402
from run_system import validate_config  # noqa: E402
from trec_eval_run import evaluate_run as evaluate_with_trec_eval, write_qrels  # noqa: E402
from search import Result, registry, write_run  # noqa: E402
from search.solr import DEFAULT_COLLECTION, DEFAULT_SOLR_URI  # noqa: E402

CONFIG_DIR = ROOT / "queries" / "rewrites"
BASE_CONFIG_DIR = ROOT / "queries" / "m3"
BASELINE_RUN = ROOT / "runs" / "M3_BASE.run"
QRELS = ROOT / "eval" / "data" / "qrels.csv"
RUN_IDS = {"none": "rewrite_none", "rubric": "rewrite_rubric"}

# Short phrases are paraphrases of the rubric criteria; every clause also
# contains at least one term from INFORMATION_NEEDS[qid]["review_terms"/"plot_terms"].
REWRITE_TERMS: dict[str, list[tuple[str, float]]] = {
    "Q1": [
        ('"witty dialogue"', 0.3),
        ('"sharp writing"', 0.3),
        ("satirical", 0.2),
        ("clever", 0.1),
    ],
    "Q2": [
        ("predictable", 0.3),
        ('"formulaic romance"', 0.2),
        ("heartwarming", 0.2),
        ("sentimental", 0.1),
    ],
    "Q3": [
        ('"outer space"', 0.3),
        ("astronaut", 0.3),
        ("stranded", 0.2),
        ('"return home"', 0.1),
    ],
    "Q4": [
        ('"FBI agent"', 0.3),
        ('"serial killer"', 0.3),
        ('"series of murders"', 0.2),
        ("profiler", 0.1),
    ],
    "Q5": [
        ('"crime family"', 0.3),
        ('"Italian-American"', 0.2),
        ('"organized crime"', 0.2),
        ('"De Niro"', 0.1),
    ],
}


def validate_rewrite_terms(qid: str, terms: list[tuple[str, float]]) -> None:
    entry = common.INFORMATION_NEEDS[qid]
    vocab = {
        term.casefold()
        for term in entry["review_terms"] + entry["plot_terms"]
    }
    for term, weight in terms:
        if not 0.1 <= weight <= 0.3:
            raise ValueError(f"{qid}: rewrite weight {weight} outside 0.1–0.3")
        normalized = term.strip('"').casefold()
        tokens = re.findall(r"[^\W_]+(?:[-'][^\W_]+)*", normalized)
        if normalized not in vocab and not any(token in vocab for token in tokens):
            raise ValueError(f"{qid}: {term!r} is not grounded in the need vocabulary")


def build_configs() -> list[dict]:
    """Generate rewrite configs from the frozen M3 baseline configs."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    configs: list[dict] = []
    for path in sorted(BASE_CONFIG_DIR.glob("Q*.json")):
        baseline = json.loads(path.read_text(encoding="utf-8"))
        qid = baseline["qid"]
        terms = REWRITE_TERMS[qid]
        validate_rewrite_terms(qid, terms)

        field = "review_text" if baseline["source"] == "reviews" else "plot"
        clauses = [f"{field}:{term}^{weight:.1f}" for term, weight in terms]
        params = deepcopy(baseline["params"])
        params["rw"] = clauses
        if baseline["source"] == "reviews":
            params["childq"] = "{!edismax v=$text bq=$rw}"
        else:
            params["q"] = "{!edismax v=$text bq=$rw}"

        config = {
            "qid": qid,
            "need": baseline["need"],
            "source": baseline["source"],
            "filters": deepcopy(baseline["filters"]),
            "rewrite": {
                "mode": "rubric",
                "field": field,
                "clauses": clauses,
                "evidence": "eval/common.py INFORMATION_NEEDS vocabulary/criteria only",
            },
            "params": params,
        }
        out_path = CONFIG_DIR / path.name
        out_path.write_text(
            json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        configs.append(config)
        print(f"wrote {out_path}")
    return configs


def load_configs(config_dir: Path) -> list[dict]:
    configs: list[dict] = []
    for path in sorted(config_dir.glob("Q*.json")):
        config = json.loads(path.read_text(encoding="utf-8"))
        validate_config(config)
        configs.append(config)
    if {config["qid"] for config in configs} != set(common.QIDS):
        raise ValueError(f"{config_dir}: expected Q1–Q5 rewrite configs")
    return configs


def strip_rewrite(config: dict) -> dict:
    """Return the original M3 config, with no rubric boost clauses."""
    need = deepcopy(config)
    params = need["params"]
    params.pop("rw", None)
    if need["source"] == "reviews":
        params["childq"] = "{!edismax v=$text}"
    else:
        params["q"] = "{!edismax v=$text}"
    params.pop("debug", None)
    validate_config(need)
    return need


def run_mode(
    mode: str,
    configs: list[dict],
    args: argparse.Namespace,
) -> tuple[Path, dict[str, float]]:
    """Run one mode and write a TREC run plus per-query JSON metadata."""
    run_id = RUN_IDS[mode]
    rankings: dict[str, list[Result]] = {}
    latencies: dict[str, float] = {}
    args.runs.mkdir(parents=True, exist_ok=True)

    for config in configs:
        qid = config["qid"]
        need = config if mode == "rubric" else strip_rewrite(config)
        started = time.perf_counter()
        response = registry.search_response(
            need, "m3_lexical", uri=args.uri, collection=args.collection
        )
        latency_ms = (time.perf_counter() - started) * 1000
        rankings[qid] = response.results
        latencies[qid] = latency_ms

        output = {
            "system": "m3_lexical",
            "setup": run_id,
            "qid": qid,
            "need": need["need"],
            "rewrite_mode": mode,
            "rewrite_clauses": config.get("rewrite", {}).get("clauses", []),
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
                for rank, result in enumerate(response.results, start=1)
            ],
        }
        out_path = args.runs / f"{run_id}_{qid}.json"
        out_path.write_text(
            json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"wrote {out_path} ({len(response.results)} results, {latency_ms:.1f} ms)")

    run_path = write_run(rankings, args.runs / f"{run_id}.run", run_id)
    print(f"TREC run: {run_path}")
    return run_path, latencies


def evaluate(ranking_path: Path, qrels: dict[str, dict[str, int]]) -> dict:
    """Local metric implementation matching eval/output/results.md definitions."""
    rankings = common.load_trec_run(ranking_path)
    per_query: dict[str, dict[str, float]] = {}
    names = ("P@5", "P@10", "AP", "nDCG@10", "Recall@20", "MRR@10")

    for qid in common.QIDS:
        grades = qrels.get(qid, {})
        total_relevant = sum(1 for grade in grades.values() if grade >= 1)
        docs = [entry["docid"] for entry in rankings.get(qid, [])]
        hits = [1 if grades.get(docid, 0) >= 1 else 0 for docid in docs]

        p5 = sum(hits[:5]) / 5
        p10 = sum(hits[:10]) / 10
        ap = 0.0
        if total_relevant:
            seen = 0
            for rank, hit in enumerate(hits, start=1):
                if hit:
                    seen += 1
                    ap += seen / rank
            ap /= total_relevant

        dcg = sum(
            grades.get(docid, 0) / math.log2(rank + 1)
            for rank, docid in enumerate(docs[:10], start=1)
        )
        ideal = sorted(grades.values(), reverse=True)[:10]
        idcg = sum(
            grade / math.log2(rank + 1)
            for rank, grade in enumerate(ideal, start=1)
        )
        ndcg = dcg / idcg if idcg else 0.0
        recall = sum(hits) / total_relevant if total_relevant else 0.0
        first = next((rank for rank, hit in enumerate(hits[:10], 1) if hit), None)
        rr = 1 / first if first else 0.0
        per_query[qid] = dict(zip(names, (p5, p10, ap, ndcg, recall, rr)))

    means = {
        name: sum(per_query[qid][name] for qid in common.QIDS) / len(common.QIDS)
        for name in names
    }
    return {"per_query": per_query, "mean": means}


def same_rankings(left: Path, right: Path) -> bool:
    a = {
        qid: [(entry["docid"], entry["score"]) for entry in entries]
        for qid, entries in common.load_trec_run(left).items()
    }
    b = {
        qid: [(entry["docid"], entry["score"]) for entry in entries]
        for qid, entries in common.load_trec_run(right).items()
    }
    return a == b


def print_report(results: dict[str, dict], latencies: dict[str, dict[str, float]]) -> None:
    names = ("P@5", "P@10", "AP", "nDCG@10", "Recall@20", "MRR@10")
    print(f"\n{'system':<14}" + "".join(f"{name:>11}" for name in names))
    for label in ("baseline", "none", "rubric"):
        if label not in results:
            continue
        mean = results[label]["mean"]
        print(f"{label:<14}" + "".join(f"{mean[name]:>11.3f}" for name in names))

    if "baseline" in results and "rubric" in results:
        print("\nPer need (baseline -> rubric):")
        for label, name in (("P@10", "P@10"), ("AP", "AP"),
                            ("nDCG@10", "nDCG@10"), ("Recall@20", "Recall@20")):
            print(f"\n{label}:")
            for qid in common.QIDS:
                before = results["baseline"]["per_query"][qid][name]
                after = results["rubric"]["per_query"][qid][name]
                print(f"  {qid}: {before:.3f} -> {after:.3f} ({after - before:+.3f})")

    print("\nMean latency (ms):")
    for label, values in latencies.items():
        print(f"  {label:<8}: {sum(values.values()) / len(values):.1f}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("none", "rubric", "both"), default="both")
    parser.add_argument("--configs", type=Path, default=CONFIG_DIR)
    parser.add_argument("--runs", type=Path, default=ROOT / "runs")
    parser.add_argument("--baseline", type=Path, default=BASELINE_RUN)
    parser.add_argument("--qrels", type=Path, default=QRELS)
    parser.add_argument("--uri", default=DEFAULT_SOLR_URI)
    parser.add_argument("--collection", default=DEFAULT_COLLECTION)
    parser.add_argument(
        "--write-configs",
        action="store_true",
        help="regenerate queries/rewrites from queries/m3 + eval/common vocabulary",
    )
    args = parser.parse_args()

    if args.write_configs:
        configs = build_configs()
    else:
        configs = load_configs(args.configs)

    result_paths: dict[str, Path] = {}
    latencies: dict[str, dict[str, float]] = {}
    for mode in ("none", "rubric"):
        if args.mode in {mode, "both"}:
            result_paths[mode], latencies[mode] = run_mode(mode, configs, args)

    if "none" in result_paths and args.baseline.exists():
        reproduced = same_rankings(result_paths["none"], args.baseline)
        print(
            "Baseline check: "
            + ("OK - rewrite_none reproduces M3_BASE rankings" if reproduced
               else "WARNING - rewrite_none differs from M3_BASE")
        )

    use_trec_eval = shutil.which("trec_eval") is not None
    qrels = common.load_qrels(args.qrels)
    results: dict[str, dict] = {}
    with tempfile.TemporaryDirectory() as tmp:
        qrels_path = Path(tmp) / "qrels.trec"
        if use_trec_eval:
            write_qrels(qrels, qrels_path)

        def score(path: Path) -> dict:
            if use_trec_eval:
                return evaluate_with_trec_eval(path, qrels_path)
            return evaluate(path, qrels)

        if args.baseline.exists():
            results["baseline"] = score(args.baseline)
        for mode, path in result_paths.items():
            results[mode] = score(path)

    print(
        "Metrics engine: "
        + ("trec_eval v10.0" if use_trec_eval else "local fallback (trec_eval not on PATH)")
    )
    print_report(results, latencies)
    return 0


if __name__ == "__main__":
    sys.exit(main())
