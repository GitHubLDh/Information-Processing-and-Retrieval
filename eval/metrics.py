#!/usr/bin/env python3
"""Compute official IR metrics for Setup A and Setup B with trec_eval.

The script converts the graded qrels to the TREC qrels format, converts each
run with its raw Solr scores (matching the tutorial's solr_to_trec.py), and
calls trec_eval for:

    P@5, P@10          binary precision at cutoff (rel >= threshold)
    AP, MAP            average precision / mean average precision
    nDCG@10            graded normalised discounted cumulative gain (trec_eval
                       gain = qrel grade)
    Recall@20          pooled recall at the run depth
    MRR@10             mean reciprocal rank of the first relevant result
    PR curve           trec_eval iprec_at_recall_* and 11pt_avg

trec_eval must be installed and available on PATH.

Usage:
    python eval/metrics.py
    python eval/metrics.py --qrels eval/data/qrels.csv --threshold 1
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    import common
except ImportError:  # allows "python -m eval.metrics"
    from . import common


# ---------------------------------------------------------------------------
# Helpers for the trec_eval engine
# ---------------------------------------------------------------------------

PR_LEVELS = [index / 10 for index in range(11)]
PR_MEASURES = [f"iprec_at_recall_{level:.2f}" for level in PR_LEVELS]


def is_relevant(rel: int, threshold: int) -> int:
    return 1 if rel >= threshold else 0


def write_trec_qrels(qrels: dict[str, dict[str, int]], path: Path) -> None:
    """Write the graded qrels in the TREC format: qid 0 docid rel."""
    with path.open("w", encoding="utf-8") as handle:
        for qid in common.QIDS:
            for docid, rel in sorted(qrels.get(qid, {}).items()):
                handle.write(f"{qid} 0 {docid} {rel}\n")


def write_trec_run(rankings: dict[str, list[dict]], setup: str, path: Path) -> None:
    """Write a run in TREC format, matching the tutorial's solr_to_trec.py."""
    with path.open("w", encoding="utf-8") as handle:
        for qid in common.QIDS:
            entries = sorted(rankings.get(qid, []), key=lambda item: item["rank"])
            for rank, entry in enumerate(entries, start=1):
                handle.write(
                    f"{qid} Q0 {entry['docid']} {rank} {entry['score']} {setup}\n"
                )


def parse_trec_eval(output: str) -> dict[str, dict[str, float]]:
    """Parse trec_eval's ``measure qid value`` lines into a nested dict."""
    parsed: dict[str, dict[str, float]] = {}
    for line in output.splitlines():
        parts = line.split()
        if len(parts) < 3:
            continue
        measure, qid, value = parts[0], parts[1], parts[2]
        try:
            parsed.setdefault(measure, {})[qid] = float(value)
        except ValueError:
            continue
    return parsed


def call_trec_eval(
    trec_eval: str,
    qrels_path: Path,
    run_path: Path,
    measure_args: list[str],
) -> dict[str, dict[str, float]]:
    """Run trec_eval with per-query output and return the parsed measures."""
    command = [trec_eval, "-q", *measure_args, str(qrels_path), str(run_path)]
    process = subprocess.run(command, capture_output=True, text=True)
    if process.returncode != 0:
        raise SystemExit(
            "trec_eval failed:\n" + (process.stderr or process.stdout).strip()
        )
    return parse_trec_eval(process.stdout)


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

