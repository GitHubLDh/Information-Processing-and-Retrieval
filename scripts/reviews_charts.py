"""
Generates the two review-characterization charts for the report (vector PDF output,
per course guidance to use static, programmatically-generated visualizations):

  1. Histogram of review length (word count)
  2. Scatter plot of a movie's average review length vs. its rating

Usage: python3 scripts/reviews_charts.py
"""

import csv
import statistics
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt

INTERIM_DIR = Path(__file__).resolve().parent.parent / "data" / "interim"
FIGURES_DIR = Path(__file__).resolve().parent.parent / "report" / "figures"


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def plot_review_length_histogram(reviews):
    lengths = [len(r["content"].split()) for r in reviews]
    over_cap = sum(1 for l in lengths if l > 1500)

    fig, ax = plt.subplots(figsize=(4.5, 3))
    ax.hist([l for l in lengths if l <= 1500], bins=40, color="#4C72B0", edgecolor="white")
    ax.set_xlabel("Review length (words)")
    ax.set_ylabel("Number of reviews")
    ax.set_title(f"Review length distribution\n({over_cap} reviews over 1500 words not shown)")
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "review_length_hist.pdf")
    plt.close(fig)


def plot_length_vs_rating_scatter(movies, reviews):
    lengths_by_movie = defaultdict(list)
    for r in reviews:
        lengths_by_movie[r["movie_id"]].append(len(r["content"].split()))

    avg_lengths, ratings = [], []
    for m in movies:
        movie_review_lengths = lengths_by_movie.get(m["movie_id"])
        if not movie_review_lengths:
            continue
        try:
            rating = float(m["vote_average"])
        except (TypeError, ValueError):
            continue
        avg_lengths.append(statistics.mean(movie_review_lengths))
        ratings.append(rating)

    slope, intercept = statistics.linear_regression(avg_lengths, ratings)
    x_line = [min(avg_lengths), max(avg_lengths)]
    y_line = [slope * x + intercept for x in x_line]

    fig, ax = plt.subplots(figsize=(4.5, 3))
    ax.scatter(avg_lengths, ratings, s=8, alpha=0.3, color="#4C72B0")
    ax.plot(x_line, y_line, color="#C44E52", linewidth=1.5)
    ax.set_xlabel("Movie's average review length (words)")
    ax.set_ylabel("Movie rating (vote\\_average)")
    ax.set_title(f"Review length vs. rating (n={len(avg_lengths)})")
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "review_length_vs_rating.pdf")
    plt.close(fig)


def main():
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    movies = read_csv(INTERIM_DIR / "movies_clean.csv")
    reviews = read_csv(INTERIM_DIR / "reviews_clean.csv")

    plot_review_length_histogram(reviews)
    plot_length_vs_rating_scatter(movies, reviews)
    print(f"Wrote charts to {FIGURES_DIR}")


if __name__ == "__main__":
    main()
