# Document model and indexing (Milestone 2)

This document describes **what is indexed, how it is indexed, and why**. It is the
Milestone 2 companion to the Milestone 1 schema proposal in
[`docs/schema.md`](schema.md) and the machine-readable source schema in
[`docs/collection.schema.json`](collection.schema.json). It reflects the index that
`scripts/build_collection.py`, `solr/schema.json`, and `solr/startup.sh` actually
build, not the earlier proposal.

Related: [`docs/index-verification.md`](index-verification.md).

## 1. Summary

| Item | Value |
|---|---:|
| Movie documents | 6,104 |
| Review child documents | 12,057 |
| Total Solr documents | 18,161 |
| Solr core | `movies` |
| Solr version used for verification | 10.0.0 (Lucene 10.3.2) |
| Source collection | `data/final/collection.jsonl` |
| Solr upload file | `data/final/solr_documents.json` |
| Index schema | `solr/schema.json` |

The collection has one **parent** document per movie and zero or more **child**
documents per review. Solr's block-join support lets a query search review text and
still return the parent movie, which is why the index has more documents than the
collection.

## 2. Source collection

### 2.1 One document per movie

`data/final/collection.jsonl` is JSON Lines: one JSON object per movie, one object
per line. JSONL was chosen in Milestone 1 because the collection mixes:

- scalars (`year`, `runtime`, `vote_average`),
- lists (`genres`, `director`, `crew_names`),
- nested objects (`cast`, `crew_roles`, `wikipedia`, `reviews`),
- long text (`plot`, review `text`).

A CSV would force the lists and nested objects into joined strings and break
per-field querying. JSONL keeps the structure native and feeds Solr directly.

The source document is validated against [`docs/collection.schema.json`](collection.schema.json)
before it is written. The schema requires `movie_id`, `title`, `genres`, `director`,
`cast`, `crew_names`, `crew_roles`, `reviews`, and `num_reviews`; nullable fields use
`null`, never `""`, `0`, or `"N/A"`.

A shortened example (`movie_id:155`, *The Dark Knight*):

```json
{
  "movie_id": 155,
  "title": "The Dark Knight",
  "release_date": "2008-07-16",
  "year": 2008,
  "runtime": 152,
  "original_language": "en",
  "status": "Released",
  "overview": "Batman raises the stakes in his war on crime...",
  "tagline": "Welcome to a world without rules.",
  "genres": ["Action", "Thriller", "Crime"],
  "vote_average": 8.5,
  "vote_count": 35160,
  "director": ["Christopher Nolan"],
  "cast": [
    {"name": "Christian Bale", "character": "Bruce Wayne", "order": 0},
    {"name": "Heath Ledger", "character": "Joker", "order": 1}
  ],
  "crew_names": ["Christopher Nolan", "Michael Uslan"],
  "crew_roles": [
    {"name": "Christopher Nolan", "job": "Director"},
    {"name": "Michael Uslan", "job": "Executive Producer"}
  ],
  "wikipedia": {
    "title": "The Dark Knight",
    "url": "https://en.wikipedia.org/wiki/The_Dark_Knight",
    "wikidata_id": "Q163872",
    "imdb_id": "tt0468569",
    "match_method": "tmdb"
  },
  "plot": "In Gotham City, the Joker...",
  "reviews": [
    {"author": "talisencrw", "rating": 10.0, "text": "This has no competition...", "created_at": "2016-05-25"}
  ],
  "num_reviews": 14
}
```

### 2.2 Source field groups

| Group | Fields | Role |
|---|---|---|
| Identity | `movie_id`, `title`, `original_title`, `release_date`, `year` | primary key, display, filtering |
| Metadata | `runtime`, `original_language`, `status`, `overview`, `tagline`, `genres`, `vote_average`, `vote_count`, `popularity`, `budget`, `revenue` | description, filters, ranking signals |
| People | `director`, `cast`, `crew_names`, `crew_roles` | cast/crew search and display |
| Provenance | `wikipedia` | source article and identifiers |
| Narrative | `plot` | long free text from the Wikipedia Plot section |
| Reception | `reviews`, `num_reviews` | review text, author, rating, date |

