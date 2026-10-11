# Cast & crew aggregation (P4)

## Purpose

`cast.csv` (150,044 rows) and `crew.csv` (63,632 rows) store **one row per person per
movie** (15.5 cast rows per movie on average). The final collection is one document per
movie, so joining them naively would duplicate every movie ~15×. This step collapses
both files to one row per movie, which the final join then attaches by `movie_id`.

## Script

[`scripts/aggregate_cast_crew.py`](../../scripts/aggregate_cast_crew.py). Run with
`python3 scripts/aggregate_cast_crew.py`. Reads `data/raw/cast.csv`,
`data/raw/crew.csv` and `data/interim/movies_clean.csv`; writes
`data/interim/castcrew_agg.csv` (9,710 rows — exactly one per cleaned movie).

| Column | Content |
|---|---|
| `movie_id`, `title` | from `movies_clean.csv` (join keys / human check) |
| `director` | unique names with `job == "Director"`, `; `-joined (683 movies have >1) |
| `cast` | **full cast** in billing order, `; `-joined as `Name (Character)`; bare `Name` when the character field is empty |
| `crew_names` | **unique crew names**, `; `-joined — the searchable field |
| `crew_roles` | **every crew credit** as `Name (Job)`, `; `-joined — the display-only field; a person with several jobs appears once per job |

## Design decisions (for the group to confirm)

1. **Full cast and full crew, not top-N.** An actor at billing position 18 is still
   someone a user half-remembers ("the one with X in it"), so truncating to the top
   billing would lose searchable names. The dataset itself caps cast at **20 rows per
   movie** (median 20, mean 15.5) and crew at **30** (mean 6.5), so the full lists
   stay small enough to keep as one cell — no truncation needed.
2. **No cast/crew size counts.** Earlier drafts stored `num_cast`/`num_crew`; they add
   no retrieval value (the lists themselves already have a length), so they were dropped.
2. **`director` is kept as its own column** on top of `crew`, because "directed by X"
   is by far the most common structured query and shouldn't require substring matching
   inside the crew cell. 48 cleaned movies have no director on record (no `crew` rows
   or no `job == "Director"`), which is left as an empty value rather than guessed
   from other jobs.
3. **Empty output rows are kept.** A movie with no cast/crew rows still appears in the
   file with empty `director`/`cast`/`crew_names`/`crew_roles` (96 movies have no cast,
   37 have no crew), so a left join on this file never drops movies.
4. **Multi-director movies stay multi-valued** (`Robert Rodriguez; Frank Miller` for
   *Sin City*) — in the JSONL collection these become a list, not a `;`-joined string.
5. **Crew splits into searchable names + display-only roles.** `crew_names` is the
   deduplicated list of people (a person with several credits appears once) and is the
   *only* crew field that goes in the searchable index. `crew_roles` keeps the `Name
   (Job)` credits for the detail page and must **never be indexed as text** — job words
   like "Producer" belong to display only, otherwise a query for "a movie about a
   producer" would surface the film with the most producers. In the final JSONL:
   `crew_names: ["Christopher Nolan", "Emma Thomas"]` and
   `crew_roles: [{name, job}]`. `director` survives separately from `crew_names` because
   "directed by X" is the most common structured query and shouldn't rely on substring
   matching inside the names cell. `cast` stays as objects (`cast: [{name, character,
   order}]`) so Solr can index actor names *and* characters ("search me the one with the
   Joker") plus keep billing order for display.

## Numbers

| Metric | Value |
|---|---:|
| Rows written | 9,710 |
| Movies with no cast rows | 96 |
| Movies with no crew rows | 37 |
| Movies with no director | 48 |
| Movies with more than 1 director | 683 |
| `cast.csv` / `crew.csv` movie ids not in `movies_clean.csv` | 48 / 61 |

The last line: `cast.csv` and `crew.csv` reference a few movies that cleaning dropped
(duplicates / missing release date). They are skipped here because the aggregation is
driven by `movies_clean.csv`, keeping the output aligned with the final collection.

## Data-quality notes

- `cast_order` is a clean non-negative integer for every row — safe to sort on.
- 7,222 cast rows have an **empty `character` field** (documentaries, concert films,
  self-appearances); the script formats those as the bare actor name instead of
  `Name ()`.
- `crew.csv` only covers **5 distinct jobs** in 3 departments (Producer, Executive
  Producer, Director, Writer, Screenplay — Production/Writing/Directing) — there is no
  cinematography, editing or music credit in this dataset. `crew_names` keeps the
  people; `crew_roles` records which of these roles each person had for display.
