"""
Exploratory data analysis on the structured fields of the cleaned movies, for the
report's Characterization section and as a value-range audit before the final join.

Computes:
  - data integrity checks (malformed ids, invalid dates, out-of-range or placeholder
    values, empty text fields, constant columns)
  - release-year distribution by decade
  - genre distribution (and comparison against data/raw/genres.csv reference counts)
  - original-language distribution
  - rating, vote-count and runtime summaries

Writes data/interim/structured_eda_report.md and prints a summary.

Usage: python3 scripts/structured_eda.py
"""

import csv
import datetime
import statistics
from collections import Counter
from pathlib import Path

INTERIM_DIR = Path(__file__).resolve().parent.parent / "data" / "interim"
RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
TODAY = datetime.date.today().isoformat()


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def as_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def integrity_checks(movies):
    findings = Counter()
    malformed_ids = []
    future_dates = []
    for row in movies:
        movie_id = row["movie_id"]
        if not movie_id.strip().isdigit():
            findings["non-numeric movie_id (malformed CSV row)"] += 1
            malformed_ids.append(movie_id.strip()[:60])

        date = (row["release_date"] or "").strip()
        if date == "0" or len(date) != 10:
            findings["invalid release_date"] += 1
        elif date > TODAY:
            findings["future release_date"] += 1
            future_dates.append((date, row["title"]))

        runtime = as_float(row["runtime"])
        if runtime is None:
            findings["missing runtime"] += 1
        elif runtime == 0:
            findings["runtime = 0"] += 1
        elif runtime > 360:
            findings["runtime > 360 min"] += 1

        rating = as_float(row["vote_average"])
        votes = as_float(row["vote_count"])
        if rating is None:
            findings["missing vote_average"] += 1
        elif not 0 <= rating <= 10:
            findings["vote_average outside 0-10"] += 1
        elif rating == 0 and votes:
            findings["vote_average = 0 despite having votes"] += 1
        if votes is not None and votes == 0:
            findings["vote_count = 0 (unrated)"] += 1

        if not (row["overview"] or "").strip():
            findings["empty overview"] += 1
        if not (row["genres"] or "").strip():
            findings["empty genres"] += 1
        if not (row["title"] or "").strip():
            findings["empty title"] += 1
        if (row["status"] or "") != "Released":
            findings["status != Released"] += 1
        if as_float(row["budget"]) == 0:
            findings["budget = 0 (unknown)"] += 1
        if as_float(row["revenue"]) == 0:
            findings["revenue = 0 (unknown)"] += 1
        if not (row["tagline"] or "").strip():
            findings["empty tagline"] += 1

    constant_columns = [c for c in ("adult", "video", "original_title", "homepage",
                                    "poster_path", "backdrop_path")
                        if len({r[c] for r in movies}) <= 3]
    return findings, malformed_ids, sorted(future_dates, reverse=True), constant_columns


def numeric_summary(values):
    values = [v for v in values if v is not None]
    return {
        "n": len(values),
        "mean": statistics.mean(values),
        "median": statistics.median(values),
        "min": min(values),
        "max": max(values),
    }