def evaluate_setup(
    rankings: dict[str, list[dict]],
    qrels: dict[str, dict[str, int]],
    trec_eval: str,
    qrels_path: Path,
    run_path: Path,
    threshold: int = 1,
    cutoff: int = 20,
) -> dict[str, dict]:
    binary = call_trec_eval(
        trec_eval,
        qrels_path,
        run_path,
        [
            "-l", str(threshold),
            "-m", "map",
            "-m", "P.5,10",
            "-m", "recall.20",
            "-m", "iprec_at_recall",
            "-m", "11pt_avg",
        ],
    )
    graded = call_trec_eval(
        trec_eval,
        qrels_path,
        run_path,
        ["-m", "ndcg_cut.10"],
    )
    mrr = call_trec_eval(
        trec_eval,
        qrels_path,
        run_path,
        ["-l", str(threshold), "-M", "10", "-m", "recip_rank"],
    )

    results: dict[str, dict] = {}
    for qid in common.QIDS:
        entries = rankings.get(qid, [])
        judged = qrels.get(qid, {})
        grades = [judged.get(entry["docid"], 0) for entry in entries]
        total_relevant = sum(is_relevant(rel, threshold) for rel in judged.values())
        unjudged = sum(1 for entry in entries[:cutoff] if entry["docid"] not in judged)

        results[qid] = {
            "num_retrieved": len(entries[:cutoff]),
            "num_relevant_retrieved": sum(
                is_relevant(rel, threshold) for rel in grades[:cutoff]
            ),
            "num_judged_relevant": total_relevant,
            "num_judged": len(judged),
            "unjudged_retrieved": unjudged,
            "P@5": binary.get("P_5", {}).get(qid, 0.0),
            "P@10": binary.get("P_10", {}).get(qid, 0.0),
            "AP": binary.get("map", {}).get(qid) if total_relevant else None,
            "nDCG@10": graded.get("ndcg_cut_10", {}).get(qid) if any(judged.values()) else None,
            "Recall@20": binary.get("recall_20", {}).get(qid) if total_relevant else None,
            "MRR@10": mrr.get("recip_rank", {}).get(qid),
            "_auc": binary.get("11pt_avg", {}).get(qid),
            "_iprec": [binary.get(measure, {}).get(qid, 0.0) for measure in PR_MEASURES],
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
        "| Qid | Setup | Ret. | Relevant retrieved / pooled relevant | P@10 | AP | nDCG@10 | Recall@20 | Unjudged |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for qid in common.QIDS:
        for setup in common.SETUPS:
            item = all_results[setup][qid]
            lines.append(
                f"| {qid} | {setup} | {item['num_retrieved']} | "
                f"{item['num_relevant_retrieved']} / {item['num_judged_relevant']} | "
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
        "## Metric definitions and how the values were obtained",
        "",
        "All values are computed with `trec_eval` by `eval/metrics.py`. The script",
        "converts the graded judgments in `eval/data/qrels.csv` to the TREC qrels format",
        "(`qid 0 docid rel`) and the saved runs (`runs/A_Q1.json`--`runs/A_Q5.json`",
        "and `runs/B_Q1.json`--`runs/B_Q5.json`) to the TREC run format, using the",
        "numeric `movie_id` as the document id. Following the tutorial's",
        "`solr_to_trec.py`, the converted runs keep each Solr score; trec_eval sorts",
        "by score, so equal scores are resolved by trec_eval's own tie-breaking and",
        "not by the saved rank column. The script then calls trec_eval with `-q` to get",
        f"per-query and aggregate values. Binary metrics use `-l {threshold}`, so a",
        "movie counts as relevant when its grade is at least that value; the nDCG",
        "measure uses the full 0/1/2 grades. Aggregate rows are unweighted means over",
        "the five queries, so each information need contributes equally regardless of",
        "how many candidates it has. Per-query rows show the same values before",
        "averaging; delta rows are Setup B minus Setup A.",
        "",
        f"- **P@5 / P@10 (precision at 5 and 10).** The fraction of the first 5 or 10",
        f"  results that are relevant: `(relevant results in the top k) / k`. The",
        "  divisor is always `k`, so if a setup returned fewer than `k` movies (for",
        "  example, Setup A returns only 7 for Q4), the missing positions count as",
        "  non-relevant. Obtained from trec_eval's `P.5` and `P.10` measures, then",
        "  averaged over queries in the aggregate table.",
        f"- **AP / MAP (average precision and mean average precision).** AP walks the",
        "  ranked list and averages the precision at every rank where a relevant movie",
        "  occurs, divided by the total number of judged-relevant movies for that query:",
        "  `AP = (1 / R) * sum over relevant ranks i of (hits_i / rank_i)`, where",
        "  `hits_i` is the number of relevant movies seen up to rank `i` and `R` is the",
        "  per-query pooled relevant count shown in the judgment summary and in the",
        "  `Relevant retrieved / pooled relevant` column. Relevant movies that were",
        "  not retrieved within the run depth remain in `R`, so they lower AP. MAP is",
        "  the unweighted mean of AP over the five queries. Obtained from trec_eval's",
        "  `map` measure; AP and MAP are undefined for a query with no relevant judged",
        "  movie and are excluded from that mean.",
        "- **nDCG@10 (normalised discounted cumulative gain at 10).** Uses the graded",
        "  labels, so a grade-2 movie contributes more than a grade-1 movie. trec_eval's",
        "  `ndcg_cut` uses the qrel grade directly as the gain:",
        "  `DCG@10 = sum over the first 10 ranks of rel / log2(rank + 1)`.",
        "  The ideal DCG (`IDCG@10`) is computed by sorting all judged grades for that",
        "  query in descending order and applying the same formula to the top 10;",
        "  `nDCG@10 = DCG@10 / IDCG@10`. The value is 1 when the top 10 follows the",
        "  best possible graded ordering. Obtained from trec_eval's `ndcg_cut.10`, then",
        "  averaged over queries in the aggregate table.",
        "- **Recall@20 (pooled recall at 20).** The fraction of the pooled relevant",
        "  movies found in the top 20: `(relevant movies in the top 20) / (total",
        "  judged-relevant movies in the pool)`. The denominator is the pooled",
        "  judged-relevant set, not every relevant movie in the 6,104-document",
        "  collection, so this is pooled recall rather than absolute collection",
        "  recall. Obtained from trec_eval's `recall.20` measure, then averaged over",
        "  queries in the aggregate table.",
        "- **MRR@10 (mean reciprocal rank at 10).** The reciprocal of the rank of the",
        "  first relevant movie within the top 10 (`1 / rank`), or 0 if no relevant",
        "  movie occurs in the top 10. MRR@10 is the mean of this value over the five",
        "  queries. It measures how early the first relevant hit appears and ignores",
        "  the rest of the ranking. Obtained from trec_eval's `recip_rank` measure run",
        "  with `-M 10`, which truncates each ranking before evaluation.",
        "",
        "## Notes",
        "",
        "- Reported values are trec_eval measures (`map`, `P.5,10`, `ndcg_cut.10`, "
        "`recall.20`, and `recip_rank` with `-M 10`).",
        f"- `P@5`, `P@10`, `AP`, `Recall@20` and `MRR@10` use binary relevance",
        f"  (rel >= {threshold}); `nDCG@10` uses the graded 0/1/2 scale.",
        "- AP, nDCG, recall and MRR are undefined for a query with no relevant judged document; "
        "those queries are excluded from the corresponding mean.",
        "- Judgments cover the pooled top-20 of both systems. Any retrieved but unjudged document is "
        "treated as non-relevant, as in standard pooled IR evaluation; the `Unjudged` column is 0 "
        "for every query and setup here.",
        "- The precision-recall values are trec_eval's `iprec_at_recall_0.00` through "
        "`iprec_at_recall_1.00` measures, with `11pt_avg` as the area under the curve (AUC). "
        "The mean curve averages each of the 11 recall levels across the five queries.",
        "- `pr_curve_A.pdf` and `pr_curve_B.pdf` plot the five per-query curves for each setup "
        "in the style of the tutorial's `plot_pr_curve.py`; `pr_curve.pdf` is the mean curve "
        "used in the report.",
        "- Five queries are a small sample: differences are descriptive, not statistically tested.",
        "",
    ])
    (out_dir / "results.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {out_dir / 'results.md'}")

    write_latex_tables(aggregate, all_results, needs, out_dir, threshold)
    write_pr_curve(all_results, out_dir)
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


