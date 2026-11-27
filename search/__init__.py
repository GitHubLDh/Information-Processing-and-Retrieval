"""Shared building blocks for the Milestone 3 search systems.

The retrieval runners and the web page use the same ``Result`` shape, Solr
transport and TREC writer, so every system produces runs that
``eval/metrics.py`` can read.
"""

from .result import Result
from .run import format_trec_line, write_run
from .solr import post

__all__ = ["Result", "format_trec_line", "post", "write_run"]
