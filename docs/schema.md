# Final collection schema (proposal — needs group confirmation)

One **JSON Lines** file, `data/final/collection.jsonl`: one JSON object per movie, one
line per object. This is the single artifact P1–P4 and Milestone 2 (Solr) all build on.
Everything below is a proposal for the group to confirm or amend; nothing else should
be encoded against until it is confirmed.

Owner: **P4** (integration). Feeds: Milestone 2 indexing, Milestone 3 semantic search.

## Why JSONL (not CSV)

The collection mixes scalars (year, runtime), multi-valued fields (genres, cast, crew),
and long text (plot, reviews, reception). A CSV would force cast/crew/reviews/genres
into `;`-joined strings, which breaks per-field querying and tokenization. JSONL keeps
lists as lists and nested objects as objects, and Solr ingests it directly.

## Lineage

| Source file (produced by) | Becomes |
|---|---|
| `data/interim/movies_clean.csv` (P1) | identity + structured metadata fields |
| `data/interim/reviews_clean.csv` (P1) | `reviews` array |
| `data/interim/castcrew_agg.csv` (P4) | `director`, `cast`, `crew` |
| `data/interim/movies_wikipedia_links.csv` (P2) | `wikipedia` object |
| `data/interim/*` wiki parse output (P3) | `plot`, `reception`, `production` |

## Document structure

Fields are **nullable**. `null` (not `""`, not `0`, not `"N/A"`) is the one and only
marker for *missing* — see "Missing-value rules" below.

```json
{
  "movie_id": 155,
  "title": "The Dark Knight",
  "original_title": "The Dark Knight",
  "release_date": "2008-07-16",
  "year": 2008,
  "runtime": 152,
  "original_language": "en",
  "status": "Released",
  "overview": "Batman raises the stakes in his war on crime...",
  "tagline": "Why so serious?",
  "genres": ["Drama", "Action", "Crime", "Thriller"],
  "vote_average": 8.5,
  "vote_count": 38844,
  "popularity": 123.45,
  "budget": 185000000,
  "revenue": 1004558444,

  "director": ["Christopher Nolan"],
  "cast": [
    {"name": "Christian Bale", "character": "Bruce Wayne", "order": 0},
    {"name": "Heath Ledger", "character": "Joker", "order": 1}
  ],
  "crew": [
    {"name": "Christopher Nolan", "job": "Director"},
    {"name": "Emma Thomas", "job": "Producer"}
  ],

  "wikipedia": {
    "title": "The Dark Knight",
    "url": "https://en.wikipedia.org/wiki/The_Dark_Knight",
    "wikidata_id": "Q191568",
    "imdb_id": "tt0468569",
    "match_method": "tmdb"
  },
  "plot": "In Gotham City, the Joker...",
  "reception": "The Dark Knight received critical acclaim...",
  "production": null,

  "reviews": [
    {"author": "Cat Ellington", "rating": null, "text": "As I'm writing this review...", "created_at": "2020-01-02"}
  ],
  "num_reviews": 1,
  "avg_review_words": 512.0
}
```

## Field reference

