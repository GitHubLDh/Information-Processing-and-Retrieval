# Milestone 3 lexical changes 

This is the running change log for P1's iteration over the M2 retrieval setup.
The frozen comparison point is **Setup B** (`runs/B.run`, `eval/output/results.md`),
the better of the two M2 systems. All trials use the same five information needs,
the same structured filters, the same collection, and the cumulative 219 manual
grades in `eval/data/qrels.csv`. Rankings were produced on a scratch Solr 10.0.0
core loaded from `data/final/solr_documents.json`; the M3 baseline reproduced
`runs/B.run` byte-for-byte before any parameter was changed.

All metrics below were regenerated with **trec_eval v10.0** via
`scripts/trec_eval_run.py`: binary relevance at grade >= 1, qrel grade as the
nDCG gain, pooled recall at depth 20. The official engine reproduces the saved
Setup B aggregates exactly. For `mm=70%`, Q5 has no retrieved documents, so
trec_eval emits zeros for that query and exits non-zero; those zeros are included
in the means below.

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
| Q2 | 0.486 → 0.486 / 0.037 | 0.891 → 0.891 / 0.110 | 0.518 → 0.518 / 0.037 |
| Q3 | 0.452 → 0.442 / 0.056 | 0.679 → 0.687 / 0.227 | 0.556 → 0.556 / 0.056 |
| Q4 | 0.460 → 0.465 / 0.071 | 0.603 → 0.603 / 0.257 | 0.500 → 0.500 / 0.071 |
| Q5 | 0.763 → 0.738 / 0.000 | 0.816 → 0.874 / 0.000 | 1.000 → 1.000 / 0.000 |

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

## Story field boosts and rerank weight

Problem: M2 gives every story field equal implicit weight, and BM25 length
normalisation suppresses a single matching term in a long plot (median 596
words). Trial: for the three story needs set `qf=plot^1 overview^2 title^2`
while keeping Setup B's top-20 overview rerank, at weight 1 and at weight 0.5.
The two review needs are deliberately left unchanged, so their identical scores
act as a control. Configs: `queries/m3/variants/boosts_rw1/` and
`queries/m3/variants/boosts_rw05/`.

| System | P@5 | P@10 | AP | nDCG@10 | Recall@20 | MRR@10 |
|---|---:|---:|---:|---:|---:|---:|
| B (frozen baseline) | 0.880 | 0.780 | 0.497 | 0.737 | 0.588 | 1.000 |
| boosted `qf`, rerank weight 1 | 0.800 | 0.740 | 0.463 | 0.680 | 0.588 | 0.900 |
| boosted `qf`, rerank weight 0.5 | 0.840 | 0.720 | 0.466 | 0.676 | 0.588 | 0.900 |

Per-need change from B (`rw=1` / `rw=0.5`):

| Need | AP | nDCG@10 | Recall@20 |
|---|---:|---:|---:|
| Q1 | 0.326 → 0.326 / 0.326 | 0.697 → 0.697 / 0.697 | 0.364 → 0.364 / 0.364 |
| Q2 | 0.486 → 0.486 / 0.486 | 0.891 → 0.891 / 0.891 | 0.518 → 0.518 / 0.518 |
| Q3 | 0.452 → 0.302 / 0.298 | 0.679 → 0.379 / 0.379 | 0.556 → 0.556 / 0.556 |
| Q4 | 0.460 → 0.466 / 0.461 | 0.603 → 0.596 / 0.568 | 0.500 → 0.500 / 0.500 |
| Q5 | 0.763 → 0.738 / 0.757 | 0.816 → 0.836 / 0.845 | 1.000 → 1.000 / 1.000 |

**Rejected.** Direct overview weighting in `qf` reproduces the M2
unrestricted regression on Q3: AP falls by 0.150 and nDCG@10 by 0.300, and P@10
falls from 0.700 to 0.400. Q4 gains 0.006 AP and Q5 gains up to 0.029 nDCG@10,
but every aggregate early-precision and ranking metric is worse and recall is
unchanged. Lowering the rerank weight from 1 to 0.5 does not recover the loss.
The M3 default therefore keeps `qf=plot` and rerank weight 1. This also
confirms on the unrestricted pool that reranking the top 20 is a safer way to
use the short overview than mixing it into the first-stage query. Saved runs:
`runs/M3_BOOST_RW1.run`, `runs/M3_BOOST_RW05.run`.

