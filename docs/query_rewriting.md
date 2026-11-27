# Individual exploration — rubric-based query rewriting

**Question.** Do vague, thematic information needs retrieve better once they are
expanded or rewritten with words from the need rubric?

**Short answer.** Only partly. The rewrite helps the two review-based needs on
AP and pooled recall, but it does not improve graded top-10 quality overall and
it clearly hurts Q3. It is therefore a useful *individual* result, not a new
default system.

## Method

The rewrite is built from `INFORMATION_NEEDS` in `eval/common.py` only: the
`review_terms` / `plot_terms` vocabulary and short phrases that paraphrase the
rubric criteria. **No judged document text and no relevance grades were used to
construct it.** `eval/data/qrels.csv` is loaded only after both runs exist, to
measure them.

Each need gets four low-weight `bq` clauses (weights 0.1–0.3). The clauses are
passed through a local parameter dereference (`bq=$rw`) inside the first-stage
eDisMax query, so the Setup B overview reranker is unchanged:

- review needs: `childq={!edismax v=$text bq=$rw}`
- story needs: `q={!edismax v=$text bq=$rw}`

Using a local `bq` rather than a top-level `bq` matters: a top-level `bq` is also
inherited by the rerank query, which would mix plot boosts into the overview
stage. Solr's parsed query confirms the clauses are applied in the intended
stage.

Generated configs: `queries/rewrites/Q1.json` … `Q5.json`.

| Need | Field | Boost clauses |
|---|---|---|
| Q1 | `review_text` | `"witty dialogue"^0.3`, `"sharp writing"^0.3`, `satirical^0.2`, `clever^0.1` |
| Q2 | `review_text` | `predictable^0.3`, `"formulaic romance"^0.2`, `heartwarming^0.2`, `sentimental^0.1` |
| Q3 | `plot` | `"outer space"^0.3`, `astronaut^0.3`, `stranded^0.2`, `"return home"^0.1` |
| Q4 | `plot` | `"FBI agent"^0.3`, `"serial killer"^0.3`, `"series of murders"^0.2`, `profiler^0.1` |
| Q5 | `plot` | `"crime family"^0.3`, `"Italian-American"^0.2`, `"organized crime"^0.2`, `"De Niro"^0.1` |

Modes:

- `none`: the original M3 config, with the boost clauses removed. It reproduces
  `runs/M3_BASE.run` exactly (checked by `rewrite_experiment.py`).
- `rubric`: the rewritten config above.

Everything else is frozen: same needs, same filters, same collection, same
`m3_lexical` backend and same top-20 rerank.

## Results

Runs were produced on the scratch Solr 10.0.0 core loaded from
`data/final/solr_documents.json`. Metrics were computed with **trec_eval v10.0**
via `scripts/trec_eval_run.py` (binary relevance at grade >= 1, qrel grade as the
nDCG gain, pooled recall at depth 20). The official engine reproduces the saved
`runs/M3_BASE.run` aggregates exactly. `rewrite_experiment.py` uses trec_eval
automatically when it is on PATH and falls back to the local implementation
otherwise.

| System | P@5 | P@10 | AP | nDCG@10 | Recall@20 | MRR@10 |
|---|---:|---:|---:|---:|---:|---:|
| `M3_BASE` / `rewrite_none` | 0.880 | 0.780 | 0.497 | 0.737 | 0.588 | 1.000 |
| `rewrite_rubric` | 0.880 | 0.760 | 0.504 | 0.722 | 0.590 | 1.000 |

Per-need change from baseline (`rubric − baseline`):

| Need | P@10 | AP | nDCG@10 | Recall@20 |
|---|---:|---:|---:|---:|
| Q1 | 0.800 → 0.800 (+0.000) | 0.326 → 0.341 (+0.015) | 0.697 → 0.690 (−0.007) | 0.364 → 0.394 (+0.030) |
| Q2 | 0.900 → 0.900 (+0.000) | 0.486 → 0.526 (+0.040) | 0.891 → 0.859 (−0.032) | 0.518 → 0.556 (+0.037) |
| Q3 | 0.700 → 0.600 (−0.100) | 0.452 → 0.406 (−0.046) | 0.679 → 0.637 (−0.042) | 0.556 → 0.500 (−0.056) |
| Q4 | 0.900 → 0.900 (+0.000) | 0.460 → 0.463 (+0.003) | 0.603 → 0.611 (+0.008) | 0.500 → 0.500 (+0.000) |
| Q5 | 0.600 → 0.600 (+0.000) | 0.763 → 0.784 (+0.022) | 0.816 → 0.810 (−0.005) | 1.000 → 1.000 (+0.000) |

Mean search latency in the final verification run was 9.7 ms for `none` and
5.1 ms for `rubric`;
these are warm-cache single-pass timings and are too noisy to claim a speed
difference. The extra clauses do not change the request shape beyond one dereferenced
`rw` parameter.

## Interpretation

- **Q1/Q2 behave as hypothesised.** AP rises by +0.015 and +0.040, and recall
  rises by +0.030 and +0.037. The rubric words recover review evidence that the
  original sentence mentions only vaguely.
- **Q3 regresses on every ranking metric.** Boosting generic space terms such
  as "outer space" pulls in films with space imagery but without the stranded
  crew and survival objective. This is the same failure mode seen in the M2
  fixed-pool experiments: thematic expansion helps review language more than
  plot language.
- **Q4 is essentially unchanged.** The rubric terms are already explicit in the
  need, so there is little new evidence to add.
- **Q5 improves AP slightly (+0.022) but loses a little nDCG@10 (−0.005).**
  Recall is already 1.000 at depth 20, so there is no headroom there.
- Overall AP and recall improve marginally, but P@10 and nDCG@10 fall. Since
  graded top-10 quality is the primary M2/M3 comparison metric, **the rewrite is
  not adopted as a default**. It remains an individual finding: rubric rewriting
  is promising for subjective, review-based needs and risky for concrete plot
  needs.

With only five information needs these are descriptive differences, not
statistically significant results. The final table above is the trec_eval v10.0
output and can be reproduced with the command below.

## Reproduce

```bash
# Scratch Solr core on port 18984 (do not touch the project core on 8983)
docker run --rm -d --name pri-mm2-lab -p 127.0.0.1:18984:8983 \
  -e SOLR_HEAP=768m solr:10.0.0 solr-precreate movies
# apply solr/schema.json and upload data/final/solr_documents.json

# Generate queries/rewrites/Q*.json from queries/m3 + eval/common, then run both modes
python3 scripts/rewrite_experiment.py --write-configs --mode both \
  --uri http://127.0.0.1:18984/solr
python3 scripts/trec_eval_run.py runs/M3_BASE.run runs/rewrite_none.run \
  runs/rewrite_rubric.run --per-query
```

Saved runs: `runs/rewrite_none.run`, `runs/rewrite_rubric.run` and their
`_Q*.json` files. All reported numbers trace to those runs and
`eval/data/qrels.csv`.
