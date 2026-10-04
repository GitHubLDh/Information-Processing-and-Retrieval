"""
Builds a small sample of the raw Kaggle TMDB dataset so teammates can test
their scripts (Wikidata linking, Wikipedia fetching, schema design) without
waiting for the full cleaning pipeline.

Selects the 75 movies with the highest vote_count from movies.csv (popular
movies are far more likely to have a Wikipedia article, which matters for
testing the Wikidata-linking and Wikipedia-fetching steps), then pulls the
matching rows from cast.csv, crew.csv, and reviews.csv by movie_id.

Usage: python3 scripts/make_sample.py
"""

import csv
from pathlib import Path

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
SAMPLE_DIR = Path(__file__).resolve().parent.parent / "data" / "sample"
SAMPLE_SIZE = 75


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(path, rows, fieldnames):
    SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main():
    movies = read_csv(RAW_DIR / "movies.csv")

    def vote_count(row):
        try:
            return int(row["vote_count"])
        except (TypeError, ValueError):
            return 0

    movies.sort(key=vote_count, reverse=True)
    sample_movies = movies[:SAMPLE_SIZE]
    sample_ids = {row["id"] for row in sample_movies}

    cast = [r for r in read_csv(RAW_DIR / "cast.csv") if r["movie_id"] in sample_ids]
    crew = [r for r in read_csv(RAW_DIR / "crew.csv") if r["movie_id"] in sample_ids]
    reviews = [r for r in read_csv(RAW_DIR / "reviews.csv") if r["movie_id"] in sample_ids]

    write_csv(SAMPLE_DIR / "movies_sample.csv", sample_movies, list(sample_movies[0].keys()))
    write_csv(SAMPLE_DIR / "cast_sample.csv", cast, list(cast[0].keys()))
    write_csv(SAMPLE_DIR / "crew_sample.csv", crew, list(crew[0].keys()))
    write_csv(SAMPLE_DIR / "reviews_sample.csv", reviews, list(reviews[0].keys()) if reviews else [])

    reviewed_ids = {r["movie_id"] for r in reviews}
    print(f"Sampled {len(sample_movies)} movies (by highest vote_count)")
    print(f"  cast rows:    {len(cast)}")
    print(f"  crew rows:    {len(crew)}")
    print(f"  review rows:  {len(reviews)}")
    print(f"  movies in sample with >=1 review: {len(reviewed_ids)} / {len(sample_movies)}")
    print(f"Written to {SAMPLE_DIR}")


if __name__ == "__main__":
    main()