### 2.3 Missing values

`null` is the only missing marker. A genuinely empty list stays `[]` (for example
`genres: []` or `reviews: []`), and a genuine zero stays `0` (`vote_count: 0`).
Source placeholders are normalized during the build:

- `runtime = 0` → `null` (64 movies in the final collection),
- `budget = 0` / `revenue = 0` → `null` (2,374 / 2,242 movies),
- empty `overview` / `tagline` → `null` (10 / 1,135 movies),
- `vote_average = 0` when `vote_count = 0` → `null` (139 movies).

This matters for the index because Solr does not index `null` fields. A null field
is simply absent from the document, which is why coverage in Section 8 is below
100% for some fields.

## 3. Indexing pipeline

```text
data/interim/*.csv
        │
        ▼
scripts/build_collection.py
  ├── join by numeric movie_id
  ├── drop movies without a usable plot
  ├── drop plots shorter than 50 words
  ├── strip footnote markers
  ├── validate against docs/collection.schema.json
  ├── write data/final/collection.jsonl
  ├── write data/final/collection_manifest.json
  └── write data/final/solr_documents.json
        │
        ▼
solr/startup.sh
  ├── start Docker container solr_pri (solr:10)
  ├── create core "movies"
  ├── POST solr/schema.json to /schema
  ├── POST solr_documents.json to /update?commit=true
  └── verify doc_type:movie and doc_type:review counts
        │
        ▼
Solr core "movies"
  ├── parent documents  (doc_type=movie,  6,104)
  └── child documents   (doc_type=review, 12,057)
```

### 3.1 Build the collection

`scripts/build_collection.py` reads five interim files:

| Input | Produces |
|---|---|
| `movies_clean.csv` | identity and structured metadata |
| `reviews_clean.csv` | the `reviews` array, grouped per movie |
| `castcrew_agg.csv` | `director`, `cast`, `crew_names`, `crew_roles` |
| `movies_wikipedia_links.csv` | the `wikipedia` object |
| `wikipedia_plot.csv` | the `plot` text |

The join key is the numeric TMDB `movie_id`. Non-numeric IDs are rejected (the CSV
phantom-row bug). Cast and crew are already aggregated to one row per movie, so the
join does not multiply movie rows. Reviews are grouped into a list per movie.

Filters applied in the final run:

| Filter | Effect |
|---|---|
| Require a Wikipedia plot with status `ok` | dropped 3,231 movies |
| Require at least 50 plot words | dropped 374 more |
| Strip footnote markers (`[1]`, `[a]`, ...) | removes token noise from plots |
| Validate every document against the JSON Schema | build fails on an invalid document |

Result: **6,104 movies** carrying **12,057 reviews**. The manifest records the
counts, filters, build date, and git commit:

```json
{
  "build_script": "scripts/build_collection.py",
  "git_commit": "68b4f28...",
  "filters": { "reject_non_numeric_movie_id": true, "require_plot": true,
               "strip_footnote_markers": true, "min_plot_words": 50 },
  "output": { "documents": 6104, "dropped_no_plot": 3231,
              "dropped_below_50_words": 374 }
}
```

### 3.2 Convert to Solr documents

`to_solr_document()` in `scripts/build_collection.py` makes three structural
changes:

1. **Parent identity.** Adds `id = movie-<movie_id>` and `doc_type = movie`.
2. **Flattening.** Converts nested source objects into Solr's flat field names:
   - `cast[]` → `cast.name[]`, `cast.character[]`, `cast.order[]`
   - `crew_roles[]` → `crew_roles.name[]`, `crew_roles.job[]`
   - `wikipedia{}` → `wikipedia.title`, `wikipedia.url`, `wikipedia.wikidata_id`,
     `wikipedia.imdb_id`, `wikipedia.match_method`
3. **Review children.** Each review becomes a child document:
   - `id = movie-<movie_id>-review-<n>`
   - `doc_type = review`
   - `review_text`, `review_author`, `review_rating`, `review_created_at`
   - review dates `YYYY-MM-DD` become `YYYY-MM-DDT00:00:00Z` because Solr's
     `pdate` field requires a full timestamp.

The parent receives the children in `_childDocuments_`:

