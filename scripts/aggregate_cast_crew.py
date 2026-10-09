"""
Aggregates the per-person cast.csv / crew.csv rows into one row per movie, so the
final join can attach cast and crew without duplicating movie records.

Reads data/raw/cast.csv, data/raw/crew.csv and data/interim/movies_clean.csv;
writes data/interim/castcrew_agg.csv with one row per cleaned movie:

  movie_id   - as in movies_clean.csv
  director   - "; "-joined unique names with job == "Director"
  cast       - the FULL cast in billing order, "; "-joined "Name (Character)"
               (bare name when the character field is empty)
  crew       - the FULL crew in file order, "; "-joined "Name (Job)"
  num_cast   - total cast rows for the movie
  num_crew   - total crew rows for the movie

The dataset stores at most 20 cast rows per movie, so the full cast list stays a
manageable cell. Movies that exist in movies_clean.csv but have no cast/crew rows
still get an output row (empty director/cast/crew), so a left join on this file
never drops movies.

Usage: python3 scripts/aggregate_cast_crew.py
"""

import csv
from collections import defaultdict
from pathlib import Path

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
INTERIM_DIR = Path(__file__).resolve().parent.parent / "data" / "interim"


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def aggregate(movies, cast, crew):
    cast_by_movie = defaultdict(list)
    for row in cast:
        try:
            order = int(row["cast_order"])
        except (TypeError, ValueError):
            order = 10**6
        cast_by_movie[row["movie_id"]].append((order, row["name"], row["character"]))

    crew_by_movie = defaultdict(list)
    for row in crew:
        crew_by_movie[row["movie_id"]].append(row)

    rows = []
    for movie in movies:
        movie_id = movie["movie_id"]

        cast_members = sorted(cast_by_movie.get(movie_id, []))
        cast_str = "; ".join(
            f"{name} ({character})" if character.strip() else name
            for _, name, character in cast_members
        )

        crew_rows = crew_by_movie.get(movie_id, [])
        directors, seen = [], set()
        for row in crew_rows:
            if row["job"] == "Director" and row["name"] not in seen:
                seen.add(row["name"])
                directors.append(row["name"])
        crew_str = "; ".join(
            f"{row['name']} ({row['job']})" if (row["job"] or "").strip() else row["name"]
            for row in crew_rows
        )

        rows.append({
            "movie_id": movie_id,
            "title": movie["title"],
            "director": "; ".join(directors),
            "cast": cast_str,
            "crew": crew_str,
            "num_cast": len(cast_members),
            "num_crew": len(crew_rows),
        })
    return rows


def main():
    movies = read_csv(INTERIM_DIR / "movies_clean.csv")
    cast = read_csv(RAW_DIR / "cast.csv")
    crew = read_csv(RAW_DIR / "crew.csv")

    rows = aggregate(movies, cast, crew)

    INTERIM_DIR.mkdir(parents=True, exist_ok=True)
    out = INTERIM_DIR / "castcrew_agg.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["movie_id", "title", "director",
                                               "cast", "crew",
                                               "num_cast", "num_crew"])
        writer.writeheader()
        writer.writerows(rows)

    clean_ids = {m["movie_id"] for m in movies}
    print(f"movies in movies_clean.csv: {len(clean_ids):,}")
    print(f"rows written to {out}: {len(rows):,}")
    print(f"clean movies with no cast rows: "
          f"{sum(1 for r in rows if r['num_cast'] == 0)}")
    print(f"clean movies with no crew rows: "
          f"{sum(1 for r in rows if r['num_crew'] == 0)}")
    print(f"clean movies with no director: "
          f"{sum(1 for r in rows if not r['director'])}")
    print(f"clean movies with >1 director: "
          f"{sum(1 for r in rows if ';' in r['director'])}")
    print(f"cast/crew movie ids not present in movies_clean.csv: "
          f"cast={len({r['movie_id'] for r in cast} - clean_ids)}, "
          f"crew={len({r['movie_id'] for r in crew} - clean_ids)}")


if __name__ == "__main__":
    main()
