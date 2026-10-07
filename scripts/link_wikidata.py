"""Link movies to English Wikipedia articles through Wikidata.

Usage:
  python scripts/link_wikidata.py data/sample/movies_sample.csv --prefix sample
  python scripts/link_wikidata.py data/interim/movies_clean.csv

The input must contain TMDB IDs in ``id`` or ``movie_id``. An optional IMDb
column (``imdb_id`` or ``imdb``) is used for a second pass when TMDB lookup
does not find a Wikidata item. Results are checkpointed after every batch, so
rerunning the command skips IDs already recorded in the successful mapping.
"""

import argparse
import csv
import json
import random
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ENDPOINT = "https://query.wikidata.org/sparql"
USER_AGENT = "PRI-movie-linker/1.0 (student research; contact: FEUP PRI project)"
BATCH_SIZE = 125
PAUSE_SECONDS = 1.2


def read_csv(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def write_csv(path, rows, columns):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def sparql_literal(value):
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def build_query(ids, property_id):
    values = " ".join(sparql_literal(value) for value in ids)
    identifier = "?tmdb" if property_id == "P4947" else "?imdb"
    entity_property = "?item wdt:P4947 ?tmdb ." if property_id == "P4947" else "?item wdt:P345 ?imdb ."
    return f"""SELECT ?lookup ?item ?imdb ?article WHERE {{
      VALUES {identifier} {{ {values} }}
      {entity_property}
      BIND({identifier} AS ?lookup)
      OPTIONAL {{ ?item wdt:P345 ?imdb . }}
      OPTIONAL {{ ?article schema:about ?item ; schema:isPartOf <https://en.wikipedia.org/> . }}
    }}"""


def query_wikidata(ids, property_id):
    query = build_query(ids, property_id)
    url = ENDPOINT + "?" + urllib.parse.urlencode({"query": query, "format": "json"})
    request = urllib.request.Request(url, headers={"Accept": "application/sparql-results+json", "User-Agent": USER_AGENT})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                payload = json.load(response)
            return payload["results"]["bindings"]
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            if attempt == 4:
                raise
            delay = (2 ** attempt) + random.random()
            print(f"Request failed ({exc}); retrying in {delay:.1f}s", flush=True)
            time.sleep(delay)


def article_title(url):
    if not url:
        return ""
    return urllib.parse.unquote(url.rsplit("/", 1)[-1].replace("_", " "))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--prefix", default="movies", help="output filename prefix (default: movies)")
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    parser.add_argument("--pause", type=float, default=PAUSE_SECONDS)
    args = parser.parse_args()

    base = Path(__file__).resolve().parent.parent / "data" / "interim"
    success_path = base / f"{args.prefix}_wikipedia_links.csv"
    no_match_path = base / f"{args.prefix}_wikipedia_unmatched.csv"
    checkpoint_path = base / f"{args.prefix}_wikipedia_checkpoint.csv"
    movies = read_csv(args.input)
    id_column = "movie_id" if movies and "movie_id" in movies[0] else "id"
    imdb_column = next((c for c in ("imdb_id", "imdb") if movies and c in movies[0]), None)
    ids = list(dict.fromkeys(row[id_column].strip() for row in movies if row.get(id_column, "").strip()))

    completed = {}
    if checkpoint_path.exists():
        completed = {r["movie_id"]: r for r in read_csv(checkpoint_path)}
    elif success_path.exists():
        completed = {r["movie_id"]: r for r in read_csv(success_path)}
    remaining = [value for value in ids if value not in completed]
    print(f"{len(ids)} unique IDs; {len(completed)} already mapped; querying {len(remaining)}", flush=True)

    for offset in range(0, len(remaining), args.batch_size):
        batch = remaining[offset:offset + args.batch_size]
        result = query_wikidata(batch, "P4947")
        found = {}
        for row in result:
            key = row["lookup"]["value"]
            entity = row["item"]["value"].rsplit("/", 1)[-1]
            imdb = row.get("imdb", {}).get("value", "")
            article = row.get("article", {}).get("value", "")
            found[key] = {"movie_id": key, "wikipedia_title": article_title(article), "wikipedia_url": article,
                          "imdb_id": imdb, "wikidata_id": entity, "match_method": "tmdb"}

        # Resolve remaining IDs by IMDb when present in the source file.
        row_by_id = {r[id_column].strip(): r for r in movies}
        imdb_candidates = {}
        if imdb_column:
            for movie_id in batch:
                source_imdb = row_by_id[movie_id].get(imdb_column, "").strip()
                if movie_id not in found and source_imdb:
                    imdb_candidates.setdefault(source_imdb, []).append(movie_id)
        if imdb_candidates:
            fallback_rows = query_wikidata(list(imdb_candidates), "P345")
            for row in fallback_rows:
                imdb = row["lookup"]["value"]
                entity = row["item"]["value"].rsplit("/", 1)[-1]
                article = row.get("article", {}).get("value", "")
                for movie_id in imdb_candidates[imdb]:
                    found[movie_id] = {"movie_id": movie_id, "wikipedia_title": article_title(article), "wikipedia_url": article,
                                       "imdb_id": imdb, "wikidata_id": entity, "match_method": "imdb"}

        for movie_id, mapping in found.items():
            completed[movie_id] = mapping
        write_csv(checkpoint_path, list(completed.values()), ["movie_id", "wikipedia_title", "wikipedia_url", "imdb_id", "wikidata_id", "match_method"])
        print(f"Processed {min(offset + len(batch), len(remaining))}/{len(remaining)}; total mapped {len(completed)}", flush=True)
        if offset + args.batch_size < len(remaining):
            time.sleep(args.pause)

    linked = [r for r in completed.values() if r["wikipedia_title"]]
    no_article = [r for r in completed.values() if not r["wikipedia_title"]]
    unmapped = [movie_id for movie_id in ids if movie_id not in completed]
    write_csv(success_path, linked, ["movie_id", "wikipedia_title", "wikipedia_url", "imdb_id", "wikidata_id", "match_method"])
    write_csv(no_match_path, [{"movie_id": r["movie_id"], "reason": "wikidata_item_without_english_wikipedia_link", "wikidata_id": r["wikidata_id"]} for r in no_article] +
              [{"movie_id": value, "reason": "no_wikidata_item_by_tmdb_or_imdb", "wikidata_id": ""} for value in unmapped],
              ["movie_id", "reason", "wikidata_id"])
    print(f"Wrote {len(linked)} mappings to {success_path}; {len(no_article) + len(unmapped)} unmatched to {no_match_path}", flush=True)


if __name__ == "__main__":
    main()