```json
{
  "id": "movie-11",
  "doc_type": "movie",
  "title": "Star Wars",
  "_childDocuments_": [
    {"id": "movie-11-review-0", "doc_type": "review", "review_text": "..."},
    {"id": "movie-11-review-1", "doc_type": "review", "review_text": "..."}
  ]
}
```

Solr indexes the children before the parent and populates `_root_` with the parent
id. This is what makes block joins possible. The declared `_nest_parent_` field
remains empty for these documents; do not use it as the parent link.

### 3.3 Apply the schema and index

`solr/startup.sh` is destructive and reproducible:

1. removes any old `solr_pri` container;
2. starts `solr:10` and pre-creates the `movies` core;
3. applies `solr/schema.json` through the Solr Schema API;
4. uploads `data/final/solr_documents.json` with `commit=true`;
5. compares the indexed counts with the collection counts and fails on a mismatch.

`commit=true` is required before documents become visible to searches.

### 3.4 Reproduce

```bash
python3 scripts/build_collection.py   # rebuild source collection and Solr docs
bash solr/startup.sh                  # recreate the core and reindex
python3 scripts/verify_index.py       # verify counts, analyzers, and queries
```

To stop the service:

```bash
docker rm -f solr_pri
```

## 4. Solr schema

Throughout this section, **Indexed** means the field is searchable, **Stored**
means it is returned in results, and **Multi** means it can hold a list.

### 4.1 Field types

`solr/schema.json` adds one custom field type and uses standard Solr types:

| Type | Used for | Behaviour |
|---|---|---|
| `textFoldLower` | free text | StandardTokenizer → ASCIIFolding → LowerCase → English stopwords → KStem |
| `string` | enumerations and exact identifiers | no analysis; exact, case-sensitive matching |
| `plong` | large integers | numeric filters and ranges |
| `pint` | integers | numeric filters and ranges |
| `pfloat` | floating point | numeric filters and ranges |
| `pdate` | dates | date ranges and sorting |
| `text_general` | `doc_type` only | Solr's default text analysis; sufficient for the `movie`/`review` discriminator |

### 4.2 Identity and technical fields

| Field | Type | Indexed | Stored | Multi | Source / purpose |
|---|---|---:|---:|---:|---|
| `id` | `string` | yes | yes | no | Solr unique key from the base configset; `movie-<id>` or `movie-<id>-review-<n>` |
| `movie_id` | `plong` | yes | yes | no | TMDB id; run and qrels identity; numeric filters |
| `doc_type` | `text_general` | yes | yes | no | `movie` for parents, `review` for children |
| `_nest_parent_` | `string` | yes | yes | no | declared for nested documents; empty for this collection |
| `_root_` | — | — | — | — | populated automatically by Solr with the parent id |

`id` is not in the `add-field` list because `solr-precreate` already defines it as
the unique key. The collection uses `movie_id` for evaluation and `id` for
traceability; they must not be confused.

### 4.3 Searchable full-text fields

All use `textFoldLower` and are both indexed and stored.

| Field | Multi | Why it is searchable |
|---|---:|---|
| `title` | no | users search titles and partial titles |
| `original_title` | no | non-English titles are still useful |
| `overview` | no | TMDB's short plot is the strongest compact plot signal |
| `tagline` | no | short thematic phrases |
| `genres` | yes | genre words are part of natural-language needs |
| `director` | yes | people search by director |
| `cast.name` | yes | people search by actor |
| `cast.character` | yes | users remember characters, not only actors ("who plays Superman") |
| `crew_names` | yes | names are meaningful search targets |
| `wikipedia.title` | no | article title is a useful alternate title |
| `plot` | no | the main long-text retrieval signal |
| `review_text` | no | review text is searched through nested child documents |

### 4.4 Exact, numeric, and date fields

