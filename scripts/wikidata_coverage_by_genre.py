"""Plot the two highest and lowest coverage genres with at least 100 films.

Run from any directory with: python scripts/wikidata_coverage_by_genre.py
"""

import csv
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
INTERIM = ROOT / "data" / "interim"
OUTPUT = ROOT / "report" / "figures" / "wikidata_coverage_by_genre.pdf"


def read_csv(path):
    with path.open(newline="", encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))


def main():
    movies = read_csv(INTERIM / "movies_clean.csv")
    linked_ids = {row["movie_id"] for row in read_csv(INTERIM / "movies_wikipedia_links.csv")}
    counts = defaultdict(lambda: [0, 0])
    for movie in movies:
        for genre in filter(None, (part.strip() for part in movie.get("genres", "").split(","))):
            counts[genre][1] += 1
            counts[genre][0] += movie["movie_id"] in linked_ids

    eligible = {genre: values for genre, values in counts.items() if values[1] >= 100}
    ordered = sorted(eligible, key=lambda genre: eligible[genre][0] / eligible[genre][1])
    genres = ordered[:2] + ordered[-2:]
    rates = [100 * eligible[genre][0] / eligible[genre][1] for genre in genres]
    fig, ax = plt.subplots(figsize=(4.0, 2.4))
    bars = ax.barh(genres, rates, color=["#C44E52" if rate < 60 else "#4C72B0" for rate in rates])
    ax.set_xlim(0, 108)
    ax.set_xlabel("Movies with English Wikipedia page (%)")
    ax.set_title("Wikidata linking coverage by selected genres")
    ax.grid(axis="x", alpha=0.25)
    for bar, genre in zip(bars, genres):
        linked, total = eligible[genre]
        ax.text(bar.get_width() + 1, bar.get_y() + bar.get_height() / 2,
                f"{bar.get_width():.1f}% ({linked:,}/{total:,})", va="center", fontsize=7)
    fig.tight_layout()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUTPUT, bbox_inches="tight")
    plt.close(fig)
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    main()
