"""
Builds the final collection data/final/collection.jsonl from the interim files.

One JSON object (document) per movie, one line per document. Every document is
validated against docs/collection.schema.json before it is written; the run also
emits data/final/collection_manifest.json so a clean-checkout rerun can compare.

Inputs (all in data/interim/, absent files are treated as empty):

  movies_clean.csv (P1)              -> identity + structured metadata fields
  reviews_clean.csv (P1)             -> reviews array (grouped per movie)
  castcrew_agg.csv (P4)              -> director, cast, crew_names, crew_roles
  movies_wikipedia_links.csv (P2)    -> wikipedia object
  wikipedia_plot.csv (P3)            -> plot (footnote markers stripped)

Conventions applied (see docs/schema.md):

  - Non-numeric movie_id rows are rejected (the CSV phantom-row bug).
  - null (never "", 0 or "N/A") marks missing: runtime/budget/revenue 0 -> null,
    vote_average 0 when vote_count 0 -> null, empty text -> null, empty imdb_id
    -> null.
  - release_date is validated; year is derived (kept even for future dates).
  - genres/cast/crew string cells are split into native JSON lists/objects.
  - Plot footnote markers ([a], [1], ...) are stripped; plot is required and must
    have >= 50 words after stripping.

Usage: python3 scripts/build_collection.py
"""

import csv
import datetime
import json
import re
import subprocess

from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parent.parent
INTERIM = ROOT / "data" / "interim"
FINAL = ROOT / "data" / "final"
SCHEMA_PATH = ROOT / "docs" / "collection.schema.json"

RELEASE_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
FOOTNOTE_RE = re.compile(r"\[(?:\d+|[a-z])\]")
DATE_FROM_ISO = re.compile(r"^(\d{4}-\d{2}-\d{2})")

MIN_PLOT_WORDS = 50


def load_rows(filename):
    path = INTERIM / filename
    if not path.exists():
        print(f"  WARNING: {filename} missing — treated as empty")
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def to_int(value, zero_to_null=False):
    value = value.strip()
    if not value:
        return None
    try:
        num = int(float(value))
    except ValueError:
        return None
    if zero_to_null and num == 0:
        return None
    return num


def to_float(value, zero_to_null=False):
    value = value.strip()
    if not value:
        return None
    try:
        num = float(value)
    except ValueError:
        return None
    if zero_to_null and num == 0:
        return None
    return num


def non_empty(value):
    value = value.strip()
    return value or None


def split_list(value):
    return [part.strip() for part in value.split(";") if part.strip()]


def split_genres(value):
    return [part.strip() for part in value.split(",") if part.strip()]


def parse_cast(value):
    out = []
    for entry in value.split(";"):
        entry = entry.strip()
        if not entry:
            continue
        if "(" in entry:
            name, _, character = entry.partition("(")
            character = character[:-1] if character.endswith(")") else character
            character = character.strip() or None
        else:
            name, character = entry, None
        out.append({"name": name.strip(), "character": character, "order": len(out)})
    return out


def parse_crew_roles(value):
    out = []
    for entry in value.split(";"):
        entry = entry.strip()
        if not entry:
            continue
        if "(" in entry:
            name, _, job = entry.partition("(")
            job = job.rstrip(")").strip()
        else:
            name, job = entry, None
        out.append({"name": name.strip(), "job": job})
    return out


def strip_footnotes(plot):
    return FOOTNOTE_RE.sub("", plot).strip()


def word_count(text):
    return len(re.findall(r"\S+", text))


def git_commit():
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=ROOT
        )
        return result.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def build_document(movie, castcrew, link_row, plot_row, reviews):
    release_date = RELEASE_DATE_RE.match(movie["release_date"].strip())
    year = int(release_date.group(0)[:4]) if release_date else None
    if year is not None and not 1800 <= year <= 2100:
        year = None

    vote_count = to_int(movie["vote_count"]) or 0
    vote_average = movie["vote_average"].strip()
    vote_average = (
        to_float(vote_average) if vote_average and vote_count else None
    )

    imdb_id = non_empty(link_row["imdb_id"]) if link_row else None
    wikipedia = None
    if link_row and non_empty(link_row["wikipedia_title"]) and non_empty(link_row["wikipedia_url"]):
        wikipedia = {
            "title": link_row["wikipedia_title"].strip(),
            "url": link_row["wikipedia_url"].strip(),
            "wikidata_id": non_empty(link_row["wikidata_id"]),
            "imdb_id": imdb_id,
            "match_method": non_empty(link_row["match_method"]),
        }

    plot = None
    if plot_row and plot_row.get("status", "").strip() == "ok":
        plot = strip_footnotes(plot_row["plot"] or "")
        plot = plot or None

    return {
        "movie_id": int(movie["movie_id"]),
        "title": movie["title"].strip(),
        "original_title": non_empty(movie["original_title"]),
        "release_date": movie["release_date"].strip() if release_date else None,
        "year": year,
        "runtime": to_int(movie["runtime"], zero_to_null=True),
        "original_language": non_empty(movie["original_language"]),
        "status": non_empty(movie["status"]),
        "overview": non_empty(movie["overview"]),
        "tagline": non_empty(movie["tagline"]),
        "genres": split_genres(movie["genres"]),
        "vote_average": vote_average,
        "vote_count": vote_count,
        "popularity": to_float(movie["popularity"]),
        "budget": to_int(movie["budget"], zero_to_null=True),
        "revenue": to_int(movie["revenue"], zero_to_null=True),
        "director": split_list(castcrew.get("director", "")),
        "cast": parse_cast(castcrew.get("cast", "")),
        "crew_names": split_list(castcrew.get("crew_names", "")),
        "crew_roles": parse_crew_roles(castcrew.get("crew_roles", "")),
        "wikipedia": wikipedia,
        "plot": plot,
        "reviews": reviews,
        "num_reviews": len(reviews),
    }


