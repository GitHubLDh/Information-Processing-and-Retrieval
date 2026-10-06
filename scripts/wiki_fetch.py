""""
fetches wikipedia articles by title for each movie in the sample, saves raw json responses to 
data/wikipedia/fetch/ (skips already-fetched movies, retries on failure, 1s pause between requests)
"""

import requests
import json
import time
from pathlib import Path
import pandas as pd


WIKIF_DIR = Path(__file__).resolve().parent.parent / "data" / "wikipedia" / "fetch"
WIKIF_DIR.mkdir(parents=True, exist_ok=True)
SAMPLE_DIR = Path(__file__).resolve().parent.parent / "data" / "sample"

def fetch_and_save(movie_id, title, max_retries=3):
    save_path = WIKIF_DIR / f"{movie_id}.json"

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
            response = requests.get(url, params=params, timeout=15)
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

movies = pd.read_csv(SAMPLE_DIR / "movies_sample.csv")

results = []
for _, row in movies.iterrows():
    status = fetch_and_save(row["id"], row["title"])
    results.append({"id": row["id"], "title": row["title"], "status": status})
    print(row["id"], row["title"], "->", status)
    time.sleep(1)  # pause between requests

results_df = pd.DataFrame(results)
results_df.to_csv(WIKIF_DIR / "fetch_log.csv", index=False)