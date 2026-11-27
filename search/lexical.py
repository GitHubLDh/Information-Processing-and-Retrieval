"""Lexical retrieval backends, including the frozen Milestone 2 A/B systems.

``query_params`` mirrors ``scripts/solr_client.py`` exactly. It must stay in
sync with the saved A/B runs: the offline contract check compares generated
parameters and rankings with those runs.
"""

from __future__ import annotations

from .result import Result, SearchResponse
from .solr import DEFAULT_COLLECTION, DEFAULT_SOLR_URI, post

M2_SETUPS = {"m2_a": "A", "m2_b": "B"}
M3_SYSTEMS = {"m3_lexical"}


def query_params(query: dict, setup: str) -> dict:
    """Build the frozen M2 Solr parameters for one natural-language need."""
    if "params" in query:  # Older saved query definitions already contain Solr parameters.
        return query["params"]
    if setup not in {"A", "B"} or query["source"] not in {"reviews", "story"}:
        raise ValueError("Expected setup A/B and source reviews/story")
    reviews = query["source"] == "reviews"
    fields = "review_text" if reviews else "plot"
    params = {
        "q": "{!edismax v=$text}",
        "text": query["need"],
        "qf": fields,
        "mm": "1",
        "q.op": "OR",
        "fq": ["doc_type:movie", *query["filters"]],
        "rows": 20,
        "fl": "movie_id,id,title,score,overview,year",
        "wt": "json",
    }
    if reviews:
        params["childq"] = params["q"]
        params["q"] = '{!parent which="doc_type:movie" score=max v=$childq}'
    elif setup == "B":
        params["overviewq"] = "{!edismax qf=overview v=$text}"
        params["rq"] = "{!rerank reRankQuery=$overviewq reRankDocs=20 reRankWeight=1}"
    return params


def to_results(payload: dict, *, source: str, setup: str = "A") -> list[Result]:
    """Convert a Solr response into ranked ``Result`` objects."""
    results: list[Result] = []
    seen_movie_ids: set[int] = set()
    matched_field = (
        "review_text" if source == "reviews" else "plot+overview" if setup == "B" else "plot"
    )
    for rank, doc in enumerate(payload["response"]["docs"], start=1):
        movie_id = doc.get("movie_id")
        if movie_id is None:
            raise RuntimeError(f"result {rank} is missing movie_id; refusing to write an unstable run")
        if movie_id in seen_movie_ids:
            raise RuntimeError(f"returned movie {movie_id} more than once")
        seen_movie_ids.add(movie_id)
        expected_id = f"movie-{movie_id}"
        if doc.get("id") != expected_id:
            raise RuntimeError(f"result {rank} has id {doc.get('id')!r}, expected {expected_id!r}")
        results.append(
            Result(
                movie_id=movie_id,
                title=doc.get("title"),
                year=doc.get("year"),
                score=doc.get("score"),
                snippet=doc.get("overview") or "",
                matched_field=matched_field,
            )
        )
    return results


def run_lexical(
    need: dict,
    system: str,
    *,
    uri: str = DEFAULT_SOLR_URI,
    collection: str = DEFAULT_COLLECTION,
) -> SearchResponse:
    """Run a registered lexical system (M2 or M3) for one need."""
    if system in M2_SETUPS:
        setup = M2_SETUPS[system]
    elif system in M3_SYSTEMS:
        if "params" not in need:
            raise ValueError(f"{system} needs an explicit params block in the query config")
        setup = "A"
    else:
        raise ValueError(f"Not a lexical system: {system!r}")

    params = query_params(need, setup)
    if system in M3_SYSTEMS and "rq" in params:
        setup = "B"  # metadata only: this run also reranks with the overview
    payload = post(params, uri, collection)
    return SearchResponse(
        results=to_results(payload, source=need.get("source", "story"), setup=setup),
        query_params=params,
        num_found=payload["response"].get("numFound"),
    )


def search_m2(
    need: dict,
    system: str,
    *,
    uri: str = DEFAULT_SOLR_URI,
    collection: str = DEFAULT_COLLECTION,
) -> list[Result]:
    """Backward-compatible M2 entry point returning just the ranked results."""
    return run_lexical(need, system, uri=uri, collection=collection).results
