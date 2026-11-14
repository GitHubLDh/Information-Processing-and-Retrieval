# Index verification (M2)

Verification of the live Solr index against `data/final/collection.jsonl`.
Run on 2026-11-13 with Solr 10.0.0 / Lucene 10.3.2 (`solr:10`, container
`solr_pri`, core `movies`).

## Reproduce

```bash
bash solr/startup.sh
python3 scripts/verify_index.py
```

`scripts/verify_index.py` is the reproducible check used in the demo. It reads
the collection and manifest, queries Solr, exercises the analyzer through
`/analysis/field`, and exits non-zero if a required check fails.

Expected summary:

```text
SUMMARY: 25 passed, 0 failed, 2 warning(s)
```

The two warnings are explained under "Findings" below; they are schema
behaviour, not index failures.

## Document counts

| Check | Expected | Actual |
|---|---:|---:|
| Manifest documents | 6,104 | 6,104 |
| `collection.jsonl` lines | 6,104 | 6,104 |
| Reviews in collection | 12,057 | 12,057 |
| Solr total documents (`*:*`) | 18,161 | 18,161 |
| Solr movie parents (`doc_type:movie`) | 6,104 | 6,104 |
| Solr review children (`doc_type:review`) | 12,057 | 12,057 |

The total is larger than the movie count because each review is indexed as a
nested child document.

## Sample document and children

Sample: `movie_id:11` (*Star Wars*, 1977).

- The parent is found once with `id=movie-11`, `doc_type=movie`, and non-empty
  `title`, `plot`, `cast.name`, and `crew_names`.
- `{!child of="doc_type:movie"}id:movie-11` returns its 7 review children, all
  with `doc_type=review` and ids `movie-11-review-0` … `movie-11-review-6`.
- `movie_id:2` (*Ariel*) is a parent with no review children; the same child
  query returns 0, confirming that blocks without children are valid.
- A manual spot check of `movie_id:155` (*The Dark Knight*, 14 reviews) also
  returned the correct parent document and metadata.

Note the child-parser direction: `{!child of=...}` takes a **parent** query.
`{!child of="doc_type:movie"}doc_type:review` is invalid because the main query
would match children; `{!child of="doc_type:movie"}id:movie-11` is correct.

## Analyzer (`textFoldLower`)

Checked through `/solr/movies/analysis/field` with
`analysis.fieldtype=textFoldLower`:

| Input | Final token |
|---|---|
| `Amélie` | `amelie` |
| `Café` | `cafe` |
| `Matrix` | `matrix` |
| `the`, `and` | removed (English stopwords) |
| `investigating` | `investigate` (KStem) |
| `runners` | `runner` (KStem) |
| `Moulins` | `moulin` (KStem) |

The chain is StandardTokenizer → ASCIIFolding → LowerCase → StopFilter →
KStem, identical for indexing and querying.

## Sanity queries

| Query | Matches |
|---|---:|
| `title:"star wars"` | 10 |
| `cast.name:"robert de niro"` | 47 |
| `plot:astronaut` | 41 |
| `{!parent which="doc_type:movie" score=max}review_text:clever` | 353 |
| `genres:comedy AND year:[2000 TO 2010]` | 476 |
| `runtime:[90 TO 120]` | 3,709 |
| `status:Released` | 6,064 |
| `original_language:en` | 4,891 |

`title:"star wars"` returning 10 is expected: the field is analyzed, so it also
matches franchise titles such as *Star Wars: Episode …*, not just the 1977 film.

## Findings

### 1. Display-only fields are exact-queryable through docValues

`solr/schema.json` marks `crew_roles.name`, `crew_roles.job`, and `cast.order`
as `indexed: false`, and the live schema confirms it. They are therefore **not
full-text searchable**: no tokenization, no stemming, no relevance scoring.

However, the default Solr field definitions enable docValues, so exact-value
queries still resolve:

| Query | Matches | Interpretation |
|---|---:|---|
| `crew_roles.job:Producer` | 5,665 | exact docValues lookup works |
| `crew_roles.job:producer` | 0 | string field is case-sensitive |
| `crew_roles.job:producers` | 0 | no stemming |
| `cast.order:0` | 6,100 | exact numeric docValues lookup works |

This does not affect normal free-text retrieval (there is no catch-all field, so
an unfielded query such as `producer` does not hit these fields). If the team
wants these fields to be *strictly* unqueryable, add `"docValues": false` to
those three fields in `solr/schema.json` and rebuild the index. `cast.order` is
multi-valued, so it is not used for sorting and would not lose functionality.

### 2. Nesting uses block join, not `_nest_path_`

The documents are nested through `_childDocuments_`; Solr populates `_root_` but
leaves `_nest_parent_` empty. This is normal for anonymous block-join children.
The `{!parent which=...}` and `{!child of=...}` parsers both work on this
structure.

### 3. Nested child syntax is easy to get backwards

Use a parent query with `{!child}`:

```text
{!child of="doc_type:movie"}id:movie-11
```

not a child query (`doc_type:review`), which raises
`Parent query must not match any docs besides parent filter`.

## Screenshots still to capture for the demo

No headless browser is available in this environment, so capture these manually
during demo preparation:

1. Core overview — `http://localhost:8983/solr/#/movies`
2. Schema browser — `http://localhost:8983/solr/#/movies/schema`
3. Analysis screen — `http://localhost:8983/solr/#/movies/analysis`, choose
   field type `textFoldLower` and paste the sample from this document
4. Query screen — `http://localhost:8983/solr/#/movies/query` with
   `plot:astronaut`
5. Nested query — same screen with
   `{!parent which="doc_type:movie" score=max}review_text:clever`

## Note for the evaluation work

Separate from the index: `runs/B_Q1.json`, `B_Q2.json`, `B_Q3.json`, and
`B_Q5.json` are not valid UTF-8, so `json.load` fails on them. Rerun Setup B
after forcing UTF-8 decoding in `scripts/solr_client.py` before building the
qrels pool.
