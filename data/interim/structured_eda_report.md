# Structured data exploration (P4)

Script: [`scripts/structured_eda.py`](../../scripts/structured_eda.py). Run with `python3 scripts/structured_eda.py`. Computed against `data/interim/movies_clean.csv` (9,710 movies) plus `data/raw/genres.csv` as a reference table.

## 1. Data integrity audit

Movies audited: **9,710**. Value problems found (a movie may fail several checks):

| Check | Movies |
|---|---:|
| budget = 0 (unknown) | 5,700 |
| revenue = 0 (unknown) | 5,683 |
| empty tagline | 3,749 |
| vote_count = 0 (unrated) | 1,067 |
| runtime = 0 | 392 |
| empty genres | 263 |
| empty overview | 155 |
| status != Released | 56 |
| future release_date | 14 |
| runtime > 360 min | 6 |
| vote_average = 0 despite having votes | 2 |
| non-numeric movie_id (malformed CSV row) | 1 |
| invalid release_date | 1 |
| missing vote_average | 1 |

### 1.1 Malformed row caused by a carriage return inside an unquoted field

`1` row(s) have a non-numeric `movie_id`, e.g. `"Of the domestic exploration for finding my voice...."`. This is a CSV artifact, not a real movie: in `data/raw/movies.csv` the `overview` of movie **457697** (*XXXXXXX*, 2016) contains a lone `\r` byte inside an unquoted field, which splits that line into two records:

```
...as a point.  Translation of the cards' symbols to a joint.\r Of the domestic exploration for finding my voice.,2016-09-01,13,0,0,6.9,...
```
Consequences, verified by hand:

- the **real movie 457697** parses with `release_date = None` and is wrongly dropped by the cleaning step (`movies_clean.csv` does not contain it);
- the **phantom fragment** keeps `release_date = "0"`, passes the non-empty-date filter, and survives into `movies_clean.csv` and even into the Wikidata unmatched list, where it was queried as a movie ID.

Recommended fix (owner of `clean_movies.py`): drop rows whose `movie_id` is not numeric, and/or pre-replace stray `\r` bytes outside quoted fields when reading the raw file. Until then, the join script must reject non-numeric IDs so the phantom never reaches the final collection.

### 1.2 Future release dates

14 cleaned movies have a `release_date` after today (2026-10-08) — unreleased titles announced in the dataset (max 2028-03-16). They are legitimate rows but should be excluded from any "year" analysis of released films:

| Release date | Title |
|---|---|
| 2028-03-16 | Fast Forever |
| 2027-12-16 | Avengers: Secret Wars |
| 2027-11-24 | Frozen III |
| 2027-11-04 | Margie Claus |
| 2027-06-30 | Shrek 5 |
| 2027-04-07 | Vāranāsi |
| 2027-03-25 | Dragon |
| 2027-03-18 | Sonic the Hedgehog 4 |
| 2027-02-05 | Remain |
| 2026-12-17 | Dune: Part Three |
| ... | 4 more |

### 1.3 Constant and non-retrieval columns

Columns with at most 3 distinct values: `adult`, `video`. Two further columns carry little retrieval signal: `original_title` differs from `title` for only 18% of movies (they are equal for 82%), and `homepage`, `poster_path`, `backdrop_path` are near-unique display URLs (one per movie). Recommendation: drop `adult`, `video` and the display URLs from the final schema; keep `original_title` only if non-English original titles are wanted for display.

## 2. Release year

| Decade | Movies |
|---|---:|
| 1900 | 3 |
| 1910 | 19 |
| 1920 | 69 |
| 1930 | 136 |
| 1940 | 136 |
| 1950 | 205 |
| 1960 | 241 |
| 1970 | 425 |
| 1980 | 674 |
| 1990 | 990 |
| 2000 | 1643 |
| 2010 | 2805 |
| 2020 | 2354 |
| future date (> today) | 9 |
| invalid date | 1 |

Distribution is strongly skewed to recent decades: 2805 movies in the 2010s alone, versus 363 released before 1950. Any evaluation query set should weight decades deliberately, or older films will be under-represented. Note: the 14 future releases from section 1.2 are split here — those dated in 2026 after today fall inside the 2020s row, the rest appear as "future date"; the phantom row (section 1.1) is the "invalid date" row.

