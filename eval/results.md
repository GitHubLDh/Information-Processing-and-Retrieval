# Evaluation results

Relevance threshold: rel >= 1. Run depth: 20. All retrieved movies at this depth have judgments.

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
| A | 0.800 | 0.740 | 0.465 | 0.647 | 0.588 | 0.900 |
| B | 0.880 | 0.780 | 0.497 | 0.694 | 0.588 | 1.000 |

| Delta (B - A) | P@5 | P@10 | MAP | nDCG@10 | Recall@20 | MRR@10 |
|---:|---:|---:|---:|---:|---:|---:|
| Delta | +0.080 | +0.040 | +0.032 | +0.046 | +0.000 | +0.100 |

## Per-query metrics

| Qid | Setup | Ret. | Judged rel. | P@5 | P@10 | AP | nDCG@10 | Recall@20 | RR@10 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Q1 | A | 20 | 33 | 0.800 | 0.800 | 0.326 | 0.645 | 0.364 | 1.000 |
| Q1 | B | 20 | 33 | 0.800 | 0.800 | 0.326 | 0.645 | 0.364 | 1.000 |
| Q1 | Delta B-A | | | +0.000 | +0.000 | +0.000 | +0.000 | +0.000 | +0.000 |
| Q2 | A | 20 | 27 | 1.000 | 0.900 | 0.486 | 0.877 | 0.519 | 1.000 |
| Q2 | B | 20 | 27 | 1.000 | 0.900 | 0.486 | 0.877 | 0.519 | 1.000 |
| Q2 | Delta B-A | | | +0.000 | +0.000 | +0.000 | +0.000 | +0.000 | +0.000 |
| Q3 | A | 20 | 18 | 0.600 | 0.500 | 0.378 | 0.556 | 0.556 | 1.000 |
| Q3 | B | 20 | 18 | 0.800 | 0.700 | 0.452 | 0.647 | 0.556 | 1.000 |
| Q3 | Delta B-A | | | +0.200 | +0.200 | +0.074 | +0.090 | +0.000 | +0.000 |
| Q4 | A | 20 | 28 | 0.800 | 0.900 | 0.445 | 0.480 | 0.500 | 1.000 |
| Q4 | B | 20 | 28 | 1.000 | 0.900 | 0.460 | 0.486 | 0.500 | 1.000 |
| Q4 | Delta B-A | | | +0.200 | +0.000 | +0.015 | +0.007 | +0.000 | +0.000 |
| Q5 | A | 20 | 7 | 0.800 | 0.600 | 0.693 | 0.679 | 1.000 | 0.500 |
| Q5 | B | 20 | 7 | 0.800 | 0.600 | 0.763 | 0.814 | 1.000 | 1.000 |
| Q5 | Delta B-A | | | +0.000 | +0.000 | +0.069 | +0.135 | +0.000 | +0.500 |

## Notes

- `P@10` uses binary relevance (rel >= 1); `nDCG@10` uses the graded 0/1/2 scale.
- AP, nDCG, recall and MRR are undefined for a query with no relevant judged document; those queries are excluded from the corresponding mean.
- Recall uses all known relevant judgments for each need, including earlier pools.
- Five queries are a small sample: differences are descriptive, not statistically tested.
