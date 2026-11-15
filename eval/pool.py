#!/usr/bin/env python3
"""Build the pooled judgment set from the Setup A and Setup B runs.

Pooling is the standard IR evaluation step that prevents judging only the results
of one system. We take the union of the two top-20 runs per information need,
deduplicate by numeric movie_id, and write:

    eval/pool.csv              machine-readable pooled candidates
    eval/qrels_template.csv    blank relevance sheet (qid, docid, rel, judge, notes)
    eval/evidence.csv          overview + plot/review evidence used for judging
    eval/judging/Q*.md         human-readable evidence sheets

Usage:
    python eval/pool.py
"""

from __future__ import annotations

import csv
from pathlib import Path

import common


def build_pool() -> list[dict]:
    rankings = {setup: common.load_run(setup) for setup in common.SETUPS}
    collection = common.load_collection()

    rows: list[dict] = []
    for qid in common.QIDS:
        by_doc: dict[str, dict] = {}
        for setup in common.SETUPS:
            for entry in rankings.get(setup, {}).get(qid, []):
                docid = entry["docid"]
                row = by_doc.setdefault(docid, {
                    "qid": qid,
                    "docid": docid,
                    "rank_A": "",
                    "rank_B": "",
                    "score_A": "",
                    "score_B": "",
                })
                row[f"rank_{setup}"] = entry["rank"]
                row[f"score_{setup}"] = f"{entry['score']:.6f}"

        for docid, row in by_doc.items():
            record = collection.get(docid, {})
            if not record:
                print(f"warning: {qid}/{docid} is not in the collection")
            row["title"] = record.get("title", "")
            row["year"] = record.get("year", "")
            row["genres"] = record.get("genres", "")
            row["overview"] = common.clean_text(record.get("overview") or "")
            rows.append(row)

    rows.sort(key=lambda row: (
        row["qid"],
        min(
            int(row["rank_A"]) if row["rank_A"] else 10**6,
            int(row["rank_B"]) if row["rank_B"] else 10**6,
        ),
        row["title"],
    ))
    return rows


def default_pool_sort(row: dict) -> tuple:
    return (
        row["qid"],
        min(
            int(row["rank_A"]) if row["rank_A"] else 10**6,
            int(row["rank_B"]) if row["rank_B"] else 10**6,
        ),
        row["title"],
    )


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {path} ({len(rows)} rows)")


def write_evidence(rows: list[dict], collection: dict[str, dict], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    evidence_rows: list[dict] = []
    needs = common.load_all_needs()

    for qid in common.QIDS:
        need = needs[qid]
        qid_rows = [row for row in rows if row["qid"] == qid]
        lines = [
            f"# {qid} — {need['title']}",
            "",
            f"**Need:** {need['need']}",
            "",
            f"**Relevance criteria:** {need['criteria']}",
            "",
            "**Scale:** 2 = highly relevant; 1 = partially relevant / weak or indirect "
            "evidence; 0 = not relevant.",
            "",
            f"Pooled candidates: {len(qid_rows)}.",
            "",
        ]

        for row in qid_rows:
            record = collection.get(row["docid"], {})
            evidence = common.document_evidence(record, qid)
            ranks = []
            if row["rank_A"]:
                ranks.append(f"A #{row['rank_A']}")
            if row["rank_B"]:
                ranks.append(f"B #{row['rank_B']}")
            lines.extend([
                f"## {row['title']} ({row['year']}) — movie_id {row['docid']}",
                "",
                f"Genres: {row['genres'] or 'n/a'} | Pooled ranks: {', '.join(ranks) or 'n/a'}",
                "",
                f"Overview: {evidence['overview'] or 'n/a'}",
                "",
            ])
            if evidence["plot_windows"]:
                lines.append("Plot evidence:")
                lines.extend(f"- {snippet}" for snippet in evidence["plot_windows"])
                lines.append("")
            if evidence["review_windows"]:
                lines.append("Review evidence:")
                lines.extend(f"- {snippet}" for snippet in evidence["review_windows"])
                lines.append("")
            if not evidence["plot_windows"] and not evidence["review_windows"]:
                lines.append("_No query-term evidence found in plot or reviews._")
                lines.append("")

            evidence_rows.append({
                "qid": qid,
                "docid": row["docid"],
                "title": row["title"],
                "year": row["year"],
                "genres": row["genres"],
                "rank_A": row["rank_A"],
                "rank_B": row["rank_B"],
                "matched_plot_terms": "; ".join(evidence["matched_plot_terms"]),
                "matched_review_terms": "; ".join(evidence["matched_review_terms"]),
                "plot_evidence": " || ".join(evidence["plot_windows"]),
                "review_evidence": " || ".join(evidence["review_windows"]),
                "overview": evidence["overview"],
            })

        (out_dir / f"{qid}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"wrote {out_dir / (qid + '.md')} ({len(qid_rows)} candidates)")

    write_csv(
        out_dir.parent / "evidence.csv",
        evidence_rows,
        [
            "qid", "docid", "title", "year", "genres", "rank_A", "rank_B",
            "matched_plot_terms", "matched_review_terms", "plot_evidence",
            "review_evidence", "overview",
        ],
    )


def main() -> None:
    rows = build_pool()
    write_csv(
        common.DEFAULT_POOL,
        rows,
        [
            "qid", "docid", "title", "year", "genres", "rank_A", "rank_B",
            "score_A", "score_B", "overview",
        ],
    )

    qrels_template = common.EVAL_DIR / "qrels_template.csv"
    write_csv(
        qrels_template,
        [dict(row, rel="", judge="", notes="") for row in rows],
        ["qid", "docid", "title", "year", "rel", "judge", "notes"],
    )

    write_evidence(rows, common.load_collection(), common.EVAL_DIR / "judging")

    counts: dict[str, int] = {}
    for row in rows:
        counts[row["qid"]] = counts.get(row["qid"], 0) + 1
    print("pool size per query:", ", ".join(f"{qid}={counts.get(qid, 0)}" for qid in common.QIDS))
    print("total pooled judgments:", len(rows))


if __name__ == "__main__":
    main()