| Field | Type | Null? | Source / notes |
|---|---|---|---|
| `movie_id` | integer | no | primary key (TMDB); **non-numeric ids are rejected** (see phantom-row bug) |
| `title` | string | no | display / human QA |
| `original_title` | string | yes | keep only if we want non-English titles for display |
| `release_date` | string `YYYY-MM-DD` | yes | from `movies_clean.csv` |
| `year` | integer | yes | derived from `release_date`; null for future/invalid dates |
| `runtime` | integer (minutes) | yes | `0` → `null` (392 movies) |
| `original_language` | string (ISO 639-1) | yes | e.g. `en` |
| `status` | string | yes | `Released`, `Post Production`, ... (56 non-Released) |
| `overview` | string | yes | TMDB short plot (155 empty) |
| `tagline` | string | yes | 3,749 empty |
| `genres` | array[string] | no (may be `[]`) | 263 movies have none |
| `vote_average` | number 0–10 | yes | null when `vote_count = 0` (1,067 unrated) |
| `vote_count` | integer | no | 0 allowed |
| `popularity` | number | yes | |
| `budget` | integer | yes | `0` → `null` (unknown, not free) |
| `revenue` | integer | yes | `0` → `null` |
| `director` | array[string] | no (may be `[]`) | from crew, `job == Director`; multi-valued |
| `cast` | array[object] | no | full cast, billing order; `{name, character}` (`character` nullable) |
| `crew` | array[object] | no | full crew; `{name, job}` |
| `wikipedia` | object | yes | null if the movie has no Wikipedia article |
| `wikipedia.title/url/wikidata_id/imdb_id/match_method` | string | yes | `imdb_id` may be null even when linked |
| `plot` | string | yes | extracted Plot section (P3); **stored in full — no maximum length** |
| `reception` | string | yes | Reception/Critical response section |
| `production` | string | yes | Production/Development section |
| `reviews` | array[object] | no (may be `[]`) | `{author, rating, text, created_at}` |
| `num_reviews` | integer | no | 0 for 62% of movies |
| `avg_review_words` | number | yes | null when `num_reviews = 0` |

## Missing-value rules (important for stats and Solr)

1. `null` means **missing/unknown**. It is never `0`, `""`, `"N/A"` or `"Unknown"`.
2. `0`/`[]`/`""` mean **genuinely zero/empty** and are kept as such (`vote_count: 0`,
   `genres: []`, `reviews: []`).
3. Placeholders found in the source are converted to `null`: `runtime = 0`,
   `budget = 0`, `revenue = 0`, empty `tagline`/`overview` (empty string → `null`),
   `vote_average = 0` when `vote_count = 0`.
4. `release_date` in the future: **kept as a real date**, but `year` is still derived;
   they are excluded from year-distribution statistics, not from the collection.

## Filters applied when building the collection (proposed)

| Filter | Proposal | Rationale |
|---|---|---|
| Non-numeric `movie_id` | **reject** | drops the CSV phantom row; join key must be the TMDB id |
| Wikipedia plot | **require non-empty** | the project is plot/reception search; a movie with no plot can't serve it |
| Plot maximum length | **none — always store the full text** | long plots are valuable; never truncate |
| Plot minimum length | **≥ 50 words (proposal)** | drops stub/disambiguation extracts P3 logged as `no_plot`/short; independent of size |
| `num_reviews` | **no minimum** | 62% of movies have 0 reviews; requiring reviews would gut the collection. Reviews stay an optional field |
| Future release dates | **keep** | they are announced films; excluded from year stats only |
| Non-English original language | **keep** | plots are from en.wikipedia, but the movies are searchable |
| Runtime / budget / revenue | **keep** | null, not filtered on |

Resulting expected size: ~7,000 linked → minus short/missing plots ≈ 6,000–7,000
documents (exact number comes from the join run).

## Open decisions for the group

1. **Confirm JSONL** + the field names above (vs. flat CSV).
2. **Confirm requiring a Wikipedia plot** (recommended) vs. keeping metadata-only movies.
3. **Confirm the minimum plot length** (proposed 50 words). There is never a maximum —
   plots are always stored whole.
4. **Confirm no minimum review count** (proposed), or set one for review-heavy analysis.
5. **Keep `original_title`, `overview`, `popularity`, `budget`, `revenue`?** Suggested:
   keep all (cheap; `popularity`/`budget`/`revenue` enable extra structured filters).
6. **`reception`/`production` fields** — P3 currently extracts only `plot`; these stay
   `null` until P3 adds them. Schema reserves them now so P3's output shape is settled.
7. **P3 parser must strip footnote markers** (`[b]`, `[c]`, `[1]`) and reference brackets
   — currently present in parsed plot text (seen in the sample), and they pollute tokens.

## Reproducibility

The build step (`scripts/build_collection.py`, P4) will also emit
`data/final/collection_manifest.json`: row count, filters applied, per-source row
counts, script name, and the current git commit — so a clean-checkout rerun can be
compared against a recorded run.

## Machine-readable version

`docs/collection.schema.json` (JSON Schema) mirrors this document for automated
validation by the join script and by anyone consuming the file.
