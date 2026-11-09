# Frozen Setup B movie queries

**Core:** `movies`  
**Endpoint:** `http://localhost:8983/solr/movies/select`  
**Run date:** 2026-11-09  
**Result depth:** 20 per query  
**Output:** one parent movie per result; `fl=movie_id,id,title,score`  
**Run/qrels identity:** numeric `movie_id`; Solr's unique `id` is `movie-<movie_id>`.

The frozen query definitions are in [`queries/setup_b/`](../queries/setup_b/). The runner [`scripts/run_setup_b.py`](../scripts/run_setup_b.py) writes the per-query top-20 outputs to `runs/B_Q1.json` through `runs/B_Q5.json` and a TREC-style run to [`runs/B.run`](../runs/B.run). Each JSON preserves all request parameters, `num_found`, and movie results; `movie_id` is the run document ID.

Re-run the saved Setup B configuration with:

```text
python scripts/run_setup_b.py
```

## Solr document and parent-ranking contract

`scripts/build_collection.py` writes nested review children with `doc_type=review` and `review_text`, `review_author`, `review_rating`, `review_created_at`. `solr/schema.json` defines those same field names and appropriate single-value field types; `doc_type` is a single-valued `text_general` field. The collection keeps review dates as `YYYY-MM-DD`; the Solr converter writes `YYYY-MM-DDT00:00:00Z` for its `pdate` field. Parents use `doc_type=movie`, preserve `movie_id`, and use Solr `id=movie-<movie_id>`.

Q1 and Q2 query review children with inner eDisMax and wrap that query in Solr's `{!parent which="doc_type:movie" score=max ...}` parser. Solr returns the parent movie once, with the maximum matching child-review score. Q3–Q5 search parent fields and use `fq=doc_type:movie`. Use this same movie-level output contract for Setup A and Setup B: one row per movie, `movie_id` for pooling/qrels, and the stable Solr `id` retained for traceability.

Indexed counts: **6,104 movies** and **12,057 review children**. The total index count is 18,161 documents including both parent and child documents.

## Frozen parameters and observed retrieval

All queries used `rows=20` and `fl=movie_id,id,title,score`. Counts below are Solr's `numFound` before the top-20 result window. Each `runs/B_Qn.json` records every query parameter and returned row.

| ID | Final query design | `numFound` | Sample top results (`movie_id`) |
|---|---|---:|---|
| Q1 | Child eDisMax: `clever witty intelligent sharp sophisticated comedy humor`; `qf=review_text`, `pf=review_text^3`, `ps=3`, `mm=2`; parent filter `genres:comedy` | 186 | She's Out of My League (34016), Operation Fortune: Ruse de Guerre (739405), Wallace & Gromit: Vengeance Most Fowl (929204) |
| Q2 | Child eDisMax: `romance romantic cliché predictable formulaic heartwarming feel-good`; `qf=review_text`, `pf=review_text^3`, `ps=3`, `mm=2`; parent filter `genres:romance` | 185 | The Idea of You (843527), 13 Going on 30 (10096), Crazy Rich Asians (455207) |
| Q3 | eDisMax: `astronaut stranded space survival`; `qf=overview^3 plot^2 title^1 genres^1`, `pf=overview^3 plot^2`, `ps=4`, `mm=2`; parent filter `doc_type:movie`; `bq=genres:"science fiction"^2` | 60 | Mutant Aliens (30863), The Martian (286217), Zathura: A Space Adventure (6795) |
| Q4 | eDisMax: `FBI "serial killer"`; `qf=overview^3 plot^2`, `pf=overview^2 plot^2`, `ps=4`, `mm=2`; parent filter `doc_type:movie`; `bq=genres:crime^1.5 genres:thriller^1.5` | 11 | Solace (339527), Longlegs (1226578), Kiss the Girls (9437) |
| Q5 | eDisMax: `+cast.name:"Robert De Niro" +(mafia mob "organized crime" "crime family" gangster)`; `qf=cast.name^4 overview^3 plot^2`, `pf=cast.name^5 overview^2`, `ps=3`, `mm=2`; parent filter `doc_type:movie`; `bq=genres:crime^1.5` | 13 | The Irishman (398978), The Godfather Part II (240), GoodFellas (769) |

Manual inspection of the adopted variants found the expected recall/precision tradeoff. Q3 now returns 60 candidates: The Martian and Slingshot are strong matches, while Zathura and Deep Impact illustrate false positives. Q4 returns 11 candidates; Solace, Longlegs, and Switchback fit the FBI/serial-killer need, while Kiss the Girls and The Little Things need careful judgments against the FBI requirement. Q5 returns 13 candidates; The Irishman, The Godfather Part II, GoodFellas, and Casino fit, while Ronin (Russian mob) and Cop Land are likely false positives. Q1 manual checks found both clever/witty wording and criticism of lowbrow humor in She's Out of My League; Wallace & Gromit: Vengeance Most Fowl was described as clever, witty, and sophisticated. Q2 checks found explicit formula/cliché criticism for The Idea of You and a warm response for 13 Going on 30.

## Judgment and evaluation status

The query settings are frozen before pooling. Pool Setup A and Setup B at the same depth, deduplicate and judge by `movie_id`, then calculate metrics using the shared qrels. **No qrels or judgments exist yet, so no evaluation metrics are reported.** Treat the observed `numFound` and sample titles above as retrieval-run output, not relevance counts or judgments.

## Archive note

The supplied `PRI.zip` contains `PRI_WebScraper-main`, a plant database project; its schemas and example queries do not describe this movie index, and it does not provide this collection's Setup A contract. These movie queries use the movie project already present in this workspace. Confirm Setup A's run-file columns with its owner before comparing the two runs; keep the movie-level result and `movie_id` contract above for both.
