# P1 handoff for P4 — Milestone 3

This is the single comparison and handoff point for P1's M3 work. It deliberately
does **not** edit `report/main.tex`; the LaTeX block near the end is ready for P4
to paste into the report.

## Scope and frozen assets

The frozen M2 comparison point is unchanged: `queries/setup_a`, `queries/setup_b`,
the A/B behaviour of `scripts/solr_client.py`, `runs/A.run`, `runs/B.run`, and all
`eval/data/qrels*.csv` files were not modified. `solr/schema.json` was not touched
(P2 owns the vector field).

The final M3 lexical configuration is **M2 Setup B unchanged**: `mm=1`,
`qf=plot` for story needs and `qf=review_text` for review needs,
`score=max` for the parent/child review join, and the top-20 overview rerank.
Every tested alternative was kept as a saved run but rejected or not adopted.

All metrics in this document were produced with **trec_eval v10.0** against the
shared 219-grade `eval/data/qrels.csv`. Binary relevance is grade >= 1; nDCG uses
the grade as its gain; recall is pooled recall at depth 20. Unjudged candidates
in the new M3 runs are treated as grade 0 until P4 judges them.

## Run inventory

Each `runs/<id>.run` has five sibling `runs/<id>_Q*.json` files with the full
Solr request, `num_found`, per-result metadata and measured latency.

| Run id | Purpose | Outcome |
|---|---|---|
| `A.run` | Frozen M2 single-field baseline | Comparator |
| `B.run` | Frozen M2 top-20 overview rerank | Primary comparator |
| `M3_BASE.run` | M3 runner reproducing B through the shared registry | Adopted M3 baseline; rankings equal to B |
| `M3_MM2.run` | `mm=2`, `tie=0.1` | Not adopted |
| `M3_MM70.run` | `mm=70%`, `tie=0.1` | Rejected; collapses to 0–2 results per need |
| `M3_BOOST_RW1.run` | `qf=plot^1 overview^2 title^2`, rerank weight 1 | Rejected |
| `M3_BOOST_RW05.run` | Same boosted `qf`, rerank weight 0.5 | Rejected |
| `M3_JOIN_TOTAL.run` | Review join `score=total` on Q1/Q2 | Rejected |
| `M3_JOIN_AVG.run` | Review join `score=avg` on Q1/Q2 | Rejected |
| `M3_PF.run` | Isolated `pf` / `ps=2` phrase boost | Not adopted; rankings equal to B |
| `rewrite_none.run` | Rewriting control | Rankings equal to `M3_BASE` |
| `rewrite_rubric.run` | Rubric-expanded rewrites | Individual finding; not adopted as default |

Supporting M2 evidence also uses `runs/B_overview_trial.run`, described in
[query specification](query_specification.md).

## Single comparison

Mean over the five information needs. The AP column is trec_eval's `map`.

| System | Run id | P@5 | P@10 | AP | nDCG@10 | Recall@20 | MRR@10 |
|---|---|---:|---:|---:|---:|---:|---:|
| M2-A | `A.run` | 0.800 | 0.740 | 0.465 | 0.688 | 0.588 | 0.900 |
| M2-B / M3 final | `B.run`, `M3_BASE.run` | 0.880 | 0.780 | 0.497 | 0.737 | 0.588 | 1.000 |
| `mm=2`, `tie=0.1` | `M3_MM2.run` | 0.840 | 0.800 | 0.491 | 0.750 | 0.588 | 1.000 |
| `mm=70%`, `tie=0.1` | `M3_MM70.run` | 0.200 | 0.100 | 0.039 | 0.141 | 0.039 | 0.800 |
| Boosted `qf`, rerank 1 | `M3_BOOST_RW1.run` | 0.800 | 0.740 | 0.463 | 0.680 | 0.588 | 0.900 |
| Boosted `qf`, rerank 0.5 | `M3_BOOST_RW05.run` | 0.840 | 0.720 | 0.466 | 0.676 | 0.588 | 0.900 |
| Review join `total` | `M3_JOIN_TOTAL.run` | 0.840 | 0.640 | 0.429 | 0.607 | 0.542 | 1.000 |
| Review join `avg` | `M3_JOIN_AVG.run` | 0.600 | 0.500 | 0.365 | 0.507 | 0.480 | 0.800 |
| Phrase boost | `M3_PF.run` | 0.880 | 0.780 | 0.497 | 0.737 | 0.588 | 1.000 |
| Rewriting control | `rewrite_none.run` | 0.880 | 0.780 | 0.497 | 0.737 | 0.588 | 1.000 |
| Rubric rewriting | `rewrite_rubric.run` | 0.880 | 0.760 | 0.504 | 0.722 | 0.590 | 1.000 |

The honest conclusion is that **no lexical change was adopted**. `mm=2` has the
best mean nDCG@10 (0.750 versus 0.737) but lowers AP (0.497 → 0.491) and P@5, and
its Q3/Q5 AP regressions make the per-need trade-off unacceptable. All other
lexical trials are worse or identical. The rubric rewriting experiment improves
mean AP (0.497 → 0.504) and Recall@20 (0.588 → 0.590) but lowers P@10 and
nDCG@10, with gains on Q1/Q2 and a clear regression on Q3; see
[query rewriting](query_rewriting.md).