| Field | Type | Indexed | Stored | Purpose |
|---|---|---:|---:|---|
| `release_date` | `pdate` | yes | yes | date ranges and sorting |
| `year` | `pint` | yes | yes | decade filters, sorting |
| `runtime` | `pint` | yes | yes | runtime filters |
| `original_language` | `string` | yes | yes | exact language filter (`en`, `fr`, ...) |
| `status` | `string` | yes | yes | exact status filter (`Released`, ...) |
| `vote_average` | `pfloat` | yes | yes | rating filters and sorting |
| `vote_count` | `pint` | yes | yes | popularity/reliability filters |
| `popularity` | `pfloat` | yes | yes | popularity filters and sorting |
| `budget` | `plong` | yes | yes | budget filters |
| `revenue` | `plong` | yes | yes | revenue filters |
| `num_reviews` | `pint` | yes | yes | review-count filters |

These fields use exact or numeric types rather than `textFoldLower` on purpose:
`status:Released` and `original_language:en` should be exact, not stemmed or
accent-folded. Numbers and dates need range queries and sorting.

### 4.5 Display-only fields

These are stored so the result page can show them, but they are not in the
full-text index:

| Field | Type | Indexed | Stored | Multi | Why display-only |
|---|---|---:|---:|---:|---|
| `crew_roles.name` | `string` | no | yes | yes | paired with `crew_roles.job` for display |
| `crew_roles.job` | `string` | no | yes | yes | job words must not make a movie relevant |
| `cast.order` | `pint` | no | yes | yes | billing order for display; not a search signal |
| `wikipedia.url` | `string` | no | yes | no | provenance link |
| `wikipedia.wikidata_id` | `string` | no | yes | no | provenance identifier |
| `wikipedia.imdb_id` | `string` | no | yes | no | provenance identifier |
| `wikipedia.match_method` | `string` | no | yes | no | provenance/debugging |
| `review_author` | `string` | no | yes | no | display only |
| `review_rating` | `pfloat` | no | yes | no | display only |
| `review_created_at` | `pdate` | no | yes | no | display only |

### 4.6 Review child fields

| Field | Type | Indexed | Stored | Purpose |
|---|---|---:|---:|---|
| `review_text` | `textFoldLower` | yes | yes | the searchable review body |
| `review_author` | `string` | no | yes | display |
| `review_rating` | `pfloat` | no | yes | display |
| `review_created_at` | `pdate` | no | yes | display |
| `doc_type` | `text_general` | yes | yes | identifies the child as `review` |

Review children are separate documents because one movie can have up to 53 reviews.
Flattening the reviews into the parent would either duplicate the movie fields per
review or force a single concatenated review field, which would destroy per-review
scoring and the ability to return the best matching review.

### 4.7 Why these choices

- **`textFoldLower` for natural language.** The corpus is predominantly English
  Wikipedia and TMDB text. Case folding, accent folding, stopword removal, and KStem
  make queries robust to capitalization, accents, and common word variants.
- **`string` for enumerations.** Language and status are controlled vocabularies;
  exact matching avoids false positives from stemming.
- **Numeric/date types for filters.** Ranges such as `year:[2000 TO 2010]` and
  `runtime:[90 TO 120]` require numeric types.
- **`genres` as multi-valued text.** A movie has several genres, and users query
  genre words in natural language ("science fiction", "comedy").
- **`crew_names` searchable, `crew_roles.job` not.** A user may search for a person's
  name; a user should not retrieve a film merely because someone was credited as
  "Producer". This is the clearest example of a deliberate indexing decision in the
  schema.
- **No populated catch-all field.** The base configset defines `_text_`, but no
  `copyField` rules feed it, so an unfielded query such as `q=producer` resolves to
  `_text_:producer` and returns 0. Every meaningful query must name a field. This
  prevents display-only fields from leaking into general relevance and keeps the
  A/B query setups explicit. The cost is that queries must be written field by
  field.

## 5. Analyzer

### 5.1 Chain

`textFoldLower` is identical at index time and query time:

```text
StandardTokenizer → ASCIIFolding → LowerCase → StopFilter (English) → KStem
```

| Stage | Effect |
|---|---|
| StandardTokenizer | splits on spaces and punctuation; hyphens split words |
| ASCIIFolding | `Amélie` → `Amelie`, `Café` → `Cafe` |
| LowerCase | `Matrix` → `matrix` |
| StopFilter | removes English stopwords such as `the`, `and`, `of` |
| KStem | conservative English stemming: `investigating` → `investigate` |

