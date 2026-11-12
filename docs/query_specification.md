# Setup B movie queries

**Core:** `movies`  
**Endpoint:** `http://localhost:8983/solr/movies/select`  
**Run date:** 2026-11-09  
**Result depth:** 20 per query  
**Output:** one parent movie per result; `fl=movie_id,id,title,score`  
**Run/qrels identity:** numeric `movie_id`; Solr's unique `id` is `movie-<movie_id>`.

The query definitions have been revised since the saved run files were generated. The JSON query files are the current configuration; `runs/B_Q*.json` and `runs/B.run` are outputs from an earlier configuration and must be regenerated before comparing or judging this revision.

The current query definitions are in [`queries/setup_b/`](../queries/setup_b/). The shared runner [`scripts/solr_client.py`](../scripts/solr_client.py) writes the per-query top-20 outputs to `runs/B_Q1.json` through `runs/B_Q5.json` and a TREC-style run to [`runs/B.run`](../runs/B.run). Each JSON preserves all request parameters, `num_found`, and movie results; `movie_id` is the run document ID.

Re-run the saved Setup B configuration with:

```text
python scripts/solr_client.py --queries queries/setup_b --setup B
```

## Solr document and parent-ranking contract

`scripts/build_collection.py` writes nested review children with `doc_type=review` and `review_text`, `review_author`, `review_rating`, `review_created_at`. `solr/schema.json` defines those same field names and appropriate single-value field types; `doc_type` is a single-valued `text_general` field. The collection keeps review dates as `YYYY-MM-DD`; the Solr converter writes `YYYY-MM-DDT00:00:00Z` for its `pdate` field. Parents use `doc_type=movie`, preserve `movie_id`, and use Solr `id=movie-<movie_id>`.

Q1 and Q2 query review children with inner eDisMax and wrap that query in Solr's `{!parent which="doc_type:movie" score=max ...}` parser. Solr returns the parent movie once, with the maximum matching child-review score. Q3–Q5 search parent fields and use `fq=doc_type:movie`. Use this same movie-level output contract for Setup A and Setup B: one row per movie, `movie_id` for pooling/qrels, and the stable Solr `id` retained for traceability.

Indexed counts: **6,104 movies** and **12,057 review children**. The total index count is 18,161 documents including both parent and child documents.

## Query design and prior run output

All queries use `rows=20` and return movie identifiers, title, score, overview, and year. Prior counts below are Solr's `numFound` before the top-20 result window; saved run files record the parameters and results for the earlier configuration.

| ID | Current query design | Prior `numFound`* | Notes |
|---|---|---:|---|
| Q1 | Nested review search; broad OR matching over clever/witty/satirical wording and phrase boosts; comedy parent filter | 216 | Query variants include `wit`, `smart`, `satire`, `cerebral`, and descriptive phrases. |
| Q2 | Nested review search; cliché/predictability and warm-response variants; romance parent filter | 205 | Includes `predictable`, `sappy`, `sentimental`, hyphenation and spacing variants. |
| Q3 | Requires a space-travel concept and a stranded/left-behind concept; survival/rescue terms add evidence; science-fiction genre boost | 70 | Alternatives include `cosmonaut`, `spacecraft`, `marooned`, and `lost in space`. |
| Q4 | Requires a serial-killing concept; FBI/investigator wording is optional; crime/thriller genre boosts | 11 | Broader investigator wording can match plots that omit “FBI.” |
| Q5 | Requires a De Niro cast match (including `Deniro`); searches plot/overview for organized-crime variants; crime boost | 14 | Includes `Cosa Nostra`, `Italian-American`, and `Italian American`. |

\*These counts are from the earlier saved run files, not the current query definitions. Query-level alternatives are hand-curated and should be checked for precision as well as recall. The schema already folds accents, lowercases, removes English stopwords, and applies KStem; it does not provide synonym expansion. These query changes do not add lemmatization or non-English support.

Prior manual inspection found the expected recall/precision tradeoff, but it does not evaluate the current revision. Rerun Setup B before treating result counts, ranks, or titles as current. Qrels and evaluation metrics are still needed to determine whether expansions improve retrieval quality.

## Judgment and evaluation status

For evaluation, rerun the current Setup B queries, pool Setup A and Setup B at the same depth, deduplicate and judge by `movie_id`, then calculate metrics using shared qrels. **No qrels or judgments exist yet, so no evaluation metrics are reported.** Treat `numFound` as candidate counts, not relevance counts or judgments.

## Archive note

Setup A's definitions are in [`queries/setup_a/`](../queries/setup_a/), with saved results in [`runs/A_Q1.json`](../runs/A_Q1.json) through `runs/A_Q5.json` and a TREC-style run in [`runs/A.run`](../runs/A.run). Both setups use numeric `movie_id` as the run identifier and return parent movies, so they can be pooled by that field. The baseline uses plain field queries (review text for Q1–Q2 and plot for Q3–Q5); Q1–Q2 use the parent block-join parser, while Q3–Q5 filter to movie parents. See the query files for exact baseline clauses.
