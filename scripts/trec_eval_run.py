#!/usr/bin/env python3
"""Evaluate arbitrary saved runs with trec_eval v10.0.

Usage:
    python3 scripts/trec_eval_run.py runs/M3_MM2.run runs/M3_MM70.run --per-query
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for candidate in (ROOT, ROOT / "scripts", ROOT / "eval"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

import common  # noqa: E402
import metrics as trec_metrics  # noqa: E402

MEASURES = ("P_5", "P_10", "map", "ndcg_cut_10", "recall_20", "recip_rank")
LABELS = {
    "P_5": "P@5",
    "P_10": "P@10",
    "map": "AP",
    "ndcg_cut_10": "nDCG@10",
    "recall_20": "Recall@20",
    "recip_rank": "MRR@10",
}


def write_qrels(qrels: dict[str, dict[str, int]], path: Path) -> None:
    """Write graded qrels in the TREC format expected by trec_eval."""
    trec_metrics.write_trec_qrels(qrels, path)


def evaluate_run(
    run_path: Path,
    qrels_path: Path,
    threshold: int = 1,
) -> dict:
    """Return per-query and mean official metrics for one TREC run."""
    if not shutil.which("trec_eval"):
        raise RuntimeError("trec_eval is not on PATH")

    base = ["trec_eval", "-q", "-l", str(threshold)]
    first = subprocess.run(
        [*base, "-m", "map", "-m", "P.5,10", "-m", "recall.20",
         "-m", "ndcg_cut.10", str(qrels_path), str(run_path)],
        capture_output=True,
        text=True,
    )
    second = subprocess.run(
        [*base, "-M", "10", "-m", "recip_rank", str(qrels_path), str(run_path)],
        capture_output=True,
        text=True,
    )
    parsed = trec_metrics.parse_trec_eval(first.stdout + second.stdout)
    if not parsed and first.returncode not in (0, 4):
        raise RuntimeError(
            f"trec_eval failed for {run_path}: "
            f"{(first.stderr or second.stderr).strip()}"
        )

    displays = tuple(LABELS[measure] for measure in MEASURES)
    per_query: dict[str, dict[str, float]] = {}
    for qid in common.QIDS:
        per_query[qid] = {
            LABELS[measure]: parsed.get(measure, {}).get(qid, 0.0)
            for measure in MEASURES
        }
    means = {
        name: sum(per_query[qid][name] for qid in common.QIDS) / len(common.QIDS)
        for name in displays
    }
    return {"per_query": per_query, "mean": means, "measures": displays}


def print_table(results: dict[str, dict], label: str, per_query: bool = False) -> None:
    measures = results["measures"]
    print(f"\n{label}")
    print(f"{'system':<18}" + "".join(f"{name:>11}" for name in measures))
    mean = results["mean"]
    print(f"{'mean':<18}" + "".join(f"{mean[name]:>11.3f}" for name in measures))
    if per_query:
        for qid in common.QIDS:
            row = results["per_query"][qid]
            print(f"{qid:<18}" + "".join(f"{row[name]:>11.3f}" for name in measures))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runs", nargs="+", type=Path, help="TREC run files to evaluate")
    parser.add_argument("--qrels", type=Path, default=common.DEFAULT_QRELS)
    parser.add_argument("--threshold", type=int, default=1)
    parser.add_argument(
        "--per-query",
        action="store_true",
        help="print each information need in addition to the mean",
    )
    args = parser.parse_args()

    qrels = common.load_qrels(args.qrels)
    with tempfile.TemporaryDirectory() as tmp:
        qrels_path = Path(tmp) / "qrels.trec"
        write_qrels(qrels, qrels_path)
        for run_path in args.runs:
            results = evaluate_run(run_path, qrels_path, args.threshold)
            print_table(results, str(run_path), args.per_query)
    return 0


if __name__ == "__main__":
    sys.exit(main())
