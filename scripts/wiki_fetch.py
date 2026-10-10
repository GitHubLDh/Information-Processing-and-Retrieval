""""
fetches wikipedia articles by title for each movie in "movies_wikipedia_links.csv", saves raw json 
responses to data/interim/fetch/ (skips already-fetched movies, retries on failure, 5s pause between requests)
"""

import requests
import json
import time
from pathlib import Path
import pandas as pd
import urllib.parse


BASE_DIR = Path(__file__).resolve().parent.parent
USER_AGENT = "PRI-movie-fetcher/1.0 (student research; FEUP PRI project)"

WIKI_FETCH_DIR = BASE_DIR / "data" / "interim" / "fetch"
WIKI_FETCH_DIR.mkdir(parents=True, exist_ok=True)

LINKS_PATH = BASE_DIR / "data" / "interim" / "movies_wikipedia_links.csv"


def article_title_from_url(url):
    if pd.isna(url) or not url:
        return None
    return urllib.parse.unquote(url.rsplit("/", 1)[-1].replace("_", " "))

def fetch_and_save(movie_id, title, max_retries=3):
    save_path = WIKI_FETCH_DIR / f"{movie_id}.json"

    if save_path.exists():
        return "skipped"  # movie already fetched

    url = "https://en.wikipedia.org/w/api.php"
    params = {
        "action": "parse",
        "page": title,
        "prop": "text",
        "format": "json",
        "redirects": 1
    }

    for attempt in range(max_retries):
        try:
            response = requests.get(
                url, 
                params=params, 
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept-Language": "en",
                },
                timeout=20)
            response.raise_for_status()
            data = response.json()

            if "error" in data:
                return f"not_found: {data['error'].get('info')}"

            with open(save_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)

            return "ok"

        except requests.RequestException as e:
            if attempt < max_retries - 1:
                time.sleep(3 * (attempt + 1))  # wait longer each retry
            else:
                return f"failed: {e}"

    return "failed"

links = pd.read_csv(LINKS_PATH)
results = []

for _, row in links.iterrows():
    movie_id = row["movie_id"]
    title = row.get("wikipedia_title")

    if pd.isna(title) or str(title).strip() == "":
        title = article_title_from_url(row.get("wikipedia_url"))

    if pd.isna(title) or str(title).strip() == "":
        status = "unmatched"
    else:
        status = fetch_and_save(movie_id, title)

    results.append({"id": movie_id, "title": title, "status": status})
    print(movie_id, title, "->", status)
    time.sleep(5)  

pd.DataFrame(results).to_csv(WIKI_FETCH_DIR / "fetch_log.csv", index=False)