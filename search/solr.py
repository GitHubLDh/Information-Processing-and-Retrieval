"""Minimal Solr transport shared by the retrieval runners and the web page."""

from __future__ import annotations

from typing import Any

import requests

DEFAULT_SOLR_URI = "http://localhost:8983/solr"
DEFAULT_COLLECTION = "movies"


def post(
    params: dict[str, Any],
    solr_uri: str = DEFAULT_SOLR_URI,
    collection: str = DEFAULT_COLLECTION,
    timeout: float = 60,
) -> dict:
    """POST form-encoded parameters to ``<solr_uri>/<collection>/select``.

    Form encoding is deliberate: parameter dereferencing such as ``v=$text``
    in the nested parent/child queries silently returns nothing under Solr's
    JSON Request API. Solr's JSON is UTF-8, so set the encoding explicitly
    rather than letting ``requests`` guess ISO-8859-1 from a header without a
    charset.
    """
    response = requests.post(
        f"{solr_uri.rstrip('/')}/{collection}/select",
        data=params,
        timeout=timeout,
    )
    response.encoding = "utf-8"
    response.raise_for_status()
    payload = response.json()
    status = payload.get("responseHeader", {}).get("status", 0)
    if status != 0:
        raise RuntimeError(f"Solr returned response status {status}: {payload}")
    return payload
