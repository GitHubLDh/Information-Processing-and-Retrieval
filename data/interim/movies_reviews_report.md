# Movies & reviews cleaning (P1)

## Source data

[The Movie Database (TMDB) Comprehensive Dataset](https://www.kaggle.com/datasets/rishabhkumar2003/the-movie-database-tmdb-comprehensive-dataset)
(Kaggle, rishabhkumar2003), 5 CSVs: `movies.csv`, `cast.csv`, `crew.csv`, `genres.csv`, `reviews.csv`.

- `movies.csv` — one row per movie (9,771 rows). Columns include `id`, `title`, `overview`,
  `release_date`, `runtime`, `vote_average`, `vote_count`, `original_language`, and `genres`
  (already embedded as a comma-separated string, so `genres.csv` is just a reference table
  of genre names/counts — no join needed against it).
- `cast.csv` / `crew.csv` — one row per cast/crew member, linked via `movie_id`. Not yet
  aggregated to one row per movie — flagged as an open task for whoever builds the final join.
- `reviews.csv` — one row per review (13,073 rows after CSV parsing; raw line count looks
  much higher because review text contains embedded newlines inside quoted fields). Columns
  include `movie_id`, `content` (review text), `author_rating`, `movie_rating`.
- **No IMDb ID column exists anywhere** — Wikidata linking had to go through the TMDB id instead.

## Cleaning pipeline

Script: [`scripts/clean_movies.py`](../../scripts/clean_movies.py). Run with
`python3 scripts/clean_movies.py`. Reads `data/raw/movies.csv` and `data/raw/reviews.csv`,
writes `data/interim/movies_clean.csv` and `data/interim/reviews_clean.csv`.

Steps:
1. Rename `movies.csv`'s `id` column to `movie_id`, to match `cast.csv`/`crew.csv`/`reviews.csv`.
2. Drop duplicate movie rows (same `movie_id`).
3. Drop movies with no `release_date` (including rows where the CSV parser returned `None`
   rather than an empty string — a real data quirk found while testing, not just a theoretical case).
4. Drop reviews belonging to a movie that didn't survive step 3.
5. Clean each review's text: strip HTML tags and Markdown formatting (bullets, `**bold**`,
   `_italic_`) found during manual QA — see below.
6. Drop reviews that are empty after cleaning, or under ~20 words.
7. Drop duplicate reviews (same `movie_id` + same cleaned text).

## Manual QA

Read the first 50+ reviews by hand before writing the cleaning rules. Found TMDB reviews
support Markdown/HTML formatting that needed stripping, keeping the underlying text:

| Found | Example | Handling |
|---|---|---|
| Markdown bullets | `* some point` | strip leading `* ` |
| HTML tags | `<em>'Citizen Kane'</em>` | strip tags, keep inner text |
| Markdown bold/italic (nested) | `_**Not the greatest film...**_` | strip `**...**` then `_..._` |

We deliberately strip formatting entirely rather than converting it to something else — for
indexing/retrieval, only the words matter, not how they were styled; keeping markup characters
would pollute tokenization (e.g. `_bold_` wouldn't match a search for `bold`).

## Results

- **Movies: 9,771 → 9,710** (61 dropped — duplicates or missing release date)
- **Reviews: 13,073 → 12,248** (825 dropped — too short, empty after cleanup, duplicates, or
  belonging to a dropped movie)

## Information needs

See [`docs/information_needs.md`](../../docs/information_needs.md) for the full shared list.
Mine, specifically review-text-dependent (not answerable from metadata or plot alone):

1. **Need**: A movie whose reviewers describe the comedy as clever, witty, or intellectually
   sharp, rather than slapstick or lowbrow.
   **Test query**: `clever witty sophisticated intelligent humor`

2. **Need**: A romantic movie where reviewers are divided — some call it predictable or
   clichéd, others find it genuinely heartwarming.
   **Test query**: `predictable cliché heartwarming emotional romance`

Both are preliminary smoke-test queries written from the cleaned reviews only — not yet
verified against a real search system. To be re-tested once the final collection is indexed.

## Open follow-ups (not done by P1)

- `cast.csv` / `crew.csv` still need aggregating to one row per movie (top-N cast, director) —
  needed before the final join, nobody has claimed this yet.
- Reviews-level stats (count/length per movie, rating correlation, frequent words) are blocked
  on the final joined collection existing.
