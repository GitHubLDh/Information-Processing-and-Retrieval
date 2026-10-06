import json
from pathlib import Path
from bs4 import BeautifulSoup
import pandas as pd

WIKIF_DIR = Path(__file__).resolve().parent.parent / "data" / "wikipedia" / "fetch"

WIKIP_DIR = Path(__file__).resolve().parent.parent / "data" / "wikipedia" / "parse"
WIKIP_DIR.mkdir(parents=True, exist_ok=True)

def extract_sections(html):
    soup = BeautifulSoup(html, "html.parser")
    sections = {}
    current_heading = "intro"  # text before any heading (intro/lead paragraph)
    sections[current_heading] = []

    for tag in soup.find_all(["h2", "h3", "p"]):
        if tag.name in ("h2", "h3"):
            current_heading = tag.get_text().strip().lower()
            sections[current_heading] = []
        else:
            text = tag.get_text().strip()
            if text:
                sections[current_heading].append(text)

    return {k: " ".join(v) for k, v in sections.items() if v}

def get_field(sections, candidates):
    for name in candidates:
        if name in sections:
            return sections[name]
    return None

def extract_movie_fields(sections):
    return {
        "plot": get_field(sections, ["plot", "plot summary", "synopsis"]),
    }


def process_file(path):
    data = json.loads(path.read_text(encoding="utf-8"))

    if "error" in data:
        return {"status": "not_found"}

    html = data["parse"]["text"]["*"]

    sections = extract_sections(html)
    fields = extract_movie_fields(sections)
    fields["status"] = "ok"
    fields["wiki_title"] = data["parse"]["title"]
    return fields


results = []
for path in WIKIF_DIR.glob("*.json"):
    movie_id = path.stem
    result = process_file(path)
    result["movie_id"] = movie_id
    results.append(result)

pd.DataFrame(results).to_csv(WIKIP_DIR / "parsed_log.csv", index=False)