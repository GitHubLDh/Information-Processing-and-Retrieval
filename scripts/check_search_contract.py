#!/usr/bin/env python3
"""Offline check of the shared search helpers against the frozen M2 runs.

Usage:
    python3 scripts/check_search_contract.py
"""

from __future__ import annotations

import io
import json
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from search import Result, write_run  # noqa: E402
from search import lexical, registry, solr  # noqa: E402

import run_system  # noqa: E402


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


def fake_solr_payload(saved: dict) -> dict:
    """Build a Solr-shaped response from a frozen per-query JSON run."""
    docs = [
        {
            "id": f"movie-{item['movie_id']}",
            "movie_id": item["movie_id"],
            "title": item.get("title"),
            "year": item.get("year"),
            "score": item["score"],
            "overview": item.get("overview", ""),
        }
        for item in saved["results"]
    ]
    return {
        "responseHeader": {"status": 0},
        "response": {"numFound": saved["num_found"], "docs": docs},
    }


def check_m2_backends() -> tuple[bool, str]:
    """The registry must reproduce both frozen A and B runs exactly."""
    failures: list[str] = []
    for setup_dir, setup in (("setup_a", "A"), ("setup_b", "B")):
        saved_by_qid: dict[str, dict] = {}
        for path in sorted((ROOT / "runs").glob(f"{setup}_Q*.json")):
            saved = json.loads(path.read_text(encoding="utf-8"))
            saved_by_qid[saved["qid"]] = saved

        text_to_qid = {saved["need"]: qid for qid, saved in saved_by_qid.items()}
        payload_by_text = {
            saved["need"]: fake_solr_payload(saved) for saved in saved_by_qid.values()
        }
        calls: list[dict] = []

        def fake_post(params, *_args, **_kwargs):
            calls.append(params)
            return payload_by_text[params["text"]]

        rankings: dict[str, list[Result]] = {}
        with patch.object(lexical, "post", side_effect=fake_post):
            for query_file in sorted((ROOT / "queries" / setup_dir).glob("Q*.json")):
                need = json.loads(query_file.read_text(encoding="utf-8"))
                rankings[need["qid"]] = registry.search(need, f"m2_{setup.lower()}")

        if len(calls) != len(saved_by_qid):
            failures.append(
                f"{setup}: expected {len(saved_by_qid)} Solr calls, got {len(calls)}"
            )
        for params in calls:
            qid = text_to_qid.get(params.get("text"))
            expected = saved_by_qid.get(qid, {}).get("query_params")
            if expected is not None and params != expected:
                failures.append(f"{setup} {qid}: generated Solr parameters differ")

        for qid, results in rankings.items():
            saved_items = saved_by_qid[qid]["results"]
            if len(results) != len(saved_items):
                failures.append(f"{setup} {qid}: result count differs")
                continue
            for rank, (result, item) in enumerate(zip(results, saved_items), start=1):
                actual = (
                    result.movie_id, result.title, result.year, result.score, result.snippet
                )
                expected = (
                    item["movie_id"], item.get("title"), item.get("year"),
                    item["score"], item.get("overview", ""),
                )
                if actual != expected:
                    failures.append(f"{setup} {qid} rank {rank}: result fields differ")

        with tempfile.TemporaryDirectory() as tmp:
            generated_path = write_run(rankings, Path(tmp) / f"{setup}.run", setup)
            generated = generated_path.read_text(encoding="utf-8").splitlines()
        saved_lines = (ROOT / "runs" / f"{setup}.run").read_text(encoding="utf-8").splitlines()
        if generated != saved_lines:
            failures.append(f"{setup}: generated run differs from runs/{setup}.run")

    for stub in sorted(registry.STUBS):
        try:
            registry.search({}, stub)
        except NotImplementedError:
            pass
        else:
            failures.append(f"{stub} stub does not raise NotImplementedError")

    if failures:
        return False, "; ".join(failures[:3])
    return True, "m2_a and m2_b reproduce both saved parameter sets and run files"


def check_runner() -> tuple[bool, str]:
    """The generic runner must reproduce the saved B run from queries/m3."""
    saved_by_qid: dict[str, dict] = {}
    for path in sorted((ROOT / "runs").glob("B_Q*.json")):
        saved = json.loads(path.read_text(encoding="utf-8"))
        saved_by_qid[saved["qid"]] = saved
    payload_by_text = {
        saved["need"]: fake_solr_payload(saved) for saved in saved_by_qid.values()
    }

    def fake_post(params, *_args, **_kwargs):
        return payload_by_text[params["text"]]

    previous_argv = sys.argv
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        sys.argv = [
            "run_system.py",
            "--system", "m3_lexical",
            "--queries", str(ROOT / "queries" / "m3"),
            "--run-id", "B",
            "--runs", tmp,
        ]
        try:
            with patch.object(lexical, "post", side_effect=fake_post):
                with redirect_stdout(io.StringIO()):
                    run_system.main()
        finally:
            sys.argv = previous_argv

        generated_path = tmp_path / "B.run"
        if not generated_path.exists():
            return False, "runner did not write a TREC run"
        if generated_path.read_text(encoding="utf-8") != (
            ROOT / "runs" / "B.run"
        ).read_text(encoding="utf-8"):
            return False, "runner output differs from runs/B.run"

        json_files = sorted(tmp_path.glob("B_Q*.json"))
        if len(json_files) != len(saved_by_qid):
            return False, f"expected {len(saved_by_qid)} per-query JSON files, got {len(json_files)}"
        for path in json_files:
            output = json.loads(path.read_text(encoding="utf-8"))
            if "latency_ms" not in output or "query_params" not in output:
                return False, f"{path.name} is missing run metadata"

    return True, "runner reproduces runs/B.run from queries/m3 with per-query metadata"


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
        ("M2 backends", check_m2_backends()),
        ("Runner", check_runner()),
        ("Solr transport", check_post_contract()),
    ):
        print(f"{label}: {'OK' if passed else 'FAIL'} - {detail}")
        ok = ok and passed
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
