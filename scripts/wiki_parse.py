"""
reads raw Wikipedia responses from the fetch archive, extracts the plot section from each article's html,
and writes a summary table to data/interim/wikipedia_plot.csv (movie_id,wiki_title,status,plot).
"""

import json
import sys
from pathlib import Path
from bs4 import BeautifulSoup
import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "interim" 
RESPONSE_PATH = DATA_DIR / "wikipedia_responses.jsonl"
PLOT_PATH = DATA_DIR / "wikipedia_plot.csv"

def extract_plot(html):
    soup = BeautifulSoup(html, "html.parser")
    in_plot = False
    plot_paragraphs = []
    heading_options = ["plot", "synopsis", "premise", "plot summary"]

    for tag in soup.find_all(["h2", "h3", "p"]):
        text = tag.get_text(" ", strip=True)

        if tag.name in ("h2", "h3"):
            heading = text.lower()

            if heading in heading_options:
                in_plot = True
                continue

            if in_plot:
                if tag.name == "h2":
                    break
                if text:
                    plot_paragraphs.append(text)
                continue

        if in_plot and tag.name == "p" and text:
            plot_paragraphs.append(text)

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

    for line_number, line in enumerate(RESPONSE_PATH.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            print(f"Skipping malformed JSONL record on line {line_number}: {exc}", file=sys.stderr)
            continue

        if not isinstance(record, dict):
            print(f"Skipping non-object record on line {line_number}", file=sys.stderr)
            continue

        if "movie_id" not in record or "response" not in record:
            print(f"Skipping incomplete record on line {line_number}", file=sys.stderr)
            continue

        yield str(record["movie_id"]), record["response"]


results = []
for movie_id, data in load_raw_records():
    result = process_data(data)
    result["movie_id"] = movie_id
    results.append(result)

df = pd.DataFrame(results)
df = df[["movie_id", "wiki_title", "status", "plot"]]  # reorder
df.to_csv(PLOT_PATH, index=False)