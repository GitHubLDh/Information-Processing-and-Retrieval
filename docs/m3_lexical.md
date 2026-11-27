# Milestone 3 lexical changes 

This is the running change log for P1's iteration over the M2 retrieval setup.
The frozen comparison point is **Setup B** (`runs/B.run`, `eval/output/results.md`),
the better of the two M2 systems. All trials use the same five information needs,
the same structured filters, the same collection, and the cumulative 219 manual
grades in `eval/data/qrels.csv`. Rankings were produced on a scratch Solr 10.0.0
core loaded from `data/final/solr_documents.json`; the M3 baseline reproduced
`runs/B.run` byte-for-byte before any parameter was changed.

`trec_eval` is not installed in this environment, so the trial metrics below use
a local implementation of the definitions in `eval/output/results.md` (binary
relevance at grade >= 1, qrel grade as the nDCG gain, pooled recall, depth 20).
It reproduces the saved Setup B aggregates exactly, which validates the
implementation. P4 should reproduce the final comparison with trec_eval v10.0.

## Match requirement (`mm`) and tie breaking

Problem: M2 uses `mm=1` with `q.op=OR`, so a single generic word from a long
thematic sentence can retrieve a movie. Trial: require two terms (`mm=2`) or 70%
of the analysed terms (`mm=70%`), both with `tie=0.1` to keep some weight on
secondary clauses. All other Solr parameters stay at the M2 Setup B values.
Configs: `queries/m3/variants/mm2/` and `queries/m3/variants/mm70/`.

| System | P@5 | P@10 | AP | nDCG@10 | Recall@20 | MRR@10 |
|---|---:|---:|---:|---:|---:|---:|
| B (frozen baseline) | 0.880 | 0.780 | 0.497 | 0.737 | 0.588 | 1.000 |
| `mm=2`, `tie=0.1` | 0.840 | 0.800 | 0.491 | 0.750 | 0.588 | 1.000 |
| `mm=70%`, `tie=0.1` | 0.200 | 0.100 | 0.039 | 0.141 | 0.039 | 0.800 |

Per-need change from B (`mm=2` / `mm=70%`):

| Need | AP | nDCG@10 | Recall@20 |
|---|---:|---:|---:|
| Q1 | 0.326 → 0.326 / 0.030 | 0.697 → 0.697 / 0.110 | 0.364 → 0.364 / 0.030 |
| Q2 | 0.486 → 0.486 / 0.037 | 0.891 → 0.891 / 0.110 | 0.519 → 0.519 / 0.037 |
| Q3 | 0.452 → 0.442 / 0.056 | 0.679 → 0.687 / 0.227 | 0.556 → 0.556 / 0.056 |
| Q4 | 0.460 → 0.465 / 0.071 | 0.603 → 0.603 / 0.257 | 0.500 → 0.500 / 0.071 |
| Q5 | 0.763 → 0.738 / 0.000 | 0.816 → 0.873 / 0.000 | 1.000 → 1.000 / 0.000 |

`mm=70%` collapses the run: after stopword removal and stemming these natural
sentences still have many terms, and almost no movie matches that many. Q5
returns no results at all. Rejected.

`mm=2` is a mixed result, not an across-the-board gain. It raises P@10 by 0.02
and nDCG@10 by 0.013 but lowers P@5 by 0.04 and AP by 0.006, with no recall
gain. Q1/Q2 are unchanged (the nested review query is effectively unchanged),
Q4 improves slightly on AP, Q3 and Q5 lose AP even though Q5's graded ordering
improves. **Not adopted as the default M3 configuration**; `mm` stays at 1 for
the next trials. Because `tie=0.1` was changed together with `mm`, the two
effects are not isolated. Saved runs: `runs/M3_MM2.run`, `runs/M3_MM70.run`.

## Reproduce

Start a scratch core on port 18984 (do not touch the project core on 8983):

```bash
docker run --rm -d --name pri-mm2-lab -p 127.0.0.1:18984:8983 \
  -e SOLR_HEAP=768m solr:10.0.0 solr-precreate movies
# apply solr/schema.json and upload data/final/solr_documents.json
python3 scripts/run_system.py --system m3_lexical \
  --queries queries/m3/variants/mm2 --uri http://127.0.0.1:18984/solr --run-id M3_MM2
python3 scripts/run_system.py --system m3_lexical \
  --queries queries/m3/variants/mm70 --uri http://127.0.0.1:18984/solr --run-id M3_MM70
```