### 5.2 Worked examples

Verified against the live index with `/analysis/field`:

| Input | Final token(s) |
|---|---|
| `Amélie` | `amelie` |
| `Café` | `cafe` |
| `Matrix` | `matrix` |
| `the`, `and` | removed |
| `investigating` | `investigate` |
| `runners` | `runner` |
| `Moulins` | `moulin` |
| `running` | `running` (KStem does not reduce it to `run`) |

### 5.3 Consequences for retrieval

- Search is case-insensitive.
- Accents are ignored; `Amelie` matches `Amélie`.
- Stopwords cannot be searched on their own.
- Word variants often match (`investigating` / `investigate`), but KStem is not a
  full lemmatizer (`running` stays `running`).
- Hyphenated text splits: `science-fiction` becomes `science` + `fiction`.
- `string` fields behave in the opposite way: `status:Released` works,
  `status:released` does not, and `original_language:en` works while `EN` does not.
- Phrase queries operate on the analyzed token stream. `title:"star wars"` matches
  10 documents because it also finds franchise titles containing that phrase.

### 5.4 Inspect the analyzer

Admin UI: `http://localhost:8983/solr/#/movies/analysis`, choose field type
`textFoldLower`, enter text, and press Analyze.

Command line:

```bash
curl -sG 'http://localhost:8983/solr/movies/analysis/field' \
  --data-urlencode 'analysis.fieldtype=textFoldLower' \
  --data-urlencode 'analysis.fieldvalue=Amélie investigating the Matrix' \
  --data-urlencode 'wt=json' \
  | jq -r '.analysis.field_types.textFoldLower.index[-1][] | .text'
```

Output:

```text
amelie
investigate
matrix
```

## 6. Searchable vs filterable vs display-only

### 6.1 The three roles

| Role | Meaning | Examples |
|---|---|---|
| Searchable | in the inverted index, contributes to score | `title`, `overview`, `plot`, `review_text`, `cast.name` |
| Filterable | exact or numeric constraint, usually in `fq` | `year`, `runtime`, `original_language`, `status`, `genres` |
| Display-only | stored for the result page, not searched | `crew_roles.job`, `cast.order`, `wikipedia.url`, `review_author` |

Some fields serve more than one role: `year` is filterable and displayable;
`genres` is searchable and filterable; `plot` is searchable and displayable.

### 6.2 The `crew_roles` decision

`crew_roles` contains every crew credit as `{name, job}`. Indexing `job` as text
would make a query such as *"a movie about a producer"* return the films with the
most producers, regardless of their plot. That is why `crew_roles.job` is stored
but not indexed, while `crew_names` is indexed:

- `crew_names` answers "which films involve Christopher Nolan?"
- `crew_roles.job` answers "what was Christopher Nolan's credit on this film?" for
  display, but never contributes to retrieval.

`cast.character` is searchable for the opposite reason: users legitimately search
for characters ("matching movies where Christopher Reeve plays Superman"), so the
character name is a real search signal.

### 6.3 The docValues caveat

`indexed=false` means "not in the inverted text index", not "impossible to query".
Solr enables docValues by default for `string`, `pint`, and `pfloat` fields, and
docValues can answer exact-value queries:

| Query | Matches | Interpretation |
|---|---:|---|
| `crew_roles.job:Producer` | 5,665 | exact docValues lookup |
| `crew_roles.job:producer` | 0 | `string` is case-sensitive |
| `crew_roles.job:producers` | 0 | no stemming |
| `cast.order:0` | 6,100 | exact numeric docValues lookup |

These fields are **not full-text searchable**: there is no tokenization, no
stemming, and no relevance contribution. They are also not reachable by an
unfielded query because `_text_` receives no `copyField` content: `q=producer`
returns 0, while `q=crew_roles.job:Producer` returns exact docValues matches. If
the team wants them to be strictly unqueryable, add `"docValues": false` to
`crew_roles.name`, `crew_roles.job`, and `cast.order` in `solr/schema.json` and
rebuild the index. `cast.order` is multi-valued, so it is not used for sorting and
would not lose functionality.

## 7. Verification

Run:

```bash
python3 scripts/verify_index.py
```

