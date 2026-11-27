"""Registry of retrieval systems used by runners and the search page.

P2 and P3 implement the ``semantic`` and ``hybrid`` stubs with the same
``(need, *, uri, collection) -> list[Result]`` signature, then add them here.
"""

from __future__ import annotations

from functools import partial

from . import lexical
from .result import Result
from .solr import DEFAULT_COLLECTION, DEFAULT_SOLR_URI

STUBS = {"semantic", "hybrid"}


def semantic(
    need: dict,
    *,
    uri: str = DEFAULT_SOLR_URI,
    collection: str = DEFAULT_COLLECTION,
) -> list[Result]:
    """P2: encode the need and run KNN against the vector field."""
    raise NotImplementedError("semantic retrieval is not registered yet (P2/P3)")


def hybrid(
    need: dict,
    *,
    uri: str = DEFAULT_SOLR_URI,
    collection: str = DEFAULT_COLLECTION,
) -> list[Result]:
    """P3: combine the lexical and semantic rankings."""
    raise NotImplementedError("hybrid retrieval is not registered yet (P2/P3)")


SYSTEMS = {
    "m2_a": partial(lexical.search_m2, system="m2_a"),
    "m2_b": partial(lexical.search_m2, system="m2_b"),
    "semantic": semantic,
    "hybrid": hybrid,
}


def system_names() -> tuple[str, ...]:
    """Return the registered system names in display order."""
    return tuple(SYSTEMS)


def is_implemented(system: str) -> bool:
    """Whether a registered system has a backend yet."""
    return system in SYSTEMS and system not in STUBS


def search(
    need: dict,
    system: str,
    *,
    uri: str = DEFAULT_SOLR_URI,
    collection: str = DEFAULT_COLLECTION,
) -> list[Result]:
    """Run ``system`` for ``need`` and return a ranked list of movies."""
    try:
        backend = SYSTEMS[system]
    except KeyError:
        raise ValueError(
            f"Unknown system {system!r}; available: {', '.join(system_names())}"
        ) from None
    return backend(need, uri=uri, collection=collection)
