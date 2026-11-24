# Evaluation results

Computed with trec_eval version 10.0.

Relevance threshold: rel >= 1. Run depth: 20. All retrieved movies at this depth have manual judgments.

## Judgment summary

| Qid | Need | Judged | Relevant (rel>=1) | rel=2 | rel=1 | rel=0 |
|---|---|---:|---:|---:|---:|---:|
| Q1 | Clever, witty comedies | 50 | 33 | 16 | 17 | 17 |
| Q2 | Clichéd romantic movies | 40 | 27 | 16 | 11 | 13 |
| Q3 | Stranded astronauts | 57 | 18 | 9 | 9 | 39 |
| Q4 | FBI serial-killer investigation | 44 | 28 | 9 | 19 | 16 |
| Q5 | Italian-American organized crime | 28 | 7 | 6 | 1 | 21 |

## Aggregate metrics

| Setup | P@5 | P@10 | MAP | nDCG@10 | Recall@20 | MRR@10 |
|---|---:|---:|---:|---:|---:|---:|
| A | 0.800 | 0.740 | 0.465 | 0.688 | 0.588 | 0.900 |
| B | 0.880 | 0.780 | 0.497 | 0.737 | 0.588 | 1.000 |

| Delta (B - A) | P@5 | P@10 | MAP | nDCG@10 | Recall@20 | MRR@10 |
|---:|---:|---:|---:|---:|---:|---:|
| Delta | +0.080 | +0.040 | +0.032 | +0.050 | +0.000 | +0.100 |

## Per-query metrics

| Qid | Setup | Ret. | Relevant retrieved / pooled relevant | P@5 | P@10 | AP | nDCG@10 | Recall@20 | RR@10 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Q1 | A | 20 | 12 / 33 | 0.800 | 0.800 | 0.326 | 0.697 | 0.364 | 1.000 |
| Q1 | B | 20 | 12 / 33 | 0.800 | 0.800 | 0.326 | 0.697 | 0.364 | 1.000 |
| Q1 | Delta B-A | | | +0.000 | +0.000 | +0.000 | +0.000 | +0.000 | +0.000 |
| Q2 | A | 20 | 14 / 27 | 1.000 | 0.900 | 0.486 | 0.891 | 0.518 | 1.000 |
| Q2 | B | 20 | 14 / 27 | 1.000 | 0.900 | 0.486 | 0.891 | 0.518 | 1.000 |
| Q2 | Delta B-A | | | +0.000 | +0.000 | +0.000 | +0.000 | +0.000 | +0.000 |
| Q3 | A | 20 | 10 / 18 | 0.600 | 0.500 | 0.378 | 0.569 | 0.556 | 1.000 |
| Q3 | B | 20 | 10 / 18 | 0.800 | 0.700 | 0.452 | 0.679 | 0.556 | 1.000 |
| Q3 | Delta B-A | | | +0.200 | +0.200 | +0.074 | +0.110 | +0.000 | +0.000 |
| Q4 | A | 20 | 14 / 28 | 0.800 | 0.900 | 0.445 | 0.592 | 0.500 | 1.000 |
| Q4 | B | 20 | 14 / 28 | 1.000 | 0.900 | 0.460 | 0.603 | 0.500 | 1.000 |
| Q4 | Delta B-A | | | +0.200 | +0.000 | +0.015 | +0.010 | +0.000 | +0.000 |
| Q5 | A | 20 | 7 / 7 | 0.800 | 0.600 | 0.693 | 0.689 | 1.000 | 0.500 |
| Q5 | B | 20 | 7 / 7 | 0.800 | 0.600 | 0.763 | 0.816 | 1.000 | 1.000 |
| Q5 | Delta B-A | | | +0.000 | +0.000 | +0.069 | +0.127 | +0.000 | +0.500 |

## Metric definitions and how the values were obtained

