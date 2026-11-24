# Movie retrieval with natural-language queries

Each Q1–Q5 JSON file contains the sentence sent to Solr, its evidence source, and its structured constraints. The A and B copies are identical. The shared query builder in `scripts/solr_client.py` contains the ranking rules. No rule looks up a query ID. Evaluation checks that both sets of definitions agree.

| Need | Evidence | Structured constraints in both setups |
|---|---|---|
| Q1 · Clever comedy | Best matching review | Comedy. The judging rubric requires praise for wit or sharp writing. |
| Q2 · Predictable yet heartwarming romance | Best matching review | Romance. Judges consider both the predictability and the warm reception across reviews. |
| Q3 · Stranded astronauts trying to survive or get home | Story | Science Fiction |
| Q4 · FBI investigation of serial killings | Story | Crime or Thriller |
| Q5 · De Niro and an Italian-American Mafia family | Story | Cast phrase De Niro or Deniro, excluding plots containing the phrase “Russian mafia” |

The Q3 and Q4 genre constraints apply equally to A and B. They can exclude relevant films with incomplete genre tags. The inherited Q5 exclusion can also exclude a story that mentions multiple organizations. The review join takes the maximum child score, so it cannot directly combine two different reviewers’ opinions on Q2.

## Saved systems

- **A** uses eDisMax as a single-field bag-of-words baseline. It searches `review_text` or `plot` with `q.op=OR` and `mm=1`.
- **B** takes A’s top 20 plot matches and reranks them by adding the overview match score with weight 1. Both stages use the same sentence. The Solr rerank parser uses `reRankDocs=20` and `reRankWeight=1`. Review rankings are identical in A and B.
- Both send the complete sentence as the dereferenced `text` parameter in a form POST to the same `movies/select` endpoint. Review searches use `{!parent which="doc_type:movie" score=max v=$childq}`. All final results are filtered to movie parents.
- Both request 20 movies and save numeric `movie_id`, rank and score in TREC format. The runner checks the Solr key `movie-<movie_id>` and records the full request in the per-query JSON. Accent folding, lowercasing, Solr English stopwords and KStem apply in both systems.

## Full-collection results

All 84 newly retrieved pairs received manual grades. Together with 135 prior grades, the qrels contain 219 assessed pairs. The initial unrestricted A/weighted-overview trial pooled 130 pairs. The final A/B pool contains 100 distinct pairs, all judged. The unrestricted comparisons use trec_eval, the same 219 grades, binary threshold 1 and depth 20. nDCG uses the grade as its gain. The checked-in precision–recall curves use trec_eval v10.0.

| Unrestricted system | P@5 | P@10 | MAP | nDCG@10 | Recall@20 | MRR@10 |
|---|---:|---:|---:|---:|---:|---:|
| A, single field | .800 | .740 | .465 | .688 | .588 | .900 |
| Direct weighted overview trial | .800 | .740 | .456 | .680 | .572 | .900 |
| Equal-weight rank fusion of A and the direct trial | .880 | .740 | .467 | .693 | .561 | .900 |
| **B, rerank the top 20** | **.880** | **.780** | **.497** | **.737** | **.588** | **1.000** |

Direct overview matching displaced relevant Q3 candidates. Its Q3 AP fell from .378 to .228. Rank fusion scored each candidate by summing 1/(60 + rank) across the two top-20 lists, breaking ties by ascending movie ID. It lost pooled recall. Reranking improved early precision while retaining all baseline candidates. The direct trial ranking is saved in [B_overview_trial.run](../runs/B_overview_trial.run).

Q1 and Q2 kept identical review rankings. Q3 gained two relevant movies in the top ten. Q4 gained one in the top five. Q5 moved its first relevant movie from second to first. Recall@20 is equal by design. These results describe the five needs used for system selection. [Per-query metrics and deltas](../eval/output/results.md)

## Controlled experiments, 23 November 2026

The 135 manually graded query–movie pairs from Milestone 2 form a **fixed candidate set** selected by the historical runs. For each need a Solr filter admits its previously judged IDs. Scoring still uses the complete index statistics, the same structured constraints and depth 20. The diagnostic preserves the original Solr rank order and exponential nDCG gain (2^grade − 1). Binary relevance is grade ≥1 and recall uses all judged positives for the need. Compare values within this table. This diagnostic measures ranking among known candidates. It cannot establish recall of newly discovered movies. These five needs were used for system selection.

