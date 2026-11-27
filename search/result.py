"""The common result shape returned by every retrieval system."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Result:
    """One movie in a ranked list.

    ``snippet`` is display text for the search page (a plot excerpt, or the
    matching review/overview). ``matched_field`` records which Solr field
    supplied the score, when the system knows it.
    """

    movie_id: int
    title: str | None = None
    year: int | None = None
    score: float | None = None
    snippet: str = ""
    matched_field: str | None = None

    def __post_init__(self) -> None:
        if isinstance(self.movie_id, bool) or not isinstance(self.movie_id, int):
            raise TypeError(f"movie_id must be an int, got {self.movie_id!r}")
        if self.score is not None and (
            isinstance(self.score, bool) or not isinstance(self.score, (int, float))
        ):
            raise TypeError(f"score must be a number or None, got {self.score!r}")
        if not isinstance(self.snippet, str):
            raise TypeError(f"snippet must be a string, got {self.snippet!r}")
