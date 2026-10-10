"""
reads raw Wikipedia responses from the fetch archive, extracts the plot section from each article's html,
and writes a summary table to data/interim/wikipedia_plot.csv (movie_id,wiki_title,status,plot).
"""

import json
from pathlib import Path
from bs4 import BeautifulSoup
import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "interim" 
RESPONSE_PATH = DATA_DIR / "wikipedia_responses.jsonl"
PLOT_PATH = DATA_DIR / "wikipedia_plot.csv"

def extract_plot(html):
    soup = BeautifulSoup(html, "html.parser")
    current_heading = None
    plot_paragraphs = []

    for tag in soup.find_all(["h2", "h3", "p"]):
        if tag.name in ("h2", "h3"):
            current_heading = tag.get_text().strip().lower()
        elif current_heading == "plot":
            text = tag.get_text().strip()
            if text:
                plot_paragraphs.append(text)
        elif current_heading is not None and plot_paragraphs:
            # moved past the plot section (stop)
            break

    return " ".join(plot_paragraphs) if plot_paragraphs else None


def process_data(data):
    if "error" in data:
        return {"status": "not_found", "plot": None, "wiki_title": None}

    html = data["parse"]["text"]["*"]
    plot = extract_plot(html)

    return {
        "status": "ok" if plot else "no_plot",
        "plot": plot,
        "wiki_title": data["parse"]["title"],
    }


def load_raw_records():
    if not RESPONSE_PATH.exists():
        raise FileNotFoundError(f"Missing Wikipedia response archive: {RESPONSE_PATH}")

    for line in RESPONSE_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        yield str(record["movie_id"]), record["response"]


results = []
for movie_id, data in load_raw_records():
    result = process_data(data)
    result["movie_id"] = movie_id
    results.append(result)

df = pd.DataFrame(results)
df = df[["movie_id", "wiki_title", "status", "plot"]]  # reorder
df.to_csv(PLOT_PATH, index=False)