"""
reads raw json from data/wikipedia/fetch/, extracts the plot section from each article's html, 
and writes a summary table to data/wikipedia/parse/parsed_log.csv (movie_id, title, status, plot)
"""

import json
from pathlib import Path
from bs4 import BeautifulSoup
import pandas as pd

WIKI_FETCH_DIR = Path(__file__).resolve().parent.parent / "data" / "interim" / "fetch"
PLOT_PATH = Path(__file__).resolve().parent.parent / "data" / "interim" / "wikipedia_plot.csv"

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


def process_file(path):
    data = json.loads(path.read_text(encoding="utf-8"))

    if "error" in data:
        return {"status": "not_found", "plot": None, "wiki_title": None}

    html = data["parse"]["text"]["*"]
    plot = extract_plot(html)

    return {
        "status": "ok" if plot else "no_plot",
        "plot": plot,
        "wiki_title": data["parse"]["title"],
    }


results = []
for path in WIKI_FETCH_DIR.glob("*.json"):
    movie_id = path.stem
    result = process_file(path)
    result["movie_id"] = movie_id
    results.append(result)

df = pd.DataFrame(results)
df = df[["movie_id", "wiki_title", "status", "plot"]] # reorder
df.to_csv(PLOT_PATH, index=False)