## 3. Genres

`genres` is a comma-separated string on each movie (multi-label). Counts overlap — a movie contributes to each of its genres:

| Genre | movies_clean | genres.csv reference | diff |
|---|---:|---:|---:|
| Drama | 4314 | 4334 | -20 |
| Comedy | 2771 | 2777 | -6 |
| Thriller | 2155 | 2172 | -17 |
| Action | 1962 | 1967 | -5 |
| Romance | 1383 | 1384 | -1 |
| Horror | 1326 | 1343 | -17 |
| Adventure | 1265 | 1268 | -3 |
| Crime | 1166 | 1170 | -4 |
| Science Fiction | 1004 | 1010 | -6 |
| Fantasy | 865 | 867 | -2 |
| Family | 777 | 779 | -2 |
| Animation | 676 | 680 | -4 |
| Mystery | 647 | 650 | -3 |
| Music | 354 | 354 | 0 |
| History | 352 | 354 | -2 |
| TV Movie | 344 | 344 | 0 |
| Documentary | 286 | 288 | -2 |
| War | 221 | 221 | 0 |
| Western | 140 | 141 | -1 |

19 distinct genres. The reference-table counts differ slightly because `genres.csv` was built from the raw data (before cleaning dropped 61 movies); differences are small and consistent with that. The rarest genres (Western, War, Documentary, TV Movie) have very few movies — genre-filtered information needs over them will return small result sets.

## 4. Original language

| Language | Movies | Share |
|---|---:|---:|
| en | 6624 | 68.2% |
| fr | 433 | 4.5% |
| ja | 392 | 4.0% |
| es | 313 | 3.2% |
| de | 237 | 2.4% |
| it | 201 | 2.1% |
| hi | 158 | 1.6% |
| tl | 123 | 1.3% |
| ko | 98 | 1.0% |
| sv | 95 | 1.0% |
| nl | 76 | 0.8% |
| pt | 72 | 0.7% |
| tr | 69 | 0.7% |
| pl | 65 | 0.7% |
| (all others) | 754 | 7.8% |

68 distinct languages; English (`en`) is 68% of the collection, so non-English subsets are small but present (fr, ja, es, de, it, hi...). Wikipedia plots, however, were fetched only from **en.wikipedia.org**, so non-English movies will often pair an English plot with an original-language title — relevant when interpreting language-filtered queries.

## 5. Rating, votes and runtime

| Metric | Mean | Median | Min | Max |
|---|---:|---:|---:|---:|
| `vote_average` | 5.49 | 6.17 | 0.0 | 10.0 |
| `vote_count` | 1,570 | 76 | 0 | 38,844 |
| `runtime` (min, non-zero) | 97.8 | 98.0 | 1 | 650 |

- **1,067 movies (11%) have `vote_count = 0`** and therefore no meaningful rating (their `vote_average` is 0 or missing) — a rating filter like `vote_average >= 7` silently excludes them, and "unrated" must be an explicit state in the schema. Excluding unrated movies, the mean rating is 6.17 (the 5.49 above is dragged down by the zeros).
- **392 movies report `runtime = 0`** — a missing-value placeholder, not a zero-minute film; treat as missing, not as a value.
- Runtime extremes are real features, not errors: 6 movies over 6 hours (e.g. *Satantango*, *Napoleon*, documentaries/concert films) — they are correct but distort means, which is why the median is reported alongside.
- `budget`/`revenue` are 0 for 59% / 59% of movies (unknown, not free) — they are qualitatively different from real zeros and should not be averaged naively.

## 6. Consequences for the final collection

1. Reject non-numeric `movie_id` at join time (section 1.1) so the phantom row never enters the collection, and record that real movie 457697 was lost earlier.
2. Keep `year` derived from `release_date` but flag future dates; exclude them from year-distribution statistics.
3. Model `runtime = 0`, `vote_count = 0`, empty `genres`/`overview` and `budget = 0` as *missing*, not as values.
4. Drop constant columns (`adult`, `video`, `original_title`, poster/backdrop paths) from the final schema unless someone needs them for display.
5. Genres stay a multi-valued list (JSONL array), never a single flat column.

