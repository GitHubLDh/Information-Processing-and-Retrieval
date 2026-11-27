"""Shared building blocks for the Milestone 3 search systems.

The retrieval runners and the web page use the same ``Result`` shape, Solr
transport and TREC writer, so every system produces runs that
``eval/metrics.py`` can read.
"""

from .registry import SYSTEMS, is_implemented, search, system_names
from .result import Result
from .run import format_trec_line, write_run
from .solr import post

__all__ = [
    "Result",
    "SYSTEMS",
    "format_trec_line",
    "is_implemented",
    "post",
    "search",
    "system_names",
    "write_run",
]