## Review-join score mode

Problem: `score=max` makes a movie inherit only its single best matching review,
so Q2's rubric (one reviewer calls it predictable, another finds it
heartwarming) cannot be satisfied by combining two pieces of evidence. Trial:
change the block-join to `score=total` and `score=avg` for Q1/Q2 only; the three
story needs are untouched. Solr rejects `score=sum` with *"Unable to parse
ScoreMode from: sum"*, so `total` (Solr's name for summing child scores) is the
sum variant. Configs: `queries/m3/variants/reviewjoin_total/` and
`queries/m3/variants/reviewjoin_avg/`.

| System | P@5 | P@10 | AP | nDCG@10 | Recall@20 | MRR@10 |
|---|---:|---:|---:|---:|---:|---:|
| B (frozen baseline) | 0.880 | 0.780 | 0.497 | 0.737 | 0.588 | 1.000 |
| `score=total` | 0.840 | 0.640 | 0.429 | 0.607 | 0.542 | 1.000 |
| `score=avg` | 0.600 | 0.500 | 0.365 | 0.507 | 0.480 | 0.800 |

Per-need change from B (`total` / `avg`):

| Need | P@10 | AP | nDCG@10 | Recall@20 |
|---|---:|---:|---:|---:|
| Q1 | 0.800 → 0.500 / 0.000 | 0.326 → 0.178 / 0.022 | 0.697 → 0.489 / 0.000 | 0.364 → 0.212 / 0.121 |
| Q2 | 0.900 → 0.500 / 0.300 | 0.486 → 0.292 / 0.126 | 0.891 → 0.446 / 0.437 | 0.518 → 0.444 / 0.222 |
| Q3 | 0.700 → 0.700 / 0.700 | 0.452 → 0.452 / 0.452 | 0.679 → 0.679 / 0.679 | 0.556 → 0.556 / 0.556 |
| Q4 | 0.900 → 0.900 / 0.900 | 0.460 → 0.460 / 0.460 | 0.603 → 0.603 / 0.603 | 0.500 → 0.500 / 0.500 |
| Q5 | 0.600 → 0.600 / 0.600 | 0.763 → 0.763 / 0.763 | 0.816 → 0.816 / 0.816 | 1.000 → 1.000 / 1.000 |

Review counts of the top-10 movies show why both alternatives fail:

| System | Q1 mean / max / >=5 reviews | Q2 mean / max / >=5 reviews |
|---|---:|---:|
| `score=max` (B) | 9.5 / 19 / 8 of 10 | 4.3 / 8 / 4 of 10 |
| `score=total` | 16.5 / 34 / 10 of 10 | 6.5 / 12 / 8 of 10 |
| `score=avg` | 1.4 / 3 / 0 of 10 | 2.8 / 5 / 2 of 10 |

`total` rewards movies simply for having many reviews; `avg` rewards movies
with one strong review and few others. Neither produces the two-reviewer
consensus Q2 needs, and both lower pooled recall by replacing relevant
candidates in the top 20. Q3–Q5 are bitwise identical to B, confirming the
change was isolated. **Rejected**; keep `score=max`. Saved runs:
`runs/M3_JOIN_TOTAL.run`, `runs/M3_JOIN_AVG.run`.

## Phrase boosts

Problem: M2's fixed-pool word-pair boost (`pf2=qf`, `ps2=1`) reduced graded
ranking quality, so phrase evidence needs an unrestricted check before being
adopted or dismissed. Trial: an isolated phrase boost with `pf` on the searched
field and `ps=2`, inserted as local params in the main eDisMax query for story
needs and in the nested `childq` for review needs. Configs:
`queries/m3/variants/phrase/`.

