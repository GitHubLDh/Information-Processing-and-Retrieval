#!/usr/bin/env python3
"""Build a judgeable pool of P1 candidates that are not yet in qrels.csv.

The output is separate from the frozen M2 pool and qrels files. P4 can pass it to
``eval/judge.py --pool`` to judge the new candidates, then append the resulting
grades to ``eval/data/qrels.csv``.

Usage:
    python3 scripts/build_p1_pool.py
    python3 scripts/build_p1_pool.py --out eval/data/p1_new_pool.csv
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for candidate in (ROOT, ROOT / "eval"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

import common  # noqa: E402

DEFAULT_RUNS = [
    "M3_BASE",
    "M3_MM2",
    "M3_MM70",
    "M3_BOOST_RW1",
    "M3_BOOST_RW05",
    "M3_JOIN_TOTAL",
    "M3_JOIN_AVG",
    "M3_PF",
    "rewrite_none",
    "rewrite_rubric",
]
FIELDS = [
    "qid",
    "docid",
    "title",
    "year",
    "genres",
    "origin_runs",
    "best_rank",
    "overview",
]


def build_rows(
    run_ids: list[str],
    qrels: dict[str, dict[str, int]],
    collection: dict[str, dict],
) -> list[dict[str, str | int]]:
    candidates: dict[tuple[str, str], dict] = {}

    for run_id in run_ids:
        ranking = common.load_trec_run(common.RUNS_DIR / f"{run_id}.run")
        for qid in common.QIDS:
            judged = qrels.get(qid, {})
            for entry in ranking.get(qid, []):
                docid = str(entry["docid"])
                if docid in judged:
                    continue
                key = (qid, docid)
                origin = f"{run_id}#{entry['rank']}"
                record = candidates.setdefault(
                    key,
                    {"origin_runs": [], "best_rank": entry["rank"]},
                )
                if origin not in record["origin_runs"]:
                    record["origin_runs"].append(origin)
                record["best_rank"] = min(record["best_rank"], entry["rank"])

    rows: list[dict[str, str | int]] = []
    for (qid, docid), record in sorted(
        candidates.items(),
        key=lambda item: (common.QIDS.index(item[0][0]), item[1]["best_rank"], item[0][1]),
    ):
        doc = collection.get(docid, {})
        rows.append(
            {
                "qid": qid,
                "docid": docid,
                "title": doc.get("title", ""),
                "year": doc.get("year", ""),
                "genres": doc.get("genres", ""),
                "origin_runs": "; ".join(record["origin_runs"]),
                "best_rank": record["best_rank"],
                "overview": doc.get("overview", ""),
            }
        )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", nargs="+", default=DEFAULT_RUNS)
    parser.add_argument("--qrels", type=Path, default=common.DEFAULT_QRELS)
    parser.add_argument("--collection", type=Path, default=common.COLLECTION_PATH)
    parser.add_argument("--out", type=Path, default=common.DATA_DIR / "p1_new_pool.csv")
    args = parser.parse_args()

    qrels = common.load_qrels(args.qrels)
    collection = common.load_collection(args.collection)
    rows = build_rows(args.runs, qrels, collection)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    counts = {qid: 0 for qid in common.QIDS}
    for row in rows:
        counts[str(row["qid"])] += 1
    print(f"wrote {args.out} ({len(rows)} unjudged query–movie pairs)")
    print("  " + ", ".join(f"{qid}={counts[qid]}" for qid in common.QIDS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