All values are computed with `trec_eval` by `eval/metrics.py`. The script
converts the graded judgments in `eval/data/qrels.csv` to the TREC qrels format
(`qid 0 docid rel`) and the saved runs (`runs/A.run`
and `runs/B.run`) to the TREC run format, using the
numeric `movie_id` as the document id. Following the tutorial's
`solr_to_trec.py`, the converted runs keep each Solr score; trec_eval sorts
by score, so equal scores are resolved by trec_eval's own tie-breaking and
not by the saved rank column. The script then calls trec_eval with `-q` to get
per-query and aggregate values. Binary metrics use `-l 1`, so a
movie counts as relevant when its grade is at least that value; the nDCG
measure uses the full 0/1/2 grades. Aggregate rows are unweighted means over
the five queries, so each information need contributes equally regardless of
how many candidates it has. Per-query rows show the same values before
averaging; delta rows are Setup B minus Setup A.

- **P@5 / P@10 (precision at 5 and 10).** The fraction of the first 5 or 10
  results that are relevant: `(relevant results in the top k) / k`. The
  divisor is always `k`; if a setup returns fewer than `k` movies, missing positions count as
  non-relevant. Obtained from trec_eval's `P.5` and `P.10` measures, then
  averaged over queries in the aggregate table.
- **AP / MAP (average precision and mean average precision).** AP walks the
  ranked list and averages the precision at every rank where a relevant movie
  occurs, divided by the total number of judged-relevant movies for that query:
  `AP = (1 / R) * sum over relevant ranks i of (hits_i / rank_i)`, where
  `hits_i` is the number of relevant movies seen up to rank `i` and `R` is the
  per-query pooled relevant count shown in the judgment summary and in the
  `Relevant retrieved / pooled relevant` column. Relevant movies that were
  not retrieved within the run depth remain in `R`, so they lower AP. MAP is
  the unweighted mean of AP over the five queries. Obtained from trec_eval's
  `map` measure; AP and MAP are undefined for a query with no relevant judged
  movie and are excluded from that mean.
- **nDCG@10 (normalised discounted cumulative gain at 10).** Uses the graded
  labels, so a grade-2 movie contributes more than a grade-1 movie. trec_eval's
  `ndcg_cut` uses the qrel grade directly as the gain:
  `DCG@10 = sum over the first 10 ranks of rel / log2(rank + 1)`.
  The ideal DCG (`IDCG@10`) is computed by sorting all judged grades for that
  query in descending order and applying the same formula to the top 10;
  `nDCG@10 = DCG@10 / IDCG@10`. The value is 1 when the top 10 follows the
  best possible graded ordering. Obtained from trec_eval's `ndcg_cut.10`, then
  averaged over queries in the aggregate table.
- **Recall@20 (pooled recall at 20).** The fraction of the pooled relevant
  movies found in the top 20: `(relevant movies in the top 20) / (total
  judged-relevant movies in the pool)`. The denominator is the pooled
  judged-relevant set, not every relevant movie in the 6,104-document
  collection, so this is pooled recall rather than absolute collection
  recall. Obtained from trec_eval's `recall.20` measure, then averaged over
  queries in the aggregate table.
- **MRR@10 (mean reciprocal rank at 10).** The reciprocal of the rank of the
  first relevant movie within the top 10 (`1 / rank`), or 0 if no relevant
  movie occurs in the top 10. MRR@10 is the mean of this value over the five
  queries. It measures how early the first relevant hit appears and ignores
  the rest of the ranking. Obtained from trec_eval's `recip_rank` measure run
  with `-M 10`, which truncates each ranking before evaluation.

## Notes

- Reported values are trec_eval measures (`map`, `P.5,10`, `ndcg_cut.10`, `recall.20`, and `recip_rank` with `-M 10`).
- `P@5`, `P@10`, `AP`, `Recall@20` and `MRR@10` use binary relevance
  (rel >= 1); `nDCG@10` uses the graded 0/1/2 scale.
- AP, nDCG, recall and MRR are undefined for a query with no relevant judged document; those queries are excluded from the corresponding mean.
- Recall uses all known relevant manual judgments, including earlier pools.
- The precision-recall values are trec_eval's `iprec_at_recall_0.00` through `iprec_at_recall_1.00` measures, with `11pt_avg` as the area under the curve (AUC). The mean curve averages each of the 11 recall levels across the five queries.
- `pr_curve_A.pdf` and `pr_curve_B.pdf` plot the five per-query curves for each setup and `pr_curve.pdf` shows their mean curves for the current runs.
- Five queries are a small sample: differences are descriptive, not statistically tested.