| System | P@5 | P@10 | AP | nDCG@10 | Recall@20 | MRR@10 |
|---|---:|---:|---:|---:|---:|---:|
| B (frozen baseline) | 0.880 | 0.780 | 0.497 | 0.737 | 0.588 | 1.000 |
| `pf=field`, `ps=2` | 0.880 | 0.780 | 0.497 | 0.737 | 0.588 | 1.000 |

All five top-20 lists are identical to B. Solr's parsed query confirms that
the phrase clause was actually applied: for Q3 it contains
`(plot:"? ? science fiction film astronaut ? stranded far from earth ? struggle ? survive ? return home"~2)`.
It simply does not change any ordering at slop 2 for these needs, because few
documents contain nearly the whole sentence in close proximity. **Not adopted**:
no benefit, and M2's separate `pf2` trial was harmful on the fixed pool. Saved
run: `runs/M3_PF.run`.

## Final decisions

The final lexical configuration is **the frozen M2 Setup B unchanged**:
`mm=1`, `qf=plot` / `qf=review_text`, `score=max`, no phrase boost, no analyzer
or schema change. P1's contribution here is the unrestricted verification of
each proposed change and the evidence for rejecting it, plus the shared
retrieval interface and search page.

| Change | Saved run | Evidence | Decision |
|---|---|---|---|
| `mm=2`, `tie=0.1` | `runs/M3_MM2.run` | P@10 +0.02, nDCG +0.013, but P@5 −0.04, AP −0.006; Q3/Q5 AP down | not adopted |
| `mm=70%`, `tie=0.1` | `runs/M3_MM70.run` | 0–2 results per need, Q5 empty | rejected |
| `qf=plot^1 overview^2 title^2`, rerank 1 | `runs/M3_BOOST_RW1.run` | Q3 AP −0.150, nDCG −0.300 | rejected |
| same, rerank 0.5 | `runs/M3_BOOST_RW05.run` | same Q3 loss, no recovery | rejected |
| review join `score=total` | `runs/M3_JOIN_TOTAL.run` | rewards movies with many reviews, pooled recall −0.046 | rejected |
| review join `score=avg` | `runs/M3_JOIN_AVG.run` | rewards single-review movies, pooled recall −0.108 | rejected |
| `pf=field`, `ps=2` | `runs/M3_PF.run` | identical rankings to B | not adopted |
| Analyzer / KStem change | M2 verification | KStem already handles the observed variants; changing it needs a reindex | not attempted |
| Character trigrams | M2 scratch-core trial | no typo gain, promoted judged nonrelevant Q3/Q5 films | rejected (M2) |
| Extra query stopwords | M2 fixed-pool trial | lower P@10, MAP and nDCG than the stock list | rejected (M2) |
| WordNet synonyms | M2 fixed-pool trial | Q3 AP up but Q4 nDCG 0.631 → 0.426 | rejected (M2) |

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
python3 scripts/run_system.py --system m3_lexical \
  --queries queries/m3/variants/boosts_rw1 --uri http://127.0.0.1:18984/solr --run-id M3_BOOST_RW1
python3 scripts/run_system.py --system m3_lexical \
  --queries queries/m3/variants/boosts_rw05 --uri http://127.0.0.1:18984/solr --run-id M3_BOOST_RW05
python3 scripts/run_system.py --system m3_lexical \
  --queries queries/m3/variants/reviewjoin_total --uri http://127.0.0.1:18984/solr --run-id M3_JOIN_TOTAL
python3 scripts/run_system.py --system m3_lexical \
  --queries queries/m3/variants/reviewjoin_avg --uri http://127.0.0.1:18984/solr --run-id M3_JOIN_AVG
python3 scripts/run_system.py --system m3_lexical \
  --queries queries/m3/variants/phrase --uri http://127.0.0.1:18984/solr --run-id M3_PF
python3 scripts/trec_eval_run.py runs/B.run runs/M3_MM2.run runs/M3_MM70.run \
  runs/M3_BOOST_RW1.run runs/M3_BOOST_RW05.run \
  runs/M3_JOIN_TOTAL.run runs/M3_JOIN_AVG.run runs/M3_PF.run --per-query
```