| Trial | P@5 | P@10 | MAP | nDCG@10 | Recall@20 | MRR@10 |
|---|---:|---:|---:|---:|---:|---:|
| A, single field | .840 | .760 | .717 | .757 | .815 | 1.000 |
| Direct weighted overview | .880 | .760 | .719 | .763 | .826 | 1.000 |
| A + adjacent word-pair boosts | .840 | .760 | .724 | .736 | .823 | 1.000 |
| Direct overview + word-pair boosts | .840 | .760 | .712 | .739 | .811 | 1.000 |
| Direct overview + extra query stopwords | .840 | .740 | .708 | .751 | .818 | 1.000 |
| Direct overview + selected plot synonyms | .840 | .720 | .702 | .723 | .826 | 1.000 |
| Direct overview + trigrams, clean text | .880 | .740 | .712 | .753 | .826 | 1.000 |
| Direct overview, one misspelling per need | .880 | .700 | .683 | .723 | .814 | .900 |
| Direct overview + trigrams, same misspellings | .840 | .680 | .664 | .674 | .814 | .900 |
| B, rerank the top 20 | .920 | .760 | .727 | .781 | .815 | 1.000 |

Word-pair boosts (`pf2=qf`, `ps2=1`) reduced graded ranking quality, particularly in combination with direct overview weighting. The direct field boost gave a small gain on this restricted set, which reversed in the unrestricted trial above.

**N-grams.** An isolated Solr core indexed copies of the review, overview and plot fields using token-internal character trigrams at both index and query time. These fields used standard tokenization, folding, lowercasing and the stock stop list, with trigrams in place of stemming. The ordinary fields kept their original analyzers. Each auxiliary field received one tenth of its ordinary query weight. Each query contained one substitution, deletion or transposition: `wity`, `heartwaming`, `astronatus`, `kiler`, or `Maifa`. The typo runs found the same proportion of known positives at 20, but trigrams pushed a judged nonrelevant Q3 film, *Guardians of the Galaxy*, to rank two. On Q5 the number of judged nonrelevant films in the top ten rose from two to four. The shared schema retains its original analyzer.

**Stopwords.** Removing the generic request terms `want`, `film(s)`, `movie(s)` and `reviewer(s)` at query time lowered aggregate precision, MAP and nDCG relative to direct overview matching. The existing English list was sufficient for this comparison.

**Synonyms.** The English thesaurus is a WordNet extraction in JSON Lines, with a record per sense, part of speech, gloss and synonym list. Multiword lemmas use underscores. Its README refers to the Princeton WordNet license, which permits reuse subject to retaining its copyright, conditions and disclaimer. The experiment tested two reviewed plot senses: astronaut → cosmonaut/spaceman and serial killer → serial murderer. It added alternatives only to story text, preserving the multiword alternative as a phrase. Unqualified *agent* also has broker and substance senses. The selected expansions improved Q3 AP (.594 to .631) but lowered Q4 nDCG@10 (.631 to .426) and aggregate MAP. No synonym resource is distributed with the retrieval system. [English thesaurus](https://github.com/zaibacu/thesaurus) · [WordNet license](https://wordnet.princeton.edu/license-and-commercial-use)

## Reproduce

Run the two normal retrieval commands from the repository root. The JSON and TREC artifacts under `runs/` are unrestricted by judgment ID.

```shell
python scripts/solr_client.py --queries queries/setup_a --setup A
python scripts/solr_client.py --queries queries/setup_b --setup B
python eval/pool.py
python -X utf8 eval/judge.py --judge "Your Name"
python eval/metrics.py
```

For the fixed-pool experiments use a fresh disposable Solr 10.0.0 core on a separate port. The preparation step loads the same nested collection and adds the auxiliary fields there. On subsequent runs omit `--prepare`. The scratch and project cores produced identical fixed-pool rankings for the baseline and the direct overview trial.

```shell
docker run --rm -d --name pri-typo-lab -p 127.0.0.1:18983:8983 -e SOLR_HEAP=768m solr:10.0.0 solr-precreate typo_eval
# Once the core is serving requests:
python eval/experiment.py --prepare
docker stop pri-typo-lab
```

The script prints per-need and aggregate results using the [135 frozen manual grades](../eval/data/qrels_milestone2.csv). The [current evaluation](../eval/output/results.md) reports all six metrics for the unrestricted runs. The [original Python scores](https://github.com/GitHubLDh/Information-Processing-and-Retrieval/blob/f06387fe46592d9c44279da862e73639a4100915/eval/results.md) and the [historical trec_eval report charts](https://github.com/GitHubLDh/Information-Processing-and-Retrieval/tree/74e164fd2054d32c0b4a6dd3e41cb3ec6f46bf34/report/figures) describe the earlier hand-written queries.
