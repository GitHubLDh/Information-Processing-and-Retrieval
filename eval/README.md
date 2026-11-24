# Movie retrieval evaluation

This directory contains the workflow for building a shared candidate pool,
assigning relevance judgments, and comparing Setup A and Setup B.
The workflow is organized into separate sections:

- `eval/data/qrels.csv` is the authoritative, cumulative manual judgment file. The fixed-pool experiment reads the separate 135-grade snapshot in `eval/data/qrels_milestone2.csv`.
- `eval/data/pool.csv`, `evidence.csv` and `qrels_template.csv` are regenerated from the current rankings and collection.
- `eval/judging/` stores the human-readable evidence sheets for manual judging.
- `eval/output/` stores the generated metrics tables and PR-curve outputs.
- the top-level scripts remain in `eval/` for the everyday workflow.

Run commands from the repository root.

## Evaluation flow

1. Run Setup A and Setup B retrieval to produce ranked run files under `runs/`.
   Every need must have a saved ranking. For a query with zero hits, keep its
   empty per-query JSON as the TREC format has no row for it.
2. Build the pooled candidates with `pool.py`. It combines each setup's top 20
   results for every query and deduplicates movies by `movie_id`.
3. Judge each pooled candidate, assigning a relevance grade of 0, 1, or 2.
4. Calculate metrics with `metrics.py`, which converts the rankings and
   judgments to TREC format and calls `trec_eval`.
5. Current tables and precision-recall charts are written to `eval/output/`. The report loads its natural-language A/B charts directly from this directory.

## Build the pool

If `eval/data/pool.csv` is missing or the retrieval runs have changed, build or rebuild
the pool and its evidence files:

```bash
python3 eval/pool.py
```

This requires the A/B run files under `runs/` and
`data/final/collection.jsonl`. It writes `eval/data/pool.csv`,
`eval/data/qrels_template.csv`, `eval/data/evidence.csv`, and human-readable
judging sheets under `eval/judging/`.
Rebuilding the pool may add candidates; those need judgments before final
evaluation.
The offline judging page in `eval/judging/index.html` includes the rebuilt
pool and the grades already in `qrels.csv` at generation time. Its export
keeps historical judgments outside the current pool. Save the exported CSV as
`eval/data/qrels.csv` before running metrics. Use one grading session at a time.

## Judge candidates in the terminal

Start an interactive session for all queries:

```bash
python3 eval/judge.py --judge "Your Name"
```

To judge one query only, specify its ID:

```bash
python3 eval/judge.py --judge "Your Name" --qid Q1
```

The judge displays each movie's overview, matching plot/review snippets, and
ranks in Setup A and B. Grade each candidate:

- `2` — highly relevant: explicit evidence satisfies the information need.
- `1` — partially relevant: evidence is weak, indirect, or mixed.
- `0` — not relevant: no supporting evidence, or the evidence contradicts the need.

Use `s` to skip, `p` to go to the previous candidate, `q` to save and quit, and
`?` to show help. Each grade is saved to `eval/data/qrels.csv` immediately.
Already graded candidates are skipped by default, so you can resume a session.

To review existing grades:

```bash
python3 eval/judge.py --judge "Your Name" --review
```

When reviewing, press Enter to keep the current grade or enter `0`, `1`, or `2`
to change it. The `judge` column records the name supplied with `--judge`.

For historical comparisons, `python3 eval/seed_qrels.py` can regenerate the
preliminary sheet locally. Manual grading superseded those seed grades.

## Calculate and interpret metrics

After judging, calculate the results:

```bash
python3 eval/metrics.py
```

