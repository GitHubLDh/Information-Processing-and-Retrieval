# Evaluation (Milestone 2)

This directory contains the workflow for building a shared candidate pool,
assigning relevance judgments, and comparing Setup A and Setup B.
Run commands from the repository root.

## Evaluation flow

1. Run Setup A and Setup B retrieval to produce ranked run files under `runs/`.
2. Build the pooled candidates with `pool.py`. It combines each setup's top 20
   results for every query and deduplicates movies by `movie_id`.
3. Judge each pooled candidate, assigning a relevance grade of 0, 1, or 2.
4. Calculate metrics with `metrics.py`, which compares the rankings with the
   judgments in `qrels.csv`.
5. The generated tables and precision-recall chart are used in the report.

## Build the pool

If `eval/pool.csv` is missing or the retrieval runs have changed, build or rebuild
the pool and its evidence files:

```bash
python3 eval/pool.py
```

This requires the A/B run files under `runs/` and
`data/final/collection.jsonl`. It writes `pool.csv`, `qrels_template.csv`,
`evidence.csv`, and human-readable evidence sheets under `eval/judging/`.
Rebuilding the pool may add candidates; those need judgments before final
evaluation.

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
`?` to show help. Each grade is saved to `eval/qrels.csv` immediately. Already
graded candidates are skipped by default, so you can resume a session.

To review existing grades:

```bash
python3 eval/judge.py --judge "Your Name" --review
```

When reviewing, press Enter to keep the current grade or enter `0`, `1`, or `2`
to change it. The `judge` column records the name supplied with `--judge`.

The `seed_qrels.py` script can create predefined **preliminary** judgments, but
these are not a substitute for manual review. Do not use `--force` unless you
intend to replace the existing `qrels.csv`.

## Calculate and interpret metrics

After judging, calculate the results:

```bash
python3 eval/metrics.py
```

The script reads the A/B rankings and `eval/qrels.csv`. By default, grades 1 and
2 count as relevant for binary metrics (`--threshold 1`); `--threshold 2` counts
only grade 2 as relevant. Retrieved but unjudged documents count as non-relevant.
The default ranking depth is 20 (`--cutoff 20`).

It reports these metrics for each query and as averages across queries:

- **P@5 / P@10 (precision):** proportion of the first 5 or 10 results that are
  relevant under the selected threshold.
- **AP / MAP (average precision / mean average precision):** rewards relevant
  results that appear early in the ranking. AP is per query; MAP is its mean
  across queries.
- **nDCG@10:** measures ranking quality in the top 10 using graded judgments.
  Grade 2 receives more gain than grade 1, and relevant results near the top
  contribute more.
- **Recall@20:** proportion of all judged-relevant pooled candidates found in
  the top 20.
- **MRR@10 (mean reciprocal rank at 10):** based on the rank of the first
  relevant result in the top 10; earlier is better.

Queries with no relevant judged candidates have undefined AP, nDCG, and recall
and are omitted from the corresponding averages.

### Precision-recall curve

The precision-recall data measures precision as recall increases down each
ranked list. For the mean curve, the script interpolates precision at 11 recall
levels (0.0 through 1.0, in steps of 0.1), then averages each level across
queries, separately for Setup A and B. At a given recall level, higher
interpolated precision generally indicates better retrieval.

## Generated files

By default, `metrics.py` writes its outputs to `eval/`:

- `results.csv`, `results.json`, and `results.md`: per-query and aggregate
  metrics, including the Setup B minus Setup A differences.
- `results_table.tex`, `results_per_query_table.tex`, and
  `results_compact_table.tex`: LaTeX tables for the report.
- `pr_curve.csv` and `pr_curve_mean.csv`: per-query precision-recall points and
  the 11-point mean curve.
- `pr_curve.tex` and, when `pdflatex` is installed, `pr_curve.pdf`: chart source
  and compiled chart.

When the report's `figures/` directory exists and the PDF compiles successfully,
the chart is also copied to `report/figures/pr_curve.pdf`. The script does not
edit the report's main LaTeX file. It warns if qrels rows are not marked
`judge=manual`; inspect the judgments before treating those results as final.
