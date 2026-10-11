# Final collection — stats & characterization (P4)

Script: [`scripts/collection_stats.py`](../../scripts/collection_stats.py). Run with `python3 scripts/collection_stats.py`. Computed against `data/final/collection.jsonl` (**74 documents**).

## 1. Size and coverage

M2 text engine indexes every document; the M3 semantic stage additionally
needs the plot. All numbers below refer to the *final* collection.

| Field | Docs present | Coverage |
|---|---|---|
| `title` | 74 | 100.0% |
| `original_title` | 74 | 100.0% |
| `release_date` | 74 | 100.0% |
| `year` | 74 | 100.0% |
| `runtime` | 74 | 100.0% |
| `original_language` | 74 | 100.0% |
| `status` | 74 | 100.0% |
| `overview` | 74 | 100.0% |
| `tagline` | 74 | 100.0% |
| `genres` | 74 | 100.0% |
| `vote_average` | 74 | 100.0% |
| `vote_count` | 74 | 100.0% |
| `popularity` | 74 | 100.0% |
| `budget` | 74 | 100.0% |
| `revenue` | 74 | 100.0% |
| `director` | 74 | 100.0% |
| `cast` | 74 | 100.0% |
| `crew_names` | 74 | 100.0% |
| `crew_roles` | 74 | 100.0% |
| `wikipedia` | 74 | 100.0% |
| `plot` | 74 | 100.0% |
| `reviews` | 74 | 100.0% |
| `num_reviews` | 74 | 100.0% |

## 2. Year distribution (by decade)

| Decade | Movies |
|---|---:|
| 1970s | 2 |
| 1980s | 1 |
| 1990s | 9 |
| 2000s | 20 |
| 2010s | 42 |

## 3. Genres (top 10)

| Genre | Movies |
|---|---:|
| Adventure | 49 |
| Action | 40 |
| Science Fiction | 30 |
| Drama | 21 |
| Fantasy | 18 |
| Thriller | 14 |
| Comedy | 11 |
| Crime | 9 |
| Animation | 6 |
| Family | 6 |

## 4. Languages and status

| original_language | Movies |
|---|---:|
| `en` | 73 |
| `ko` | 1 |

| status | Movies |
|---|---:|
| `Released` | 74 |

## 5. Text and numeric field distributions

| Field | Distribution |
|---|---|
| plot | words — min 496  ·  median 664.5  ·  mean 659.92  ·  max 920 |
| overview | chars — min 101  ·  median 292  ·  mean 298.78  ·  max 728 |
| runtime | minutes — min 81  ·  median 137.5  ·  mean 137.86  ·  max 201 |
| vote_average | 0–10 — min 5.92  ·  median 7.85  ·  mean 7.81  ·  max 8.71 |
| budget | USD — min 6000000  ·  median 140000000  ·  mean 134626527.03  ·  max 356000000 |
| revenue | USD — min 28341469  ·  median 774087303.5  ·  mean 831726047.3  ·  max 2923706026 |
| cast | members — min 20  ·  median 20  ·  mean 20  ·  max 20 |
| crew_names | members — min 2  ·  median 8  ·  mean 8.05  ·  max 19 |
| crew_roles | credits — min 4  ·  median 9  ·  mean 9.11  ·  max 19 |
| director | names — min 1  ·  median 1  ·  mean 1.07  ·  max 2 |
| reviews | per movie — min 1  ·  median 8  ·  mean 11  ·  max 53 |

Multi-director movies: **5** (6.8%). No director: **0**. No cast: **0**. No crew: **0**.
Docs with ≥1 review: **74** (100.0%); with ≥1 numeric rating: **74** (100.0%).

| Reviews pool | Value |
|---|---:|
| reviews stored | 814 |
| reviews with numeric rating | 533 |
| mean rating (0–10) | 7.79
| review text — words | min 20  ·  median 110  ·  mean 203.06  ·  max 2356 |

Wikipedia linking (P2): **74/74** docs have a `wikipedia` object; `wikidata_id` present in **74**, `imdb_id` in **74**.

## 6. Missing-value hygiene

- `num_reviews == len(reviews)` holds for every document.
- No empty-string or `N/A` sentinels, no `0` placeholders for nullable numeric fields (runtime/budget/revenue/vote_average): every missing value is `null`.
- `null` placeholders: `imdb_id` inside `wikipedia` may be null even when the movie is linked (2 source rows); those are carried as `null`, not dropped.

