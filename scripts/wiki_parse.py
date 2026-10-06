import json
from pathlib import Path
from bs4 import BeautifulSoup
import pandas as pd

WIKIF_DIR = Path(__file__).resolve().parent.parent / "data" / "wikipedia" / "fetch"

WIKIP_DIR = Path(__file__).resolve().parent.parent / "data" / "wikipedia" / "parse"
WIKIP_DIR.mkdir(parents=True, exist_ok=True)

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
        "status": "ok" if plot else "no_plot_section",
        "plot": plot,
        "wiki_title": data["parse"]["title"],
    }


results = []
for path in WIKIF_DIR.glob("*.json"):
    movie_id = path.stem
    result = process_file(path)
    result["movie_id"] = movie_id
    results.append(result)

pd.DataFrame(results).to_csv(WIKIP_DIR / "parsed_log.csv", index=False)