The full change log with weak spots, M2 evidence, tested changes and decisions is
in [M3 lexical changes](m3_lexical.md). No schema change or reindex was needed.

## New candidates for P4 judgments

The saved M3 and rewriting runs surface **49 query–movie pairs that are not in
`eval/data/qrels.csv`**. Until they are judged they are scored as grade 0, so the
variant and rewriting rows above are provisional for recall-sensitive metrics.

| Need | Unjudged pairs | Main originating runs (occurrences) |
|---|---:|---|
| Q1 | 27 | `M3_JOIN_AVG` (15), `M3_JOIN_TOTAL` (12), `rewrite_rubric` (1) |
| Q2 | 15 | `M3_JOIN_AVG` (10), `M3_JOIN_TOTAL` (5) |
| Q3 | 2 | `M3_BOOST_RW1` (1), `M3_BOOST_RW05` (1), `rewrite_rubric` (1) |
| Q4 | 3 | `M3_BOOST_RW1` (2), `M3_BOOST_RW05` (2), `rewrite_rubric` (1) |
| Q5 | 2 | `M3_MM2` (1), `M3_BOOST_RW1` (1), `M3_BOOST_RW05` (1) |

A judgeable CSV is saved separately at `eval/data/p1_new_pool.csv`; it does not
overwrite the frozen M2 `pool.csv` or `qrels.csv`. Columns are `qid`, `docid`,
`title`, `year`, `genres`, `origin_runs`, `best_rank` and `overview`.

```bash
python3 scripts/build_p1_pool.py
python3 eval/judge.py --judge "Your name" --pool eval/data/p1_new_pool.csv
```

Append the resulting grades to `eval/data/qrels.csv`, rerun
`scripts/trec_eval_run.py`, and update the report table if any variant changes.
Regenerating the pool after judging will naturally shrink the unjudged list.

## LaTeX-ready block for P4

Paste this into `report/main.tex` with the `booktabs` package. It intentionally
omits the clearly inferior trials; the full run table is above.

```latex
\begin{table}[t]
\centering
\caption{M2 baseline and selected M3 systems. AP is trec_eval's \texttt{map}
averaged over the five information needs; Recall is pooled recall at 20.}
\label{tab:m3-comparison}
\begin{tabular}{lrrrrrr}
\toprule
System & P@5 & P@10 & AP & nDCG@10 & Recall@20 & MRR@10 \\
\midrule
M2-A (frozen)            & 0.800 & 0.740 & 0.465 & 0.688 & 0.588 & 0.900 \\
M2-B / M3 final          & 0.880 & 0.780 & 0.497 & 0.737 & 0.588 & 1.000 \\
M3: \texttt{mm=2}        & 0.840 & 0.800 & 0.491 & 0.750 & 0.588 & 1.000 \\
M3: boosted \texttt{qf}  & 0.800 & 0.740 & 0.463 & 0.680 & 0.588 & 0.900 \\
M3: review join \texttt{total} & 0.840 & 0.640 & 0.429 & 0.607 & 0.542 & 1.000 \\
Rubric rewriting         & 0.880 & 0.760 & 0.504 & 0.722 & 0.590 & 1.000 \\
\bottomrule
\end{tabular}
\end{table}
```

Suggested paragraph:

> For Milestone 3 we rebuilt the frozen M2 Setup B behind a shared search
> interface and tested several lexical changes on the same five information
> needs and the same 219 graded query–movie pairs. No lexical change was
> adopted: requiring two query terms raised mean nDCG@10 from 0.737 to 0.750
> but lowered AP from 0.497 to 0.491 and regressed Q3 and Q5, while direct
> overview weighting, alternative review-join score modes and phrase boosts
> were rejected or identical to the baseline. A separate query-rewriting
> exploration using only the information-need rubric vocabulary improved mean
> AP (0.497 to 0.504) and Recall@20 (0.588 to 0.590), but reduced P@10 (0.780
> to 0.760) and nDCG@10 (0.737 to 0.722), with gains on the two review-based
> needs and a clear regression on the stranded-astronaut need. With five needs
> these are descriptive rather than statistically significant results, and 49
> newly surfaced candidates remain unjudged, so the variant rows should be
> treated as provisional until P4 extends the qrels.

## Traceability and reproduction

All numbers above come from saved TREC runs and `eval/data/qrels.csv`:

```bash
python3 scripts/check_search_contract.py
python3 scripts/trec_eval_run.py runs/A.run runs/B.run runs/M3_BASE.run \
  runs/M3_MM2.run runs/M3_MM70.run runs/M3_BOOST_RW1.run \
  runs/M3_BOOST_RW05.run runs/M3_JOIN_TOTAL.run runs/M3_JOIN_AVG.run \
  runs/M3_PF.run runs/rewrite_none.run runs/rewrite_rubric.run --per-query
python3 scripts/build_p1_pool.py
```

`trec_eval` v10.0 must be on PATH. The local fallback in
`scripts/rewrite_experiment.py` is only for environments where it is not
installed; the tables here use the official engine.
