#!/usr/bin/env python3
"""Interactive relevance-judging helper for the pooled evaluation set.

The tool shows one pooled movie at a time with the overview, plot context, and
matching review snippets. Judgments are written to eval/qrels.csv immediately, so
the session can be stopped and resumed.

Usage:
    python eval/judge.py --judge "Your name"
    python eval/judge.py --judge "Your name" --qid Q1
    python eval/judge.py --judge "Your name" --qid Q1 --review

Grade 2 = highly relevant, 1 = partially relevant, 0 = not relevant.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

try:
    import common
except ImportError:
    from . import common


HELP = """
Grades: 2 = highly relevant | 1 = partially relevant | 0 = not relevant
Commands: s = skip | p = previous | q = save and quit | ? = help
Press Enter after a grade to keep an existing judgment when reviewing.
""".strip()


def load_pool(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return list(reader)


def load_qrels_rows(path: Path) -> dict[tuple[str, str], dict]:
    if not path.exists():
        return {}
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return {
            (row["qid"].strip(), str(row["docid"]).strip()): row
            for row in reader
        }


def save_qrels(path: Path, pool_rows: list[dict], qrels: dict[tuple[str, str], dict]) -> None:
    fieldnames = ["qid", "docid", "title", "year", "rel", "judge", "notes"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        seen: set[tuple[str, str]] = set()
        for row in pool_rows:
            key = (row["qid"], str(row["docid"]))
            seen.add(key)
            merged = dict(row)
            merged.update(qrels.get(key, {}))
            writer.writerow(merged)
        for key, row in qrels.items():
            if key not in seen:
                writer.writerow(row)


def show_candidate(qid: str, row: dict, collection: dict[str, dict]) -> None:
    need = common.INFORMATION_NEEDS[qid]
    record = collection.get(str(row["docid"]), {})
    evidence = common.document_evidence(record, qid)

    ranks = []
    if row.get("rank_A"):
        ranks.append(f"A #{row['rank_A']}")
    if row.get("rank_B"):
        ranks.append(f"B #{row['rank_B']}")

    print("\n" + "-" * 78)
    print(f"{qid} — {need['title']}")
    print(f"{row['title']} ({row.get('year', '?')}) — movie_id {row['docid']}")
    print(f"Genres: {row.get('genres') or 'n/a'} | Pooled ranks: {', '.join(ranks) or 'n/a'}")
    print(f"\nOverview: {evidence['overview'] or 'n/a'}")
    if evidence["plot_windows"]:
        print("\nPlot evidence:")
        for snippet in evidence["plot_windows"]:
            print(f"  - {snippet}")
    if evidence["review_windows"]:
        print("\nReview evidence:")
        for snippet in evidence["review_windows"]:
            print(f"  - {snippet}")
    if not evidence["plot_windows"] and not evidence["review_windows"]:
        print("\nNo query-term evidence found in the plot or reviews.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--judge", default="judge", help="name recorded in the qrels")
    parser.add_argument("--qid", default=None, choices=common.QIDS, help="judge one need")
    parser.add_argument("--pool", type=Path, default=common.DEFAULT_POOL)
    parser.add_argument("--qrels", type=Path, default=common.DEFAULT_QRELS)
    parser.add_argument("--review", action="store_true", help="revisit already judged documents")
    args = parser.parse_args()

    if not args.pool.exists():
        raise SystemExit(f"{args.pool} does not exist; run eval/pool.py first")

    pool_rows = load_pool(args.pool)
    qrels = load_qrels_rows(args.qrels)
    collection = common.load_collection()
    qids = [args.qid] if args.qid else common.QIDS

    print(HELP)
    for qid in qids:
        rows = [row for row in pool_rows if row["qid"] == qid]
        need = common.INFORMATION_NEEDS[qid]
        print("\n" + "=" * 78)
        print(f"{qid} — {need['title']}")
        print(f"Need: {need['need']}")
        print(f"Criteria: {need['criteria']}")

        index = 0
        while index < len(rows):
            row = rows[index]
            key = (qid, str(row["docid"]))
            existing = qrels.get(key, {})
            current = (existing.get("rel") or "").strip()
            if current and not args.review:
                index += 1
                continue

            show_candidate(qid, row, collection)
            if current:
                print(f"\nCurrent judgment: {current} (judge: {existing.get('judge') or 'n/a'})")
            print(f"\nCandidate {index + 1}/{len(rows)}")
            answer = input("Grade (0/1/2, s=skip, p=previous, q=quit, ?=help): ").strip().lower()

            if answer == "?":
                print(HELP)
                continue
            if answer == "q":
                save_qrels(args.qrels, pool_rows, qrels)
                print(f"\nsaved {args.qrels}")
                return
            if answer == "s":
                index += 1
                continue
            if answer == "p":
                index = max(0, index - 1)
                continue
            if answer == "" and current:
                index += 1
                continue
            if answer in {"0", "1", "2"}:
                qrels[key] = {
                    "qid": qid,
                    "docid": str(row["docid"]),
                    "title": row["title"],
                    "year": row.get("year", ""),
                    "rel": answer,
                    "judge": args.judge,
                    "notes": existing.get("notes", ""),
                }
                save_qrels(args.qrels, pool_rows, qrels)
                index += 1
                continue
            print("Unrecognised input. Enter 0, 1, 2, s, p, q, or ?.")

    save_qrels(args.qrels, pool_rows, qrels)
    judged = sum(1 for qid in common.QIDS for row in pool_rows if row["qid"] == qid
                 and (row["qid"], str(row["docid"])) in qrels and qrels[(row["qid"], str(row["docid"]))].get("rel"))
    total = len(pool_rows)
    print(f"\nsaved {args.qrels}: {judged}/{total} pooled documents judged")


if __name__ == "__main__":
    main()