Result: **25 passed, 0 failed, 2 warnings** (the warnings are the docValues
behaviour above). The checks cover:

| Check | Result |
|---|---|
| Manifest, collection, and Solr counts agree | 6,104 movies, 12,057 reviews, 18,161 total |
| Sample parent `movie_id:11` | *Star Wars*, correct id and metadata |
| Sample children of `movie_id:11` | 7 review children |
| Parent with no children (`movie_id:2`) | 1 parent, 0 children |
| Analyzer folding/lowercasing/stopwords/KStem | pass |
| Sanity queries | title, cast, plot, nested parent, genre/year, runtime, status, language |
| Display-only fields | `indexed=false`, exact docValues only |

The full verification record, including the exact sanity-query counts, is in
[`docs/index-verification.md`](index-verification.md).

## 8. Coverage and corpus statistics

### 8.1 Field coverage

Coverage is the share of the 6,104 movie documents with a non-null, non-empty value:

| Field | Coverage | Field | Coverage |
|---|---:|---|---:|
| `title` | 100.0% | `vote_average` | 97.7% |
| `original_title` | 100.0% | `vote_count` | 100.0% |
| `release_date` | 100.0% | `popularity` | 100.0% |
| `year` | 100.0% | `budget` | 61.1% |
| `runtime` | 99.0% | `revenue` | 63.3% |
| `original_language` | 100.0% | `director` | 99.9% |
| `status` | 100.0% | `cast` | 99.9% |
| `overview` | 99.8% | `crew_names` | 99.9% |
| `tagline` | 81.4% | `crew_roles` | 99.9% |
| `genres` | 99.7% | `wikipedia` | 100.0% |
| `plot` | 100.0% | `num_reviews` | 100.0% |

`reviews` is always present as a list, but 3,544 movies (58.1%) have at least one
review. This is the main coverage limit for review-based information needs: Q1 and
Q2 can only reach review-bearing movies.

### 8.2 Length and cardinality

| Measure | Value |
|---|---|
| Plot words | min 50 (filter floor), median 596, mean 540.2, max 3,253 |
| Overview length | median 240 characters, mean 269.9 |
| Reviews | 12,057 total; overall mean 1.98; mean 3.4 among movies with reviews; median 2; max 53 |
| Review length | median 1,043 characters, mean 1,393.2 |
| Cast per movie | median 20, max 21 |
| Crew roles per movie | median 7, max 30 |
| Genres per movie | median 3, max 8 |
| Release years | 1911–2026 |

### 8.3 Distribution highlights

- **Top genres:** Drama 2,670; Comedy 1,937; Thriller 1,608; Action 1,587;
  Adventure 1,103; Romance 990; Horror 906; Crime 890.
