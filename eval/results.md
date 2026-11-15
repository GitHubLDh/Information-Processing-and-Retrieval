# Evaluation results

Relevance threshold: rel >= 1. Run depth: 20. Unjudged retrieved documents count as non-relevant.

## Judgment summary

| Qid | Need | Judged | Relevant (rel>=1) | rel=2 | rel=1 | rel=0 |
|---|---|---:|---:|---:|---:|---:|
| Q1 | Clever, witty comedies | 37 | 27 | 15 | 12 | 10 |
| Q2 | Clichéd romantic movies | 0 | 0 | 0 | 0 | 0 |
| Q3 | Stranded astronauts | 31 | 9 | 3 | 6 | 22 |
| Q4 | FBI serial-killer investigation | 25 | 17 | 8 | 9 | 8 |
| Q5 | Italian-American organized crime | 12 | 7 | 6 | 1 | 5 |

## Aggregate metrics

| Setup | P@5 | P@10 | MAP | nDCG@10 | Recall@20 | MRR@10 |
|---|---:|---:|---:|---:|---:|---:|
| A | 0.600 | 0.480 | 0.477 | 0.681 | 0.562 | 0.800 |
| B | 0.720 | 0.540 | 0.603 | 0.625 | 0.730 | 0.800 |

| Delta (B - A) | P@5 | P@10 | MAP | nDCG@10 | Recall@20 | MRR@10 |
|---:|---:|---:|---:|---:|---:|---:|
| Delta | +0.120 | +0.060 | +0.126 | -0.056 | +0.168 | +0.000 |

## Per-query metrics

| Qid | Setup | Ret. | Judged rel. | P@10 | AP | nDCG@10 | Recall@20 | Unjudged |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Q1 | A | 20 | 27 | 0.900 | 0.554 | 0.729 | 0.593 | 0 |
| Q1 | B | 20 | 27 | 0.900 | 0.473 | 0.495 | 0.519 | 0 |
| Q1 | Delta B-A | | | +0.000 | -0.081 | -0.234 | -0.074 | |
| Q2 | A | 20 | 0 | 0.000 | n/a | n/a | n/a | 20 |
| Q2 | B | 20 | 0 | 0.000 | n/a | n/a | n/a | 20 |
| Q2 | Delta B-A | | | +0.000 | n/a | n/a | n/a | |
| Q3 | A | 14 | 9 | 0.300 | 0.298 | 0.451 | 0.444 | 0 |
| Q3 | B | 20 | 9 | 0.400 | 0.456 | 0.613 | 0.778 | 0 |
| Q3 | Delta B-A | | | +0.100 | +0.158 | +0.162 | +0.333 | |
| Q4 | A | 7 | 17 | 0.600 | 0.323 | 0.693 | 0.353 | 0 |
| Q4 | B | 20 | 17 | 0.800 | 0.648 | 0.514 | 0.765 | 0 |
| Q4 | Delta B-A | | | +0.200 | +0.325 | -0.178 | +0.412 | |
| Q5 | A | 8 | 7 | 0.600 | 0.733 | 0.852 | 0.857 | 0 |
| Q5 | B | 10 | 7 | 0.600 | 0.837 | 0.877 | 0.857 | 0 |
| Q5 | Delta B-A | | | +0.000 | +0.103 | +0.025 | +0.000 | |

## Notes

- `P@10` uses binary relevance (rel >= 1); `nDCG@10` uses the graded 0/1/2 scale.
- AP, nDCG, recall and MRR are undefined for a query with no relevant judged document; those queries are excluded from the corresponding mean.
- Judgments cover the pooled top-20 of both systems. Any retrieved but unjudged document is treated as non-relevant, as in standard pooled IR evaluation.
- Five queries are a small sample: differences are descriptive, not statistically tested.
