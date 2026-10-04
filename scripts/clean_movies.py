"""
Cleans movies.csv and reviews.csv and writes the result to data/interim/.

Expected steps (see project checklist):
  - rename columns to the agreed schema
  - drop duplicate movie rows
  - drop movies with no release_date
  - drop empty reviews
  - drop reviews under ~20 words
  - drop duplicate reviews (same movie_id + same content)
  - strip HTML tags and Markdown formatting from review text
    (bullets, **bold**, _italic_ — see notes from manual QA pass)

Usage: python3 scripts/clean_movies.py
"""

import csv
import re
from pathlib import Path

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
INTERIM_DIR = Path(__file__).resolve().parent.parent / "data" / "interim"


def clean_review_text(text):
    text = re.sub(r"<[^>]+>", "", text)          # strip HTML tags, keep inner text
    text = re.sub(r"(?m)^\s*\*\s+", "", text)     # strip leading "* " bullets
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)  # strip **bold**
    text = re.sub(r"_(.*?)_", r"\1", text)        # strip _italic_
    return text.strip()


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(path, rows, fieldnames):
    INTERIM_DIR.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def clean_movies(movies):
    seen_ids = set()
    cleaned = []
    for row in movies:
        row["movie_id"] = row.pop("id")  # rename to match cast/crew/reviews
        if row["movie_id"] in seen_ids:
            continue
        if not (row["release_date"] or "").strip():
            continue
        seen_ids.add(row["movie_id"])
        cleaned.append(row)
    return cleaned


def clean_reviews(reviews, valid_movie_ids):
    seen = set()
    cleaned = []
    for row in reviews:
        if row["movie_id"] not in valid_movie_ids:
            continue

        text = clean_review_text(row["content"])
        if not text:
            continue
        if len(text.split()) < 20:
            continue

        key = (row["movie_id"], text)
        if key in seen:
            continue
        seen.add(key)

        row["content"] = text
        cleaned.append(row)
    return cleaned


def main():
    movies = read_csv(RAW_DIR / "movies.csv")
    reviews = read_csv(RAW_DIR / "reviews.csv")

    clean_movie_rows = clean_movies(movies)
    valid_movie_ids = {row["movie_id"] for row in clean_movie_rows}
    clean_review_rows = clean_reviews(reviews, valid_movie_ids)

    movie_fieldnames = ["movie_id"] + [k for k in clean_movie_rows[0].keys() if k != "movie_id"]
    write_csv(INTERIM_DIR / "movies_clean.csv", clean_movie_rows, movie_fieldnames)
    write_csv(INTERIM_DIR / "reviews_clean.csv", clean_review_rows, list(reviews[0].keys()))

    print(f"movies:  {len(movies)} -> {len(clean_movie_rows)} after cleaning")
    print(f"reviews: {len(reviews)} -> {len(clean_review_rows)} after cleaning")


if __name__ == "__main__":
    main()
