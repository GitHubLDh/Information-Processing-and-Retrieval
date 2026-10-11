# Final collection — stats & characterization (P4)

Script: [`scripts/collection_stats.py`](../../scripts/collection_stats.py). Run with `python3 scripts/collection_stats.py`. Computed against `data/final/collection.jsonl` (**6104 documents**).

## 1. Size and coverage

M2 text engine indexes every document; the M3 semantic stage additionally
needs the plot. All numbers below refer to the *final* collection.

| Field | Docs present | Coverage |
|---|---|---|
| `title` | 6104 | 100.0% |
| `original_title` | 6104 | 100.0% |
| `release_date` | 6104 | 100.0% |
| `year` | 6104 | 100.0% |
| `runtime` | 6040 | 99.0% |
| `original_language` | 6104 | 100.0% |
| `status` | 6104 | 100.0% |
| `overview` | 6094 | 99.8% |
| `tagline` | 4969 | 81.4% |
| `genres` | 6083 | 99.7% |
| `vote_average` | 5965 | 97.7% |
| `vote_count` | 6104 | 100.0% |
| `popularity` | 6104 | 100.0% |
| `budget` | 3730 | 61.1% |
| `revenue` | 3862 | 63.3% |
| `director` | 6098 | 99.9% |
| `cast` | 6100 | 99.9% |
| `crew_names` | 6100 | 99.9% |
| `crew_roles` | 6100 | 99.9% |
| `wikipedia` | 6104 | 100.0% |
| `plot` | 6104 | 100.0% |
| `reviews` | 3544 | 58.1% |
| `num_reviews` | 6104 | 100.0% |

## 2. Year distribution (by decade)

| Decade | Movies |
|---|---:|
| 1910s | 8 |
| 1920s | 30 |
| 1930s | 76 |
| 1940s | 79 |
| 1950s | 132 |
| 1960s | 132 |
| 1970s | 221 |
| 1980s | 437 |
| 1990s | 699 |
| 2000s | 1175 |
| 2010s | 1770 |
| 2020s | 1345 |

## 3. Genres (top 10)

| Genre | Movies |
|---|---:|
| Drama | 2670 |
| Comedy | 1937 |
| Thriller | 1608 |
| Action | 1587 |
| Adventure | 1103 |
| Romance | 990 |
| Horror | 906 |
| Crime | 890 |
| Science Fiction | 783 |
| Fantasy | 694 |

## 4. Languages and status

| original_language | Movies |
|---|---:|
| `en` | 4891 |
| `fr` | 183 |
| `ja` | 168 |
| `es` | 114 |
| `hi` | 112 |
| `it` | 98 |
| `de` | 77 |
| `ko` | 59 |
| `cn` | 30 |
| `zh` | 29 |

| status | Movies |
|---|---:|
| `Released` | 6064 |
| `Post Production` | 36 |
| `In Production` | 4 |

## 5. Text and numeric field distributions

| Field | Distribution |
|---|---|
| plot | words — min 50  ·  median 596  ·  mean 540.2  ·  max 3253 |
| overview | chars — min 21  ·  median 240  ·  mean 269.92  ·  max 979 |
| runtime | minutes — min 6  ·  median 104  ·  mean 107.18  ·  max 450 |
| vote_average | 0–10 — min 1  ·  median 6.52  ·  mean 6.44  ·  max 10 |
| budget | USD — min 1  ·  median 25000000  ·  mean 45134543.28  ·  max 489900000 |
| revenue | USD — min 5  ·  median 53565695  ·  mean 140706779.4  ·  max 2923706026 |
| cast | members — min 0  ·  median 20  ·  mean 17.81  ·  max 21 |
| crew_names | members — min 0  ·  median 6  ·  mean 6.89  ·  max 30 |
| crew_roles | credits — min 0  ·  median 7  ·  mean 7.87  ·  max 30 |
| director | names — min 0  ·  median 1  ·  mean 1.08  ·  max 11 |
| reviews | per movie — min 0  ·  median 1  ·  mean 1.98  ·  max 53 |

Multi-director movies: **408** (6.7%). No director: **6**. No cast: **4**. No crew: **4**.
Docs with ≥1 review: **3544** (58.1%); with ≥1 numeric rating: **3504** (57.4%).

| Reviews pool | Value |
|---|---:|
| reviews stored | 12057 |
| reviews with numeric rating | 10899 |
| mean rating (0–10) | 6.69
| review text — words | min 20  ·  median 181  ·  mean 239.89  ·  max 4028 |

Wikipedia linking (P2): **6104/6104** docs have a `wikipedia` object; `wikidata_id` present in **6104**, `imdb_id` in **6104**.

## 6. Missing-value hygiene

- `num_reviews == len(reviews)` holds for every document.
- No empty-string or `N/A` sentinels, no `0` placeholders for nullable numeric fields (runtime/budget/revenue/vote_average): every missing value is `null`.
- `null` placeholders: `imdb_id` inside `wikipedia` may be null even when the movie is linked (2 source rows); those are carried as `null`, not dropped.