def summarize_movie(doc):
    return {
        "movie_id": doc["movie_id"],
        "title": doc["title"],
        "genres": doc["genres"],
        "director": doc["director"],
        "cast": doc["cast"],
        "crew_names": doc["crew_names"],
        "crew_roles": doc["crew_roles"],
        "reviews": doc["reviews"],
        "num_reviews": doc["num_reviews"],
    }


def main():
    rows = {
        "movies_clean.csv": load_rows("movies_clean.csv"),
        "reviews_clean.csv": load_rows("reviews_clean.csv"),
        "castcrew_agg.csv": load_rows("castcrew_agg.csv"),
        "movies_wikipedia_links.csv": load_rows("movies_wikipedia_links.csv"),
        "wikipedia_plot.csv": load_rows("wikipedia_plot.csv"),
    }

    movies = {r["movie_id"]: r for r in rows["movies_clean.csv"]}
    numeric = {mid for mid in movies if mid.strip().isdigit()}
    rejected_ids = [mid for mid in movies if not mid.strip().isdigit()]

    castcrew = {r["movie_id"]: r for r in rows["castcrew_agg.csv"]}
    castcrew = {mid: r for mid, r in castcrew.items() if mid in numeric}

    links = {r["movie_id"]: r for r in rows["movies_wikipedia_links.csv"]}
    links = {mid: r for mid, r in links.items() if mid in numeric}

    plots = {r["movie_id"]: r for r in rows["wikipedia_plot.csv"]}
    plots = {mid: r for mid, r in plots.items() if mid in numeric}

    reviews_by_movie = {}
    for rev in rows["reviews_clean.csv"]:
        mid = rev["movie_id"]
        if mid not in numeric:
            continue
        reviews_by_movie.setdefault(mid, []).append({
            "author": non_empty(rev["author"]),
            "rating": to_float(rev["author_rating"])
            if rev["author_rating"].strip() else None,
            "text": (rev.get("content") or "").replace("\r\n", "\n").strip(),
            "created_at": (
                m.group(1) if (m := DATE_FROM_ISO.match(rev["created_at"].strip()))
                else (non_empty(rev["created_at"]) or None)
            ),
        })

    with open(SCHEMA_PATH, encoding="utf-8") as f:
        schema = json.load(f)
    validator = jsonschema.Draft7Validator(schema)

    docs, dropped_no_plot, dropped_short_plot = [], 0, 0
    for mid in sorted(numeric, key=lambda m: int(m)):
        plot_row = plots.get(mid)
        if not (plot_row and plot_row.get("status", "").strip() == "ok"
                and strip_footnotes(plot_row["plot"] or "")):
            dropped_no_plot += 1
            continue
        plot_text = strip_footnotes(plot_row["plot"])
        if word_count(plot_text) < MIN_PLOT_WORDS:
            dropped_short_plot += 1
            continue

        movie = movies[mid]
        doc = build_document(
            movie,
            castcrew.get(mid, {}),
            links.get(mid),
            plot_row,
            reviews_by_movie.get(mid, []),
        )

        errors = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
        if errors:
            print("COLLECTION BUILD FAILED — invalid document:")
            print(json.dumps(summarize_movie(doc), indent=2))
            for err in errors:
                print(f"  {'/'.join(str(p) for p in err.path)}: {err.message}")
            raise SystemExit(1)
        docs.append(doc)

    FINAL.mkdir(parents=True, exist_ok=True)
    collection_path = FINAL / "collection.jsonl"
    with open(collection_path, "w", encoding="utf-8") as f:
        for doc in docs:
            f.write(json.dumps(doc, ensure_ascii=False) + "\n")

    manifest = {
        "build_script": "scripts/build_collection.py",
        "build_date": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "git_commit": git_commit(),
        "schema_file": str(SCHEMA_PATH.relative_to(ROOT)),
        "filters": {
            "reject_non_numeric_movie_id": True,
            "require_plot": True,
            "strip_footnote_markers": True,
            "min_plot_words": MIN_PLOT_WORDS,
        },
        "sources": {
            name: {"rows": len(rows[name])} for name in rows
        },
        "output": {
            "path": str(collection_path.relative_to(ROOT)),
            "documents": len(docs),
            "dropped_no_plot": dropped_no_plot,
            "dropped_below_50_words": dropped_short_plot,
        },
    }
    manifest_path = FINAL / "collection_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"movies (numeric ids): {len(numeric):,}")
    print(f"rejected non-numeric ids: {len(rejected_ids):,} (e.g. {rejected_ids[:1]})")
    print(f"documents written: {len(docs):,}")
    print(f"dropped: no plot={dropped_no_plot:,}, <{MIN_PLOT_WORDS} words={dropped_short_plot:,}")
    print(f"reviews used: {sum(len(d['reviews']) for d in docs):,}")
    print(f"manifest: {manifest_path}")


if __name__ == "__main__":
    main()