# Flask search page

A small demo interface over the shared retrieval registry. It does not write
run files and does not change the frozen M2 query builders.

## Run

Install the root requirements (including `flask`), start/index Solr as usual,
then:

```bash
python3 web/app.py
```

Open <http://127.0.0.1:5000/>. Override the defaults when needed:

```bash
PRI_SOLR_URI=http://127.0.0.1:18984/solr \
PRI_SOLR_COLLECTION=movies \
PRI_WEB_PORT=5000 \
python3 web/app.py
```

## What the page does

- `/` shows the query form, system dropdown and the five saved M3 needs as
  clickable examples.
- `/search?q=...&system=...&source=...` calls
  `registry.search_response()` with the selected system.
- Systems: `M2-A`, `M2-B`, `M3-lexical`, `semantic` and `hybrid`. The last two
  are registered stubs, so the page shows a "pending P2/P3" message instead of
  raising a 500.
- `source=story` searches `plot`; `source=reviews` uses the parent/child review
  join. Review needs such as Q1/Q2 should use the latter.
- `M3-lexical` uses the current frozen M3 baseline: Setup B's Solr parameters,
  including the top-20 overview rerank for story needs.
- Results show rank, title, year, score, matched field, a roughly 240-character
  snippet centred on the first matching query term, and a Wikipedia link when
  the movie has one. The page also shows Solr's `numFound` and measured search
  latency.

Plot text and Wikipedia URLs are display-only lookups from
`data/final/collection.jsonl`; they are not added to the frozen Solr `fl`
parameter. If that file is unavailable, the snippet falls back to the
`overview` returned by Solr and no Wikipedia link is shown.

## Error handling

- Empty query: the form is redisplayed with a message.
- Unknown `system`: a clear 400 page lists the available systems.
- Solr unreachable or HTTP error: a 502 page reports the endpoint.
- Bad query/config: a 400 page reports the underlying validation message.

Free-text web searches deliberately omit the genre filters used by the saved
Q1–Q5 runner configs, so web results are a demo and are not comparable with the
evaluation runs.
