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
| `crew` | **full crew** in file order, `; `-joined as `Name (Job)` |
| `num_cast` | total cast rows for the movie |
| `num_crew` | total crew rows for the movie |

## Design decisions (for the group to confirm)

1. **Full cast and full crew, not top-N.** An actor at billing position 18 is still
   someone a user half-remembers ("the one with X in it"), so truncating to the top
   billing would lose searchable names. The dataset itself caps cast at **20 rows per
   movie** (median 20, mean 15.5) and crew at **30** (mean 6.5), so the full lists
   stay small enough to keep as one cell — no truncation needed.
2. **`director` is kept as its own column** on top of `crew`, because "directed by X"
   is by far the most common structured query and shouldn't require substring matching
   inside the crew cell. 48 cleaned movies have no director on record (no `crew` rows
   or no `job == "Director"`), which is left as an empty value rather than guessed
   from other jobs.
3. **Empty output rows are kept.** A movie with no cast/crew rows still appears in the
   file with empty `director`/`cast`/`crew` (96 movies have no cast, 37 have no crew),
   so a left join on this file never drops movies.
4. **Multi-director movies stay multi-valued** (`Robert Rodriguez; Frank Miller` for
   *Sin City*) — in the JSONL collection these become a list, not a `;`-joined string.
5. **Format is `; `-joined text because the intermediate is CSV**; the final JSONL
   collection splits each of these back into arrays of objects
   (`cast: [{name, character, order}]`, `crew: [{name, job}]`) so Solr can index
   `cast.name` and `crew.job` as separate fields.

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
  cinematography, editing or music credit in this dataset, so `crew` in the final
  schema means *production/writing/directing crew only*.