- **Languages:** `en` 4,891; `fr` 183; `ja` 168; `es` 114; `hi` 112; `it` 98.
- **Status:** Released 6,064; Post Production 36; In Production 4.
- **Wikipedia match method:** `tmdb` for all 6,104 documents (the collection only
  contains movies linked through Wikidata's TMDB property).

The plot field dominates the free text and is the main retrieval signal. The
overview is much shorter but more focused; that is why Setup B boosts it above the
longer plot for plot-based needs.

## 9. Deviations from the M1 schema proposal

`docs/schema.md` is the Milestone 1 proposal and is marked "needs group
confirmation". The M2 index keeps the same data but changes the physical layout.
P4 owns `docs/schema.md`; this table is the proposed delta rather than a silent
rewrite.

| M1 proposal | M2 index | Why |
|---|---|---|
| `reviews` embedded in the movie document | `doc_type=review` child documents joined to the parent | per-review scoring and block joins without duplicating movie fields |
| `crew_roles` display-only, "never indexed as text" | `crew_roles.name` / `crew_roles.job` are `indexed=false`, but docValues allow exact term queries | Solr default docValues; not full-text searchable |
| `cast.order` is a sort key | `cast.order` is multi-valued and `indexed=false`; it is display order, not a sort key | the source keeps the full billed cast; multi-valued fields cannot be sorted |
| review author and text are searchable | only `review_text` is indexed; `review_author` is display-only | review search is about content, not reviewer names |
| `wikipedia` object | flattened `wikipedia.title`, `.url`, `.wikidata_id`, `.imdb_id`, `.match_method` | Solr fields are flat; only the title is searchable |
| text fields such as `title`, `overview`, `plot` typed as strings | `textFoldLower` for text; `string` only for exact fields | retrieval needs analysis; enums need exactness |
| `release_date` string | `pdate` | date ranges and sorting |
| no `doc_type` or review child fields | `doc_type`, `review_text`, `review_author`, `review_rating`, `review_created_at` added | parent/child model |
| `movie_id` integer | `plong` | 64-bit-safe numeric field |
| expected 6,000–7,000 documents | 6,104 documents | actual join and plot filter |
| `overview` 155 empty, 1,067 unrated, 392 runtime zero | 10 empty, 139 unrated, 64 runtime zero | most metadata-poor movies were dropped by the plot requirement |

The source-side JSON Schema in `docs/collection.schema.json` remains valid for
`collection.jsonl`; it describes the collection, not the Solr index. The Solr field
definitions are in `solr/schema.json`.

## 10. Query implications

The index layout directly shapes the Setup A and Setup B queries:

- **Q1/Q2 (reviews).** Search the child `review_text` field and wrap the query in
  `{!parent which="doc_type:movie" score=max}` so the result unit is a movie.
  `score=max` means a movie inherits its best matching review's score.
- **Q3/Q4 (plot).** Search parent fields (`overview`, `plot`) and add
  `fq=doc_type:movie` so review children never appear in the result list.
- **Q5 (cast + plot).** Filter on `cast.name` (or `fq=cast.name:...`) and search
  `overview`/`plot` for the organized-crime wording.
- **Analyzer effects.** Case and accents do not matter; stopwords are removed;
  KStem makes some morphological variants match. `string` filters such as
  `status:Released` and `original_language:en` remain exact and case-sensitive.
- **`crew_roles.job` must not be used as a relevance signal.** It is display-only
  for retrieval purposes, even though exact docValues queries resolve.

## 11. Design decisions and trade-offs

1. **Parent + child documents instead of one flat document per movie.**
   - Pro: no duplication of movie text per review; per-review scoring; can return
     the best review.
   - Con: two document types; movie-level queries need `fq=doc_type:movie` or the
     parent parser.
2. **A dedicated `textFoldLower` analyzer instead of Solr's default.**
   - Pro: accent folding and KStem fit English Wikipedia/TMDB text.
   - Con: KStem is conservative (`running` stays `running`) and is not a full
     lemmatizer.
3. **No populated catch-all field.**
   - Pro: explicit field choice; display-only fields cannot leak into general
     relevance. `_text_` exists but receives no `copyField` content.
   - Con: every query must name its fields; Setup B needs `qf`/`pf`.
4. **`crew_names` searchable, `crew_roles.job` display-only.**
   - Pro: people search by name, not by credit type; avoids "producer" false
     positives.
   - Con: credit-based retrieval is not supported.
5. **`genres` as analyzed multi-valued text.**
   - Pro: "science fiction" and "comedy" work as natural-language terms.
   - Con: genre values are tokenized; exact genre facets would need a separate
     string field if the team wants them later.
6. **`string` for language and status.**
   - Pro: exact, predictable filters.
   - Con: case-sensitive; queries must use the canonical values.
7. **Full plots, no truncation.**
   - Pro: long narrative text is the project's main asset.
   - Con: long fields are length-normalized by BM25, so a single matching term in
     a very long plot contributes less than in a short overview; Setup B's field
     boosts account for this.

## 12. Open items

1. Decide whether to set `docValues=false` on the display-only fields to make them
   strictly unqueryable. This requires a schema change and a reindex.
2. Decide whether `doc_type` should be a `string` rather than `text_general`. The
   current field works; the change is cosmetic.
3. Fold the deviations in Section 9 into `docs/schema.md` (P4 owns that file) or
   mark `docs/schema.md` as the historical M1 proposal.
4. Capture the Admin UI screenshots for the demo:
   core overview, Schema, Analysis (`textFoldLower`), and Query
   (`plot:astronaut` and the nested review query).
