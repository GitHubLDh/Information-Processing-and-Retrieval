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


def main():
    # TODO: load data/raw/movies.csv and data/raw/reviews.csv,
    # apply the cleaning steps above, write to data/interim/movies_clean.csv
    # and data/interim/reviews_clean.csv
    raise NotImplementedError


if __name__ == "__main__":
    main()
