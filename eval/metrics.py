#!/usr/bin/env python3
"""Compute standard IR metrics for Setup A and Setup B from the pooled qrels.

Metrics are implemented in pure Python so the evaluation has no third-party
dependencies:

    P@5, P@10          binary precision at cutoff (rel >= threshold)
    AP, MAP            average precision / mean average precision
    nDCG@10            graded normalised discounted cumulative gain
    Recall@20          pooled recall at the run depth
    MRR@10             mean reciprocal rank of the first relevant result

Usage:
    python eval/metrics.py
    python eval/metrics.py --qrels eval/qrels.csv --threshold 1
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import shutil
import subprocess
import sys
from pathlib import Path

try:
    import common
except ImportError:  # allows "python -m eval.metrics"
    from . import common


# ---------------------------------------------------------------------------
# Metric primitives
# ---------------------------------------------------------------------------

def is_relevant(rel: int, threshold: int) -> int:
    return 1 if rel >= threshold else 0


def precision_at_k(grades: list[int], k: int, threshold: int) -> float:
    if k <= 0:
        return 0.0
    top = grades[:k]
    return sum(is_relevant(rel, threshold) for rel in top) / k


def average_precision(grades: list[int], total_relevant: int, threshold: int) -> float | None:
    if total_relevant == 0:
        return None
    hits = 0
    precision_sum = 0.0
    for rank, rel in enumerate(grades, start=1):
        if is_relevant(rel, threshold):
            hits += 1
            precision_sum += hits / rank
    return precision_sum / total_relevant


def dcg(grades: list[int], k: int) -> float:
    return sum((2 ** rel - 1) / math.log2(rank + 1) for rank, rel in enumerate(grades[:k], start=1))


def ndcg_at_k(grades: list[int], ideal_grades: list[int], k: int) -> float | None:
    if not any(ideal_grades):
        return None
    ideal = dcg(ideal_grades, k)
    if ideal == 0:
        return None
    return dcg(grades, k) / ideal


def recall_at_k(grades: list[int], total_relevant: int, k: int, threshold: int) -> float | None:
    if total_relevant == 0:
        return None
    hits = sum(is_relevant(rel, threshold) for rel in grades[:k])
    return hits / total_relevant


def reciprocal_rank_at_k(grades: list[int], k: int, threshold: int) -> float | None:
    for rank, rel in enumerate(grades[:k], start=1):
        if is_relevant(rel, threshold):
            return 1.0 / rank
    return 0.0


def pr_points(grades: list[int], total_relevant: int, threshold: int, cutoff: int) -> list[tuple[float, float]]:
    """Precision/recall after each rank, for precision-recall curves."""
    if total_relevant == 0:
        return []
    points: list[tuple[float, float]] = []
    hits = 0
    for rank, rel in enumerate(grades[:cutoff], start=1):
        if is_relevant(rel, threshold):
            hits += 1
        points.append((hits / total_relevant, hits / rank))
    return points


def interpolated_precision(points: list[tuple[float, float]], level: float) -> float:
    """Standard 11-point interpolated precision at a recall level."""
    return max((precision for recall, precision in points if recall >= level), default=0.0)


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

def evaluate_setup(
    rankings: dict[str, list[dict]],
    qrels: dict[str, dict[str, int]],
    threshold: int = 1,
    cutoff: int = 20,
) -> dict[str, dict]:
    results: dict[str, dict] = {}
    for qid in common.QIDS:
        entries = rankings.get(qid, [])
        judged = qrels.get(qid, {})
        grades = [judged.get(entry["docid"], 0) for entry in entries]
        ideal_grades = sorted(judged.values(), reverse=True)
        total_relevant = sum(is_relevant(rel, threshold) for rel in judged.values())
        unjudged = sum(1 for entry in entries[:cutoff] if entry["docid"] not in judged)

        results[qid] = {
            "num_retrieved": len(entries[:cutoff]),
            "num_judged_relevant": total_relevant,
            "num_judged": len(judged),
            "unjudged_retrieved": unjudged,
            "P@5": precision_at_k(grades, 5, threshold),
            "P@10": precision_at_k(grades, 10, threshold),
            "AP": average_precision(grades, total_relevant, threshold),
            "nDCG@10": ndcg_at_k(grades, ideal_grades, 10),
            "Recall@20": recall_at_k(grades, total_relevant, cutoff, threshold),
            "MRR@10": reciprocal_rank_at_k(grades, 10, threshold),
            "_pr_points": pr_points(grades, total_relevant, threshold, cutoff),
        }

    if not any(results[qid]["num_judged_relevant"] for qid in common.QIDS):
        print("warning: no relevant documents in the qrels; metrics are undefined")

    return results


def mean_metric(results: dict[str, dict], metric: str) -> float | None:
    values = [results[qid][metric] for qid in common.QIDS if results[qid].get(metric) is not None]
    return sum(values) / len(values) if values else None


def fmt(value: float | None, digits: int = 3) -> str:
    return "n/a" if value is None else f"{value:.{digits}f}"


def fmt_delta(value: float | None, digits: int = 3) -> str:
    return "n/a" if value is None else f"{value:+.{digits}f}"


def write_results(
    all_results: dict[str, dict[str, dict]],
    qrels: dict[str, dict[str, int]],
    out_dir: Path,
    threshold: int,
    cutoff: int,
) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    needs = common.load_all_needs()

    rows = []
    for setup in common.SETUPS:
        for qid in common.QIDS:
            row = {"setup": setup, "qid": qid, "need": needs[qid]["title"]}
            row.update({key: value for key, value in all_results[setup][qid].items() if not key.startswith("_")})
            rows.append(row)

    results_csv = out_dir / "results.csv"
    with results_csv.open("w", newline="", encoding="utf-8") as handle:
        import csv
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {results_csv}")

    aggregate = {
        setup: {metric: mean_metric(all_results[setup], metric) for metric in (
            "P@5", "P@10", "AP", "nDCG@10", "Recall@20", "MRR@10"
        )}
        for setup in common.SETUPS
    }

    # JSON summary, also useful for the report and for later milestones.
    payload = {
        "threshold": threshold,
        "cutoff": cutoff,
        "aggregate": aggregate,
        "per_query": {
            setup: {
                qid: {key: value for key, value in all_results[setup][qid].items() if not key.startswith("_")}
                for qid in common.QIDS
            }
            for setup in common.SETUPS
        },
        "qrels_summary": {
            qid: {
                "judged": len(qrels.get(qid, {})),
                "relevant": sum(is_relevant(rel, threshold) for rel in qrels.get(qid, {}).values()),
                "grade_0": sum(1 for rel in qrels.get(qid, {}).values() if rel == 0),
                "grade_1": sum(1 for rel in qrels.get(qid, {}).values() if rel == 1),
                "grade_2": sum(1 for rel in qrels.get(qid, {}).values() if rel == 2),
            }
            for qid in common.QIDS
        },
    }
    (out_dir / "results.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    # Markdown report.
    lines = [
        "# Evaluation results",
        "",
        f"Relevance threshold: rel >= {threshold}. Run depth: {cutoff}. "
        "Unjudged retrieved documents count as non-relevant.",
        "",
        "## Judgment summary",
        "",
        "| Qid | Need | Judged | Relevant (rel>=%d) | rel=2 | rel=1 | rel=0 |" % threshold,
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for qid in common.QIDS:
        summary = payload["qrels_summary"][qid]
        lines.append(
            f"| {qid} | {needs[qid]['title']} | {summary['judged']} | {summary['relevant']} | "
            f"{summary['grade_2']} | {summary['grade_1']} | {summary['grade_0']} |"
        )

    lines.extend([
        "",
        "## Aggregate metrics",
        "",
        "| Setup | P@5 | P@10 | MAP | nDCG@10 | Recall@20 | MRR@10 |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ])
    for setup in common.SETUPS:
        lines.append(
            f"| {setup} | " + " | ".join(fmt(aggregate[setup][metric]) for metric in (
                "P@5", "P@10", "AP", "nDCG@10", "Recall@20", "MRR@10"
            )) + " |"
        )
    lines.extend([
        "",
        "| Delta (B - A) | P@5 | P@10 | MAP | nDCG@10 | Recall@20 | MRR@10 |",
        "|---:|---:|---:|---:|---:|---:|---:|",
        "| Delta | " + " | ".join(
            fmt_delta(aggregate["B"][metric] - aggregate["A"][metric])
            if aggregate["A"][metric] is not None and aggregate["B"][metric] is not None else "n/a"
            for metric in ("P@5", "P@10", "AP", "nDCG@10", "Recall@20", "MRR@10")
        ) + " |",
        "",
        "## Per-query metrics",
        "",
        "| Qid | Setup | Ret. | Judged rel. | P@10 | AP | nDCG@10 | Recall@20 | Unjudged |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for qid in common.QIDS:
        for setup in common.SETUPS:
            item = all_results[setup][qid]
            lines.append(
                f"| {qid} | {setup} | {item['num_retrieved']} | {item['num_judged_relevant']} | "
                f"{fmt(item['P@10'])} | {fmt(item['AP'])} | {fmt(item['nDCG@10'])} | "
                f"{fmt(item['Recall@20'])} | {item['unjudged_retrieved']} |"
            )
        a = all_results["A"][qid]
        b = all_results["B"][qid]
        lines.append(
            f"| {qid} | Delta B-A | | | "
            f"{fmt_delta(b['P@10'] - a['P@10'])} | "
            f"{fmt_delta(b['AP'] - a['AP']) if b['AP'] is not None and a['AP'] is not None else 'n/a'} | "
            f"{fmt_delta(b['nDCG@10'] - a['nDCG@10']) if b['nDCG@10'] is not None and a['nDCG@10'] is not None else 'n/a'} | "
            f"{fmt_delta(b['Recall@20'] - a['Recall@20']) if b['Recall@20'] is not None and a['Recall@20'] is not None else 'n/a'} | |"
        )

    lines.extend([
        "",
        "## Notes",
        "",
        f"- `P@10` uses binary relevance (rel >= {threshold}); `nDCG@10` uses the graded 0/1/2 scale.",
        "- AP, nDCG, recall and MRR are undefined for a query with no relevant judged document; "
        "those queries are excluded from the corresponding mean.",
        "- Judgments cover the pooled top-20 of both systems. Any retrieved but unjudged document is "
        "treated as non-relevant, as in standard pooled IR evaluation.",
        "- Five queries are a small sample: differences are descriptive, not statistically tested.",
        "",
    ])
    (out_dir / "results.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {out_dir / 'results.md'}")

    write_latex_tables(aggregate, all_results, needs, out_dir, threshold)
    write_pr_curve(all_results, qrels, out_dir, threshold, cutoff)
    return payload


def write_latex_tables(
    aggregate: dict,
    all_results: dict[str, dict[str, dict]],
    needs: dict,
    out_dir: Path,
    threshold: int,
) -> None:
    metrics = ("P@5", "P@10", "AP", "nDCG@10", "Recall@20")
    lines = [
        "% Generated by eval/metrics.py -- do not edit by hand.",
        "\\begin{table}[t]",
        "\\centering",
        "\\caption{Aggregate evaluation over the five pooled information needs. "
        f"Binary metrics use rel~$\\geq$~{threshold}; nDCG uses grades 0--2.}}",
        "\\label{tab:evaluation-aggregate}",
        "\\small",
        "\\begin{tabular}{lrrrrr}",
        "\\hline",
        "Setup & P@5 & P@10 & MAP & nDCG@10 & Recall@20 \\\\",
        "\\hline",
    ]
    for setup in common.SETUPS:
        lines.append(
            f"{setup} & " + " & ".join(fmt(aggregate[setup][metric]) for metric in metrics) + " \\\\"
        )
    lines.extend([
        "\\hline",
        "\\end{tabular}",
        "\\end{table}",
        "",
    ])
    (out_dir / "results_table.tex").write_text("\n".join(lines), encoding="utf-8")

    lines = [
        "% Generated by eval/metrics.py -- do not edit by hand.",
        "\\begin{table}[t]",
        "\\centering",
        "\\caption{Per-query results for Setup A and Setup B.}",
        "\\label{tab:evaluation-per-query}",
        "\\small",
        "\\begin{tabular}{llrrrr}",
        "\\hline",
        "Qid & Setup & P@10 & AP & nDCG@10 & Recall@20 \\\\",
        "\\hline",
    ]
    for qid in common.QIDS:
        for setup in common.SETUPS:
            item = all_results[setup][qid]
            lines.append(
                f"{qid} & {setup} & {fmt(item['P@10'])} & {fmt(item['AP'])} & "
                f"{fmt(item['nDCG@10'])} & {fmt(item['Recall@20'])} \\\\"
            )
        lines.append("\\hline")
    lines.extend(["\\end{tabular}", "\\end{table}", ""])
    (out_dir / "results_per_query_table.tex").write_text("\n".join(lines), encoding="utf-8")

    lines = [
        "% Generated by eval/metrics.py -- do not edit by hand.",
        "\\begin{table}[t]",
        "\\centering",
        "\\caption{Per-need comparison of Setup A and Setup B.}",
        "\\label{tab:evaluation-per-query}",
        "\\small",
        "\\begin{tabular}{lrrrrrr}",
        "\\hline",
        " & \\multicolumn{2}{c}{P@10} & \\multicolumn{2}{c}{nDCG@10} & \\multicolumn{2}{c}{Recall@20} \\\\",
        "Qid & A & B & A & B & A & B \\\\",
        "\\hline",
    ]
    for qid in common.QIDS:
        a = all_results["A"][qid]
        b = all_results["B"][qid]
        lines.append(
            f"{qid} & {fmt(a['P@10'])} & {fmt(b['P@10'])} & "
            f"{fmt(a['nDCG@10'])} & {fmt(b['nDCG@10'])} & "
            f"{fmt(a['Recall@20'])} & {fmt(b['Recall@20'])} \\\\"
        )
    lines.extend(["\\hline", "\\end{tabular}", "\\end{table}", ""])
    (out_dir / "results_compact_table.tex").write_text("\n".join(lines), encoding="utf-8")


def write_pr_curve(
    all_results: dict[str, dict[str, dict]],
    qrels: dict[str, dict[str, int]],
    out_dir: Path,
    threshold: int,
    cutoff: int,
) -> None:
    import csv

    rows = []
    for setup in common.SETUPS:
        for qid in common.QIDS:
            points = all_results[setup][qid]["_pr_points"]
            for index, (recall, precision) in enumerate(points, start=1):
                rows.append({
                    "setup": setup,
                    "qid": qid,
                    "rank": index,
                    "recall": f"{recall:.6f}",
                    "precision": f"{precision:.6f}",
                })
    pr_csv = out_dir / "pr_curve.csv"
    with pr_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["setup", "qid", "rank", "recall", "precision"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {pr_csv}")

    levels = [index / 10 for index in range(11)]
    mean_curves = {}
    mean_rows = []
    for setup in common.SETUPS:
        precisions = []
        for level in levels:
            query_values = []
            for qid in common.QIDS:
                points = all_results[setup][qid]["_pr_points"]
                if points:
                    query_values.append(interpolated_precision(points, level))
            precisions.append(sum(query_values) / len(query_values) if query_values else 0.0)
        mean_curves[setup] = precisions
        for level, precision in zip(levels, precisions):
            mean_rows.append({"setup": setup, "recall": f"{level:.1f}", "precision": f"{precision:.6f}"})

    mean_csv = out_dir / "pr_curve_mean.csv"
    with mean_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["setup", "recall", "precision"])
        writer.writeheader()
        writer.writerows(mean_rows)
    print(f"wrote {mean_csv}")

    colors = {"A": "blue", "B": "red"}
    lines = [
        "\\documentclass[border=4pt]{standalone}",
        "\\usepackage{pgfplots}",
        "\\pgfplotsset{compat=1.18}",
        "\\begin{document}",
        "\\begin{tikzpicture}",
        "\\begin{axis}[",
        "  width=8.5cm, height=6.2cm,",
        "  xlabel={Recall}, ylabel={Interpolated precision},",
        "  xmin=0, xmax=1, ymin=0, ymax=1,",
        "  grid=major,",
        "  legend pos=south west,",
        "  legend style={font=\\small},",
        "]",
    ]
    for setup in common.SETUPS:
        coords = " ".join(f"({level:.1f},{value:.4f})" for level, value in zip(levels, mean_curves[setup]))
        lines.append(f"\\addplot+[mark=*, thick, color={colors[setup]}] coordinates {{{coords}}};")
        lines.append(f"\\addlegendentry{{Setup {setup}}}")
    lines.extend([
        "\\end{axis}",
        "\\end{tikzpicture}",
        "\\end{document}",
        "",
    ])
    tex_path = out_dir / "pr_curve.tex"
    tex_path.write_text("\n".join(lines), encoding="utf-8")

    if shutil.which("pdflatex"):
        process = subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", tex_path.name],
            cwd=out_dir,
            capture_output=True,
            text=True,
        )
        if process.returncode != 0:
            print("warning: could not compile pr_curve.tex with pdflatex")
            print(process.stdout[-1200:])
        else:
            pdf_path = out_dir / "pr_curve.pdf"
            print(f"wrote {pdf_path}")
            figures = common.ROOT / "report" / "figures"
            if figures.exists():
                shutil.copyfile(pdf_path, figures / "pr_curve.pdf")
                print(f"wrote {figures / 'pr_curve.pdf'}")
            for suffix in (".aux", ".log"):
                aux = out_dir / f"pr_curve{suffix}"
                if aux.exists():
                    aux.unlink()


def warn_if_not_manual(path: Path) -> None:
    """Warn when the qrels still contain non-manual (e.g. seeded) judgments."""
    non_manual = 0
    total = 0
    with Path(path).open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if not (row.get("rel") or "").strip():
                continue
            total += 1
            if (row.get("judge") or "").strip().lower() != "manual":
                non_manual += 1
    if non_manual:
        print(
            f"warning: {non_manual}/{total} judgments in {path} are not marked judge=manual; "
            "the results are preliminary until the pool is manually verified.",
            file=sys.stderr,
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--qrels", type=Path, default=common.DEFAULT_QRELS)
    parser.add_argument("--runs-dir", type=Path, default=common.RUNS_DIR)
    parser.add_argument("--out-dir", type=Path, default=common.EVAL_DIR)
    parser.add_argument("--threshold", type=int, default=1, choices=[1, 2],
                        help="minimum grade counted as relevant for binary metrics")
    parser.add_argument("--cutoff", type=int, default=20)
    args = parser.parse_args()

    if not args.qrels.exists():
        raise SystemExit(
            f"qrels file {args.qrels} does not exist. Run eval/pool.py and judge the pool first."
        )

    qrels = common.load_qrels(args.qrels)
    if not qrels:
        raise SystemExit(f"{args.qrels} contains no judgments")
    warn_if_not_manual(args.qrels)

    all_results = {
        setup: evaluate_setup(common.load_run(setup, args.runs_dir), qrels, args.threshold, args.cutoff)
        for setup in common.SETUPS
    }
    write_results(all_results, qrels, args.out_dir, args.threshold, args.cutoff)


if __name__ == "__main__":
    main()
