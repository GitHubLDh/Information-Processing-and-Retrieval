#!/usr/bin/env python3
"""Shared helpers for the M2 evaluation: run loading, collection access, qrels."""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNS_DIR = ROOT / "runs"
QUERIES_DIR = ROOT / "queries"
COLLECTION_PATH = ROOT / "data" / "final" / "collection.jsonl"
EVAL_DIR = ROOT / "eval"
DEFAULT_POOL = EVAL_DIR / "pool.csv"
DEFAULT_QRELS = EVAL_DIR / "qrels.csv"

QIDS = ["Q1", "Q2", "Q3", "Q4", "Q5"]
SETUPS = ["A", "B"]

RELEVANCE_SCALE = {
    0: "not relevant",
    1: "partially relevant / weak or indirect evidence",
    2: "highly relevant / satisfies the need",
}

INFORMATION_NEEDS = {
    "Q1": {
        "title": "Clever, witty comedies",
        "need": (
            "A comedy whose reviewers describe its humour as clever, witty, or "
            "intellectually sharp, rather than slapstick or lowbrow."
        ),
        "criteria": (
            "The review text must explicitly praise the film's wit, intelligence, or "
            "sharp writing. A comedy that is only mildly funny, or relies on "
            "slapstick, is not relevant."
        ),
        "review_terms": [
            "clever", "witty", "wit", "smart", "intelligent", "sophisticated",
            "satire", "satirical", "cerebral", "sharp",
        ],
        "plot_terms": [],
    },
    "Q2": {
        "title": "Clichéd romantic movies",
        "need": (
            "A romantic comedy that reviewers call predictable or formulaic, while "
            "others still find it genuinely heartwarming."
        ),
        "criteria": (
            "The review text must show both sides of the reception: recognition of "
            "cliché or formula AND a warm/affectionate response. A straightforward "
            "romance with no such commentary is not relevant."
        ),
        "review_terms": [
            "predictable", "formulaic", "cliche", "cliched", "clichéd", "generic",
            "trope", "cheesy", "corny", "sappy", "sentimental", "by the numbers",
            "heartwarming", "heart warming", "heart-warming", "feel good",
            "feel-good",
        ],
        "plot_terms": [],
    },
    "Q3": {
        "title": "Stranded astronauts",
        "need": (
            "A science-fiction survival film about astronauts stranded away from "
            "Earth who need to survive or get home."
        ),
        "criteria": (
            "The plot must involve space travel, a stranded or isolated crew, and a "
            "survival or return objective. A film with only a brief space scene is "
            "not relevant."
        ),
        "review_terms": [],
        "plot_terms": [
            "astronaut", "cosmonaut", "spacecraft", "spaceship", "space station",
            "mars", "outer space", "space", "stranded", "marooned", "abandoned",
            "left behind", "lost in space", "adrift", "survive", "survival",
            "rescue", "return home", "back to earth", "earth",
        ],
    },
    "Q4": {
        "title": "FBI serial-killer investigation",
        "need": (
            "A crime or thriller film in which an FBI agent investigates serial "
            "killings."
        ),
        "criteria": (
            "The plot must centre on an FBI-led investigation of serial killings. A "
            "crime film with an incidental murder, or a non-FBI investigator, is not "
            "fully relevant."
        ),
        "review_terms": [],
        "plot_terms": [
            "fbi", "federal bureau", "special agent", "federal agent", "serial killer",
            "serial murder", "serial killings", "series of murders", "string of murders",
            "multiple murders", "killer", "murder", "profiler", "detective",
            "investigator", "police",
        ],
    },
    "Q5": {
        "title": "Italian-American organized crime",
        "need": (
            "A film about Italian-American organized-crime families and the loyalties "
            "and conflicts within them, rather than Russian or other organized crime."
        ),
        "criteria": (
            "The film must depict Italian-American organized crime as a central theme, "
            "and star Robert De Niro. Films about Russian mafia or other criminal "
            "organizations are not relevant even if De Niro appears."
        ),
        "review_terms": [
            "mafia", "mafioso", "mobster", "mob", "organized crime", "crime family",
            "cosa nostra", "wiseguy", "gangster", "italian", "italian american",
            "italian-american", "de niro", "deniro",
        ],
        "plot_terms": [
            "mafia", "mafioso", "mobster", "mob", "organized crime", "crime family",
            "cosa nostra", "wiseguy", "gangster", "italian", "italian american",
            "italian-american", "russian mafia", "de niro", "deniro",
        ],
    },
}


def read_text(path: Path) -> str:
    """Read a text file, tolerating the cp1252 bytes in some saved B run files."""
    data = Path(path).read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def load_json(path: Path) -> dict:
    return json.loads(read_text(path))


def load_collection(path: Path = COLLECTION_PATH) -> dict[str, dict]:
    """Return movie_id -> collection document."""
    collection: dict[str, dict] = {}
    with Path(path).open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            doc = json.loads(line)
            collection[str(doc["movie_id"])] = doc
    return collection


def load_trec_run(path: Path) -> dict[str, list[dict]]:
    """Load a TREC run file into qid -> ranked entries."""
    rankings: dict[str, list[dict]] = {}
    for line in read_text(path).splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) < 6:
            raise ValueError(f"Malformed TREC line in {path}: {line!r}")
        qid, _, docid, rank, score, _run_id = parts[:6]
        rankings.setdefault(qid, []).append({
            "docid": str(docid),
            "rank": int(rank),
            "score": float(score),
        })
    for entries in rankings.values():
        entries.sort(key=lambda item: item["rank"])
    return rankings


