#!/usr/bin/env python3
"""Offline check of the shared search helpers against the frozen M2 A run.

Usage:
    python3 scripts/check_search_contract.py
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from search import Result, write_run  # noqa: E402
from search import solr  # noqa: E402


def saved_results(qid: str = "Q1") -> list[Result]:
    """Rebuild ``Result`` objects from a frozen per-query M2 A run."""
    payload = json.loads((ROOT / "runs" / f"A_{qid}.json").read_text(encoding="utf-8"))
    if payload.get("qid") != qid:
        raise ValueError(f"runs/A_{qid}.json has qid {payload.get('qid')!r}")
    return [
        Result(
            movie_id=item["movie_id"],
            title=item.get("title"),
            year=item.get("year"),
            score=item["score"],
            snippet=item.get("overview", ""),
        )
        for item in payload["results"]
    ]


def lines_for(text: str, qid: str) -> list[str]:
    """Return the TREC lines belonging to one query."""
    return [line for line in text.splitlines() if line.split(maxsplit=1)[0] == qid]


def check_trec_contract(qid: str = "Q1") -> tuple[bool, str]:
    """The new writer must reproduce the saved M2 A lines exactly."""
    ranking = saved_results(qid)
    with tempfile.TemporaryDirectory() as tmp:
        generated_path = write_run({qid: ranking}, Path(tmp) / "check.run", "A")
        generated = lines_for(generated_path.read_text(encoding="utf-8"), qid)
    saved = lines_for((ROOT / "runs" / "A.run").read_text(encoding="utf-8"), qid)

    if not saved:
        return False, f"no saved {qid} lines found in runs/A.run"
    if generated != saved:
        for index, (actual, expected) in enumerate(zip(generated, saved), start=1):
            if actual != expected:
                return False, f"line {index}: {actual!r} != {expected!r}"
        return False, f"line count differs: {len(generated)} != {len(saved)}"
    return True, (
        f"{len(saved)} {qid} lines reproduced byte-for-byte from runs/A_{qid}.json"
    )


def check_post_contract() -> tuple[bool, str]:
    """Check the Solr URL, form encoding and UTF-8 handling without a server."""

    class FakeResponse:
        encoding: str | None = None

        def raise_for_status(self) -> None:
            pass

        def json(self) -> dict:
            return {"responseHeader": {"status": 0}, "response": {"docs": []}}

    fake = FakeResponse()
    with patch.object(solr.requests, "post", return_value=fake) as mock_post:
        payload = solr.post({"q": "*:*"}, "http://localhost:8983/solr/", "movies")

    args, kwargs = mock_post.call_args
    if args[0] != "http://localhost:8983/solr/movies/select":
        return False, f"unexpected URL: {args[0]}"
    if kwargs.get("data") != {"q": "*:*"}:
        return False, f"unexpected form data: {kwargs.get('data')}"
    if fake.encoding != "utf-8":
        return False, f"unexpected encoding: {fake.encoding!r}"
    if payload != fake.json():
        return False, "unexpected payload"
    return True, "form POST URL/data and UTF-8 decoding are correct"


def main() -> int:
    ok = True
    for label, (passed, detail) in (
        ("TREC writer", check_trec_contract()),
        ("Solr transport", check_post_contract()),
    ):
        print(f"{label}: {'OK' if passed else 'FAIL'} - {detail}")
        ok = ok and passed
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
