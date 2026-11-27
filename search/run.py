"""Write ranked ``Result`` objects in the project's TREC run format."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

from .result import Result


def format_trec_line(qid: str, result: Result, rank: int, run_id: str) -> str:
    """Return one ``qid Q0 docid rank score run_id`` line."""
    for label, value in (("qid", qid), ("run_id", run_id)):
        if not value or any(char.isspace() for char in value):
            raise ValueError(f"{label} must be a non-empty token, got {value!r}")
    if isinstance(rank, bool) or not isinstance(rank, int) or rank < 1:
        raise ValueError(f"rank must be a positive int, got {rank!r}")
    if result.score is None:
        raise ValueError(
            f"{qid} result {rank} has no score; refusing to write an unstable run"
        )
    return f"{qid} Q0 {result.movie_id} {rank} {result.score} {run_id}"


def write_run(
    rankings: Mapping[str, Sequence[Result]], path: Path, run_id: str
) -> Path:
    """Write ``path`` with one TREC line per result and return the path."""
    lines: list[str] = []
    for qid in sorted(rankings):
        seen: set[int] = set()
        for rank, result in enumerate(rankings[qid], start=1):
            if result.movie_id in seen:
                raise ValueError(f"{qid} returned movie {result.movie_id} more than once")
            seen.add(result.movie_id)
            lines.append(format_trec_line(qid, result, rank, run_id))

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(("\n".join(lines) + "\n") if lines else "", encoding="utf-8")
    return path