def load_json_run(path: Path) -> dict[str, list[dict]]:
    """Load one runs/{setup}_{qid}.json file into qid -> ranked entries."""
    payload = load_json(path)
    qid = payload["qid"]
    entries = []
    for item in payload.get("results", []):
        entries.append({
            "docid": str(item["movie_id"]),
            "rank": int(item.get("rank", len(entries) + 1)),
            "score": float(item.get("score") or 0.0),
        })
    entries.sort(key=lambda item: item["rank"])
    return {qid: entries}


def load_run(setup: str, runs_dir: Path = RUNS_DIR) -> dict[str, list[dict]]:
    """Load a setup's ranking, preferring the TREC file then per-query JSON."""
    trec_path = Path(runs_dir) / f"{setup}.run"
    if trec_path.exists():
        return load_trec_run(trec_path)
    rankings: dict[str, list[dict]] = {}
    for path in sorted(Path(runs_dir).glob(f"{setup}_Q*.json")):
        rankings.update(load_json_run(path))
    if not rankings:
        raise FileNotFoundError(f"No run files found for setup {setup} in {runs_dir}")
    return rankings


def load_qrels(path: Path = DEFAULT_QRELS) -> dict[str, dict[str, int]]:
    """Load graded qrels, skipping rows whose rel cell is blank."""
    qrels: dict[str, dict[str, int]] = {}
    with Path(path).open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        required = {"qid", "docid", "rel"}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError(f"{path} must have columns {sorted(required)}")
        for row in reader:
            rel_text = (row.get("rel") or "").strip()
            if not rel_text:
                continue
            rel = int(rel_text)
            if rel not in RELEVANCE_SCALE:
                raise ValueError(f"{path}: invalid rel {rel!r} for {row['qid']}/{row['docid']}")
            qrels.setdefault(row["qid"].strip(), {})[str(row["docid"]).strip()] = rel
    return qrels


def load_all_needs() -> dict[str, dict]:
    """Merge curated criteria with the need text stored in the query files."""
    needs = {qid: dict(value) for qid, value in INFORMATION_NEEDS.items()}
    for setup in ("setup_a", "setup_b"):
        for path in sorted((QUERIES_DIR / setup).glob("Q*.json")):
            payload = load_json(path)
            qid = payload["qid"]
            if qid in needs and payload.get("need"):
                needs[qid]["query_need"] = payload["need"]
    return needs


def clean_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    return text


def context_windows(text: str, terms: list[str], width: int = 260, limit: int = 4) -> list[str]:
    """Return short windows around the first occurrences of any term."""
    text = clean_text(text)
    lower = text.lower()
    windows: list[str] = []
    seen_spans: list[tuple[int, int]] = []

    for term in terms:
        if not term:
            continue
        for match in re.finditer(re.escape(term.lower()), lower):
            start = max(0, match.start() - width // 2)
            end = min(len(text), match.end() + width // 2)
            if any(start < seen_end and end > seen_start for seen_start, seen_end in seen_spans):
                continue
            seen_spans.append((start, end))
            snippet = text[start:end].strip()
            if start > 0:
                snippet = "..." + snippet
            if end < len(text):
                snippet = snippet + "..."
            windows.append(snippet)
            if len(windows) >= limit:
                return windows
    return windows


def matched_terms(text: str, terms: list[str]) -> list[str]:
    lower = (text or "").lower()
    return [term for term in terms if term.lower() in lower]


def review_evidence(record: dict, terms: list[str], limit: int = 3) -> list[str]:
    """Return snippets from reviews that mention any of the supplied terms."""
    snippets: list[str] = []
    for review in record.get("reviews") or []:
        text = review.get("text") or ""
        windows = context_windows(text, terms, width=280, limit=1)
        if windows:
            author = review.get("author") or "unknown"
            rating = review.get("rating")
            label = f"{author}" + (f", rating {rating}" if rating else "")
            snippets.append(f"[{label}] {windows[0]}")
            if len(snippets) >= limit:
                break
    return snippets


def plot_evidence(record: dict, terms: list[str], limit: int = 3) -> list[str]:
    windows = context_windows(record.get("plot") or "", terms, width=300, limit=limit)
    if not windows:
        windows = context_windows(record.get("overview") or "", terms, width=300, limit=limit)
    return windows


def document_evidence(record: dict, qid: str, review_limit: int = 3, plot_limit: int = 3) -> dict:
    need = INFORMATION_NEEDS[qid]
    return {
        "overview": clean_text(record.get("overview") or ""),
        "plot_excerpt": clean_text(record.get("plot") or "")[:700],
        "plot_windows": plot_evidence(record, need["plot_terms"], limit=plot_limit),
        "review_windows": review_evidence(record, need["review_terms"], limit=review_limit),
        "matched_plot_terms": matched_terms(record.get("plot") or "", need["plot_terms"]),
        "matched_review_terms": sorted({
            term
            for review in (record.get("reviews") or [])
            for term in matched_terms(review.get("text") or "", need["review_terms"])
        }),
    }
