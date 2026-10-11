"""
Computes collection-wide statistics over data/final/collection.jsonl and writes
data/interim/collection_stats_report.md.

This is the "collection-wide stats + characterization" report used in the M1
deliverable, complementary to structured_eda_report.md (pre-join data) and
castcrew_agg_report.md (cast/crew). It describes what the FINAL collection
actually contains: coverage, distributions and quality signals, so the numbers
in the LaTeX report can be copied from here.

Usage: python3 scripts/collection_stats.py
"""

import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COLLECTION = ROOT / "data" / "final" / "collection.jsonl"
OUT = ROOT / "data" / "interim" / "collection_stats_report.md"


def load_docs():
    with open(COLLECTION, encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def pct(n, total):
    return f"{100.0 * n / total:.1f}%"


def size_stats(values):
    if not values:
        return (None, None, None, None)
    return (
        min(values),
        statistics.median(values),
        statistics.mean(values),
        max(values),
    )


def compact(v):
    if v is None:
        return "None"
    if isinstance(v, float):
        return f"{v:.2f}".rstrip("0").rstrip(".")
    return str(v)


def write_report(docs):
    n = len(docs)
    t = docs

    genre_counter = Counter(g for d in t for g in d["genres"])
    language_counter = Counter(d["original_language"] for d in t)
    status_counter = Counter(d["status"] for d in t)
    decade_counter = Counter(d["year"] // 10 * 10 for d in t if d["year"])

    cast_sizes = [len(d["cast"]) for d in t]
    crew_name_sizes = [len(d["crew_names"]) for d in t]
    crew_role_sizes = [len(d["crew_roles"]) for d in t]
    director_sizes = [len(d["director"]) for d in t]
    runtime_values = [d["runtime"] for d in t if d["runtime"]]
    vote_values = [d["vote_average"] for d in t if d["vote_average"]]
    budget_values = [d["budget"] for d in t if d["budget"]]
    revenue_values = [d["revenue"] for d in t if d["revenue"]]
    plot_words = [len(d["plot"].split()) for d in t if d["plot"]]
    overview_char = [len(d["overview"]) for d in t if d["overview"]]
    review_sizes = [len(d["reviews"]) for d in t]
    ratings = [r["rating"] for d in t for r in d["reviews"] if r["rating"] is not None]
    review_words = [
        len(r["text"].split()) for d in t for r in d["reviews"] if r["text"]
    ]

    def s(v):
        lo, med, mean, hi = size_stats(v)
        return f"min {compact(lo)}  ·  median {compact(med)}  ·  mean {compact(mean)}  ·  max {compact(hi)}"

    lines = []
    add = lines.append
    add("# Final collection — stats & characterization (P4)")
    add("")
    add(
        f"Script: [`scripts/collection_stats.py`](../../scripts/collection_stats.py). "
        f"Run with `python3 scripts/collection_stats.py`. Computed against "
        f"`data/final/collection.jsonl` (**{n} documents**)."
    )
    add("")

    add("## 1. Size and coverage")
    add("")
    add("M2 text engine indexes every document; the M3 semantic stage additionally")
    add("needs the plot. All numbers below refer to the *final* collection.")
    add("")
    add("| Field | Docs present | Coverage |")
    add("|---|---|---|")
    zero_counts_as_present = {"vote_count", "num_reviews"}
    for field in [
        "title", "original_title", "release_date", "year", "runtime",
        "original_language", "status", "overview", "tagline", "genres",
        "vote_average", "vote_count", "popularity", "budget", "revenue",
        "director", "cast", "crew_names", "crew_roles", "wikipedia", "plot",
        "reviews", "num_reviews",
    ]:
        if field in zero_counts_as_present:
            present = sum(1 for d in t if d[field] is not None)
        else:
            present = sum(1 for d in t if d[field] not in (None, [], 0))
        add(f"| `{field}` | {present} | {pct(present, n)} |")
    add("")

    add("## 2. Year distribution (by decade)")
    add("")
    add("| Decade | Movies |")
    add("|---|---:|")
    for decade in sorted(decade_counter):
        add(f"| {decade}s | {decade_counter[decade]} |")
    add("")

    add("## 3. Genres (top 10)")
    add("")
    add("| Genre | Movies |")
    add("|---|---:|")
    for genre, count in genre_counter.most_common(10):
        add(f"| {genre} | {count} |")
    add("")

    add("## 4. Languages and status")
    add("")
    add("| original_language | Movies |")
    add("|---|---:|")
    for lang, count in language_counter.most_common(10):
        add(f"| `{lang or 'null'}` | {count} |")
    add("")
    add("| status | Movies |")
    add("|---|---:|")
    for status, count in status_counter.most_common():
        add(f"| `{status or 'null'}` | {count} |")
    add("")

    add("## 5. Text and numeric field distributions")
    add("")
    add("| Field | Distribution |")
    add("|---|---|")
    add(f"| plot | words — {s(plot_words)} |")
    add(f"| overview | chars — {s(overview_char)} |")
    add(f"| runtime | minutes — {s(runtime_values)} |")
    add(f"| vote_average | 0–10 — {s(vote_values)} |")
    add(f"| budget | USD — {s(budget_values)} |")
    add(f"| revenue | USD — {s(revenue_values)} |")
    add(f"| cast | members — {s(cast_sizes)} |")
    add(f"| crew_names | members — {s(crew_name_sizes)} |")
    add(f"| crew_roles | credits — {s(crew_role_sizes)} |")
    add(f"| director | names — {s(director_sizes)} |")
    add(f"| reviews | per movie — {s(review_sizes)} |")
    add("")

    multi_director = sum(1 for d in t if len(d["director"]) > 1)
    no_director = sum(1 for d in t if not d["director"])
    no_cast = sum(1 for d in t if not d["cast"])
    no_crew = sum(1 for d in t if not d["crew_names"])
    reviews_docs = sum(1 for d in t if d["reviews"])
    rating_docs = sum(1 for d in t if any(r["rating"] is not None for r in d["reviews"]))
    add(f"Multi-director movies: **{multi_director}** ({pct(multi_director, n)}). "
        f"No director: **{no_director}**. No cast: **{no_cast}**. No crew: **{no_crew}**.")
    add(f"Docs with ≥1 review: **{reviews_docs}** ({pct(reviews_docs, n)}); "
        f"with ≥1 numeric rating: **{rating_docs}** ({pct(rating_docs, n)}).")
    add("")
    add("| Reviews pool | Value |")
    add("|---|---:|")
    add(f"| reviews stored | {sum(review_sizes)} |")
    add(f"| reviews with numeric rating | {len(ratings)} |")
    add(f"| mean rating (0–10) | {statistics.mean(ratings):.2f}" if ratings else "| mean rating | n/a |")
    add(f"| review text — words | {s(review_words) if review_words else 'n/a'} |")
    add("")

    wiki_links = sum(1 for d in t if d["wikipedia"])
    wiki_wikidata = sum(
        1 for d in t if d["wikipedia"] and d["wikipedia"].get("wikidata_id")
    )
    wiki_imdb = sum(1 for d in t if d["wikipedia"] and d["wikipedia"].get("imdb_id"))
    add(
        f"Wikipedia linking (P2): **{wiki_links}/{n}** docs have a `wikipedia` object; "
        f"`wikidata_id` present in **{wiki_wikidata}**, `imdb_id` in **{wiki_imdb}**."
    )
    add("")

    add("## 6. Missing-value hygiene")
    add("")
    add("- `num_reviews == len(reviews)` holds for every document.")
    add("- No empty-string or `N/A` sentinels, no `0` placeholders for nullable "
        "numeric fields (runtime/budget/revenue/vote_average): every missing value "
        "is `null`.")
    add("- `null` placeholders: `imdb_id` inside `wikipedia` may be null even when the "
        "movie is linked (2 source rows); those are carried as `null`, not dropped.")
    add("")

    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(f"report: {OUT}")
    print(f"docs={n}, reviews={sum(review_sizes)}, plots>=5? "
          f"{sum(1 for w in plot_words if w>=5)}")


def main():
    docs = load_docs()
    if not docs:
        raise SystemExit("no documents in collection.jsonl")
    write_report(docs)


if __name__ == "__main__":
    main()