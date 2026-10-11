"""Plot English Wikipedia linking coverage by movie release decade.

Run from any directory with: python scripts/wikidata_coverage_by_decade.py
"""

import csv
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
INTERIM = ROOT / "data" / "interim"
OUTPUT = ROOT / "report" / "figures" / "wikidata_coverage_by_decade.pdf"


def read_csv(path):
    with path.open(newline="", encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))


def main():
    movies = read_csv(INTERIM / "movies_clean.csv")
    linked_ids = {row["movie_id"] for row in read_csv(INTERIM / "movies_wikipedia_links.csv")}
    decade_counts = defaultdict(lambda: [0, 0])
    for movie in movies:
        year = movie.get("release_date", "")[:4]
        if not year.isdigit():
            continue
        decade = f"{(int(year) // 10) * 10}s" if int(year) >= 1950 else "Before 1950"
        decade_counts[decade][1] += 1
        decade_counts[decade][0] += movie["movie_id"] in linked_ids

    labels = sorted(decade_counts, key=lambda value: -1 if value == "Before 1950" else int(value[:-1]))
    rates = [100 * decade_counts[label][0] / decade_counts[label][1] for label in labels]
    fig, ax = plt.subplots(figsize=(4.0, 2.6))
    ax.plot(labels, rates, marker="o", markersize=3, linewidth=1.5, color="#4C72B0")
    ax.set_ylim(0, 100)
    ax.set_ylabel("Movies with English Wikipedia page (%)")
    ax.set_xlabel("Release period")
    ax.set_title("Wikidata linking coverage by release period")
    ax.grid(axis="y", alpha=0.25)
    ax.tick_params(axis="x", rotation=35, labelsize=7)
    for label, rate in zip(labels, rates):
        linked, total = decade_counts[label]
        ax.annotate(f"{rate:.1f}%\n{linked:,}/{total:,}", (label, rate),
                    xytext=(0, 6), textcoords="offset points", ha="center", fontsize=5.5)
    fig.tight_layout()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUTPUT, bbox_inches="tight")
    plt.close(fig)
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    main()