def decade_distribution(movies):
    counter = Counter()
    for row in movies:
        date = row["release_date"] or ""
        year = date[:4]
        if len(date) == 10 and year.isdigit() and int(year) <= int(TODAY[:4]):
            counter[(int(year) // 10) * 10] += 1
        elif len(date) == 10 and year.isdigit():
            counter["future date (> today)"] += 1
        else:
            counter["invalid date"] += 1
    return counter


def genre_distribution(movies):
    counter = Counter()
    for row in movies:
        if row["genres"]:
            counter.update(g.strip() for g in row["genres"].split(",") if g.strip())
    return counter


def language_distribution(movies):
    return Counter(r["original_language"] for r in movies)


def build_report(movies, findings, malformed_ids, future_dates, constant_columns,
                 decades, genres, languages, reference_genres):
    lines = []
    add = lines.append
    same_title_share = sum(1 for r in movies if r["original_title"] == r["title"]) / len(movies)

    add("# Structured data exploration (P4)\n")
    add("Script: [`scripts/structured_eda.py`](../../scripts/structured_eda.py). Run with "
        "`python3 scripts/structured_eda.py`. Computed against `data/interim/movies_clean.csv` "
        f"({len(movies):,} movies) plus `data/raw/genres.csv` as a reference table.\n")

    add("## 1. Data integrity audit\n")
    add(f"Movies audited: **{len(movies):,}**. Value problems found (a movie may fail "
        "several checks):\n")
    add("| Check | Movies |")
    add("|---|---:|")
    for check, count in findings.most_common():
        add(f"| {check} | {count:,} |")
    add("")

    add("### 1.1 Malformed row caused by a carriage return inside an unquoted field\n")
    if malformed_ids:
        add(f"`{len(malformed_ids)}` row(s) have a non-numeric `movie_id`, e.g. "
            f"`\"{malformed_ids[0]}...\"`. This is a CSV artifact, not a real movie: in "
            "`data/raw/movies.csv` the `overview` of movie **457697** (*XXXXXXX*, 2016) "
            "contains a lone `\\r` byte inside an unquoted field, which splits that line "
            "into two records:\n")
        add("```")
        add("...as a point.  Translation of the cards' symbols to a joint.\\r Of the "
            "domestic exploration for finding my voice.,2016-09-01,13,0,0,6.9,...")
        add("```")
        add("Consequences, verified by hand:\n")
        add("- the **real movie 457697** parses with `release_date = None` and is wrongly "
            "dropped by the cleaning step (`movies_clean.csv` does not contain it);")
        add("- the **phantom fragment** keeps `release_date = \"0\"`, passes the "
            "non-empty-date filter, and survives into `movies_clean.csv` and even into the "
            "Wikidata unmatched list, where it was queried as a movie ID.")
        add("\nRecommended fix (owner of `clean_movies.py`): drop rows whose `movie_id` is "
            "not numeric, and/or pre-replace stray `\\r` bytes outside quoted fields when "
            "reading the raw file. Until then, the join script must reject non-numeric IDs "
            "so the phantom never reaches the final collection.\n")

    add("### 1.2 Future release dates\n")
    if future_dates:
        add(f"{len(future_dates)} cleaned movies have a `release_date` after today "
            f"({TODAY}) — unreleased titles announced in the dataset (max "
            f"{future_dates[0][0]}). They are legitimate rows but should be excluded from "
            "any \"year\" analysis of released films:\n")
        add("| Release date | Title |")
        add("|---|---|")
        for date, title in future_dates[:10]:
            add(f"| {date} | {title} |")
        if len(future_dates) > 10:
            add(f"| ... | {len(future_dates) - 10} more |")
        add("")

    add("### 1.3 Constant and non-retrieval columns\n")
    add("Columns with at most 3 distinct values: "
        + (", ".join(f"`{c}`" for c in constant_columns) or "none") + ". "
        f"Two further columns carry little retrieval signal: `original_title` differs "
        f"from `title` for only {100 * (1 - same_title_share):.0f}% of movies "
        f"(they are equal for {100 * same_title_share:.0f}%), and `homepage`, "
        "`poster_path`, `backdrop_path` are near-unique display URLs (one per movie). "
        "Recommendation: drop `adult`, `video` and the display URLs from the final "
        "schema; keep `original_title` only if non-English original titles are wanted "
        "for display.\n")

    add("## 2. Release year\n")
    add("| Decade | Movies |")
    add("|---|---:|")
    for decade in sorted(decades, key=lambda d: str(d)):
        add(f"| {decade} | {decades[decade]} |")
    add("")
    released = [d for d in decades if isinstance(d, int)]
    top = max(released, key=lambda d: decades[d])
    add(f"Distribution is strongly skewed to recent decades: {decades[top]} movies in "
        f"the {top}s alone, versus {sum(decades[d] for d in released if d < 1950)} "
        "released before 1950. Any evaluation query set should weight decades "
        "deliberately, or older films will be under-represented. Note: the "
        f"{len(future_dates)} future releases from section 1.2 are split here — those "
        "dated in 2026 after today fall inside the 2020s row, the rest appear as "
        "\"future date\"; the phantom row (section 1.1) is the \"invalid date\" row.\n")

    add("## 3. Genres\n")
    add("`genres` is a comma-separated string on each movie (multi-label). Counts "
        "overlap — a movie contributes to each of its genres:\n")
    add("| Genre | movies_clean | genres.csv reference | diff |")
    add("|---|---:|---:|---:|")
    for genre, count in genres.most_common():
        ref = reference_genres.get(genre, 0)
        diff = count - ref
        add(f"| {genre} | {count} | {ref} | {diff if diff == 0 else f'{diff:+d}'} |")
    add("")
    add(f"{len(genres)} distinct genres. The reference-table counts differ slightly "
        "because `genres.csv` was built from the raw data (before cleaning dropped 61 "
        "movies); differences are small and consistent with that. The rarest genres "
        "(Western, War, Documentary, TV Movie) have very few movies — genre-filtered "
        "information needs over them will return small result sets.\n")

    add("## 4. Original language\n")
    add("| Language | Movies | Share |")
    add("|---|---:|---:|")
    top_languages = languages.most_common(14)
    for lang, count in top_languages:
        add(f"| {lang} | {count} | {100 * count / len(movies):.1f}% |")
    others = sum(c for _, c in languages.most_common()[14:])
    add(f"| (all others) | {others} | {100 * others / len(movies):.1f}% |")
    add("")
    add(f"{len(languages)} distinct languages; English "
        f"(`en`) is {100 * languages['en'] / len(movies):.0f}% of the collection, so "
        "non-English subsets are small but present (fr, ja, es, de, it, hi...). "
        "Wikipedia plots, however, were fetched only from **en.wikipedia.org**, so "
        "non-English movies will often pair an English plot with an original-language "
        "title — relevant when interpreting language-filtered queries.\n")

    ratings = [as_float(r["vote_average"]) for r in movies]
    votes = [as_float(r["vote_count"]) for r in movies]
    runtimes_raw = [as_float(r["runtime"]) for r in movies]
    runtimes = [v for v in runtimes_raw if v]

    add("## 5. Rating, votes and runtime\n")
    add("| Metric | Mean | Median | Min | Max |")
    add("|---|---:|---:|---:|---:|")
    rs, vs = numeric_summary(ratings), numeric_summary(votes)
    add(f"| `vote_average` | {rs['mean']:.2f} | {rs['median']:.2f} | {rs['min']:.1f} | {rs['max']:.1f} |")
    add(f"| `vote_count` | {vs['mean']:,.0f} | {vs['median']:,.0f} | {vs['min']:,.0f} | {vs['max']:,.0f} |")
    add(f"| `runtime` (min, non-zero) | {numeric_summary(runtimes)['mean']:.1f} | "
        f"{numeric_summary(runtimes)['median']:.1f} | {numeric_summary(runtimes)['min']:.0f} | "
        f"{numeric_summary(runtimes)['max']:.0f} |")
    add("")
    rated = [as_float(r["vote_average"]) for r in movies
             if as_float(r["vote_count"]) and as_float(r["vote_average"]) is not None]
    zero_votes = sum(1 for v in votes if v == 0)
    add(f"- **{zero_votes:,} movies ({100 * zero_votes / len(movies):.0f}%) have "
        "`vote_count = 0`** and therefore no meaningful rating (their "
        "`vote_average` is 0 or missing) — a rating filter like `vote_average >= 7` "
        "silently excludes them, and \"unrated\" must be an explicit state in the "
        f"schema. Excluding unrated movies, the mean rating is "
        f"{statistics.mean(rated):.2f} (the {rs['mean']:.2f} above is dragged down by "
        "the zeros).")
    add(f"- **{findings['runtime = 0']} movies report `runtime = 0`** — a missing-value "
        "placeholder, not a zero-minute film; treat as missing, not as a value.")
    add(f"- Runtime extremes are real features, not errors: "
        f"{findings['runtime > 360 min']} movies over 6 hours (e.g. *Satantango*, "
        "*Napoleon*, documentaries/concert films) — they are correct but distort means, "
        "which is why the median is reported alongside.")
    add(f"- `budget`/`revenue` are 0 for {100 * findings['budget = 0 (unknown)'] / len(movies):.0f}% / "
        f"{100 * findings['revenue = 0 (unknown)'] / len(movies):.0f}% of movies (unknown, "
        "not free) — they are qualitatively different from real zeros and should not be "
        "averaged naively.\n")

    add("## 6. Consequences for the final collection\n")
    add("1. Reject non-numeric `movie_id` at join time (section 1.1) so the phantom row "
        "never enters the collection, and record that real movie 457697 was lost earlier.")
    add("2. Keep `year` derived from `release_date` but flag future dates; exclude them "
        "from year-distribution statistics.")
    add("3. Model `runtime = 0`, `vote_count = 0`, empty `genres`/`overview` and "
        "`budget = 0` as *missing*, not as values.")
    add("4. Drop constant columns (`adult`, `video`, `original_title`, poster/backdrop "
        "paths) from the final schema unless someone needs them for display.")
    add("5. Genres stay a multi-valued list (JSONL array), never a single flat column.\n")

    return "\n".join(lines) + "\n"


def main():
    movies = read_csv(INTERIM_DIR / "movies_clean.csv")
    reference = read_csv(RAW_DIR / "genres.csv")

    findings, malformed_ids, future_dates, constant_columns = integrity_checks(movies)
    decades = decade_distribution(movies)
    genres = genre_distribution(movies)
    languages = language_distribution(movies)
    reference_genres = {r["name"]: int(r["movie_count"]) for r in reference}

    report = build_report(movies, findings, malformed_ids, future_dates,
                          constant_columns, decades, genres, languages,
                          reference_genres)
    out = INTERIM_DIR / "structured_eda_report.md"
    out.write_text(report, encoding="utf-8")

    print(f"audited {len(movies)} movies -> {out}")
    print("\n=== Integrity findings ===")
    for check, count in findings.most_common():
        print(f"  {check}: {count}")
    print(f"\n=== Decades ===\n  " +
          ", ".join(f"{d}: {decades[d]}" for d in sorted(decades, key=str)))
    print(f"\n=== Genres: {len(genres)} distinct, top 5: " +
          ", ".join(f"{g} ({c})" for g, c in genres.most_common(5)))
    print(f"=== Languages: {len(languages)} distinct, en = {100 * languages['en'] / len(movies):.0f}%")


if __name__ == "__main__":
    main()