Use the [trec_eval v10.0 release](https://github.com/usnistgov/trec_eval/tree/v10.0)
on `PATH` to reproduce the current curves. Version 10 rounds recall cutoffs to
the nearest document count. Version 9 can give different interpolated precision
and 11-point average values for the same rankings and grades.
It reads the A/B rankings and `eval/data/qrels.csv`, writes temporary TREC qrels and
run files, and calls `trec_eval` with `-q` for per-query and aggregate values.
Following the tutorial's `solr_to_trec.py`, the run files keep each Solr score
and use the position in the saved ranking as the TREC rank; `trec_eval` sorts
by score, so equal scores are resolved by its own tie-breaking.

By default, grades 1 and 2 count as relevant for binary metrics
(`--threshold 1`); `--threshold 2` counts only grade 2 as relevant. If grades are missing, the script writes coverage and paired precision bounds to
`results.md`, `results.csv` and `results.json` under `eval/output/` and removes
stale final tables and charts from that directory. The default ranking depth is 20
(`--cutoff 20`).

It reports the corresponding `trec_eval` measures for each query and as
averages across queries:

- **P@5 / P@10 (precision):** proportion of the first 5 or 10 results that are
  relevant under the selected threshold (`trec_eval -m P.5,10`).
- **AP / MAP (average precision / mean average precision):** rewards relevant
  results that appear early in the ranking. AP is per query; MAP is its mean
  across queries (`trec_eval -m map`).
- **nDCG@10:** measures ranking quality in the top 10 using graded judgments.
  `trec_eval` uses the qrel grade as the gain, so grade 2 contributes twice as
  much as grade 1, and relevant results near the top contribute more
  (`trec_eval -m ndcg_cut.10`).
- **Recall@20:** proportion of all judged-relevant pooled candidates found in
  the top 20 (`trec_eval -m recall.20`).
- **MRR@10 (mean reciprocal rank at 10):** based on the rank of the first
  relevant result in the top 10; earlier is better (`trec_eval -M 10 -m
  recip_rank`).

Queries with no relevant judged candidates have undefined AP, nDCG, and recall
and are omitted from the corresponding averages.

### Precision-recall curve

The precision-recall data comes directly from `trec_eval`'s
`iprec_at_recall_0.00` through `iprec_at_recall_1.00` measures, as in the
tutorial's `plot_pr_curve.py`. `11pt_avg` is reported as the area under the
curve (AUC). For the mean curve, the script averages each of the 11 recall
levels across queries, separately for Setup A and B. It also writes
tutorial-style per-query plots for each setup, labelled with AP, AUC, and P@10.
At a given recall level, higher interpolated precision generally indicates
better retrieval.

## Generated files

By default, `metrics.py` writes its outputs to `eval/output/`:

- `results.csv`, `results.json`, and `results.md`: per-query and aggregate
  metrics, including the Setup B minus Setup A differences.
- `results_table.tex`, `results_per_query_table.tex`, and
  `results_compact_table.tex`: LaTeX tables for the report.
- `pr_curve.csv` and `pr_curve_mean.csv`: per-query precision-recall points and
  the 11-point mean curve, both from `trec_eval`.
- `pr_curve.tex` and, when `pdflatex` is installed, `pr_curve.pdf`: mean chart
  source and compiled chart.
- `pr_curve_A.tex`/`pr_curve_A.pdf` and `pr_curve_B.tex`/`pr_curve_B.pdf`:
  per-query plots in the tutorial's `plot_pr_curve.py` style.

The [current mean curve](output/pr_curve.pdf) and the per-query charts for
[Setup A](output/pr_curve_A.pdf) and [Setup B](output/pr_curve_B.pdf) use the
natural-language runs. The hand-written query charts are preserved at Git
revision `74e164f` under `report/figures/`. The earlier Python tables and curves
are available in the [original evaluation snapshot](https://github.com/GitHubLDh/Information-Processing-and-Retrieval/tree/f06387fe46592d9c44279da862e73639a4100915/eval).
The [controlled experiments](../docs/query_specification.md) use the frozen
judgments. The [current results](output/results.md) use the unrestricted A/B runs
and all 219 manual grades. All 100 pairs in the current top-20 pool are judged.