def compile_standalone(tex_path: Path, out_dir: Path) -> Path | None:
    """Compile a standalone pgfplots document and return the PDF path."""
    if not shutil.which("pdflatex"):
        return None
    process = subprocess.run(
        ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", tex_path.name],
        cwd=out_dir,
        capture_output=True,
        text=True,
    )
    if process.returncode != 0:
        print(f"warning: could not compile {tex_path.name} with pdflatex")
        print(process.stdout[-1200:])
        return None
    for suffix in (".aux", ".log"):
        aux = out_dir / f"{tex_path.stem}{suffix}"
        if aux.exists():
            aux.unlink()
    return tex_path.with_suffix(".pdf")


def write_pr_curve(
    all_results: dict[str, dict[str, dict]],
    out_dir: Path,
) -> None:
    import csv

    # Per-query values come directly from trec_eval's iprec_at_recall_* measures,
    # matching the tutorial's plot_pr_curve.py.
    rows = []
    for setup in common.SETUPS:
        for qid in common.QIDS:
            for level, precision in zip(PR_LEVELS, all_results[setup][qid]["_iprec"]):
                rows.append({
                    "setup": setup,
                    "qid": qid,
                    "recall": f"{level:.1f}",
                    "precision": f"{precision:.6f}",
                })
    pr_csv = out_dir / "pr_curve.csv"
    with pr_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["setup", "qid", "recall", "precision"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {pr_csv}")

    mean_curves: dict[str, list[float]] = {}
    mean_rows = []
    for setup in common.SETUPS:
        precisions = [
            sum(all_results[setup][qid]["_iprec"][index] for qid in common.QIDS)
            / len(common.QIDS)
            for index in range(len(PR_LEVELS))
        ]
        mean_curves[setup] = precisions
        for level, precision in zip(PR_LEVELS, precisions):
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
        coords = " ".join(f"({level:.1f},{value:.4f})" for level, value in zip(PR_LEVELS, mean_curves[setup]))
        lines.append(f"\\addplot+[const plot, mark=*, thick, color={colors[setup]}] coordinates {{{coords}}};")
        lines.append(f"\\addlegendentry{{Setup {setup}}}")
    lines.extend([
        "\\end{axis}",
        "\\end{tikzpicture}",
        "\\end{document}",
        "",
    ])
    tex_path = out_dir / "pr_curve.tex"
    tex_path.write_text("\n".join(lines), encoding="utf-8")
    pdf_path = compile_standalone(tex_path, out_dir)
    figures = common.ROOT / "report" / "figures"
    if pdf_path:
        print(f"wrote {pdf_path}")
        if figures.exists():
            shutil.copyfile(pdf_path, figures / "pr_curve.pdf")
            print(f"wrote {figures / 'pr_curve.pdf'}")

    # Per-query plots in the same style as the tutorial's plot_pr_curve.py.
    for setup in common.SETUPS:
        lines = [
            "\\documentclass[border=4pt]{standalone}",
            "\\usepackage{pgfplots}",
            "\\pgfplotsset{compat=1.18}",
            "\\begin{document}",
            "\\begin{tikzpicture}",
            "\\begin{axis}[",
            "  width=8.5cm, height=6.2cm,",
            "  xlabel={Recall}, ylabel={Precision},",
            "  xmin=0, xmax=1, ymin=0, ymax=1,",
            "  grid=major,",
            "  legend pos=south west,",
            "  legend style={font=\\tiny},",
            f"  title={{Precision-Recall Curve (Setup {setup})}},",
            "]",
        ]
        for qid in common.QIDS:
            item = all_results[setup][qid]
            coords = " ".join(
                f"({level:.1f},{value:.4f})"
                for level, value in zip(PR_LEVELS, item["_iprec"])
            )
            label = (
                f"Q{int(qid[1:])}: AP={fmt(item['AP'])}, "
                f"AUC={fmt(item['_auc'])}, P@10={fmt(item['P@10'])}"
            )
            lines.append(f"\\addplot+[const plot, mark=*, thick] coordinates {{{coords}}};")
            lines.append(f"\\addlegendentry{{{label}}}")
        lines.extend([
            "\\end{axis}",
            "\\end{tikzpicture}",
            "\\end{document}",
            "",
        ])
        query_tex = out_dir / f"pr_curve_{setup}.tex"
        query_tex.write_text("\n".join(lines), encoding="utf-8")
        query_pdf = compile_standalone(query_tex, out_dir)
        if query_pdf:
            print(f"wrote {query_pdf}")
            if figures.exists():
                shutil.copyfile(query_pdf, figures / query_pdf.name)
                print(f"wrote {figures / query_pdf.name}")


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
    parser.add_argument("--out-dir", type=Path, default=common.REPORTS_DIR)
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

    trec_eval = shutil.which("trec_eval")
    if not trec_eval:
        raise SystemExit(
            "trec_eval not found. Install it (e.g. 'brew install trec_eval') "
            "and make sure it is on PATH; PRI evaluations are expected to use trec_eval."
        )

    all_results: dict[str, dict[str, dict]] = {}
    with tempfile.TemporaryDirectory(prefix="pri-trec-eval-") as tmp_dir:
        tmp_path = Path(tmp_dir)
        qrels_path = tmp_path / "qrels.trec"
        write_trec_qrels(qrels, qrels_path)
        for setup in common.SETUPS:
            rankings = common.load_run(setup, args.runs_dir)
            run_path = tmp_path / f"{setup}.run"
            write_trec_run(rankings, setup, run_path)
            all_results[setup] = evaluate_setup(
                rankings,
                qrels,
                trec_eval,
                qrels_path,
                run_path,
                args.threshold,
                args.cutoff,
            )

    write_results(all_results, qrels, args.out_dir, args.threshold, args.cutoff)


if __name__ == "__main__":
    main()
