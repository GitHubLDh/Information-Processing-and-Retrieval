# Wikipedia fetch and plot extraction

## Summary

This stage turns the Wikidata-linked English Wikipedia article set into a usable narrative-text corpus for retrieval. The fetch pipeline succeeded on 7,014 out of 7,016 linked titles, and the parser extracted a plot summary for 6,478 pages. In practice, this means the project now has a large and useful collection of Wikipedia plot text that can support topical and narrative retrieval, with a smaller set of pages still needing manual review.

## Source data and method

Scripts:
- [`scripts/wiki_fetch.py`](../../scripts/wiki_fetch.py)
- [`scripts/wiki_parse.py`](../../scripts/wiki_parse.py)

Inputs and outputs:
- `data/interim/movies_wikipedia_links.csv` — 7,016 movies with an English Wikipedia article match
- `data/interim/wikipedia_responses.jsonl` — raw parse responses from the MediaWiki API
- `data/interim/wikipedia_plot.csv` — extracted plot summary for each movie
- `data/interim/failed_fetches.csv` — permanent fetch failures

The fetch script calls the MediaWiki API with `action=parse`, `prop=text`, and `redirects=1` for each linked movie title. This ensures that page redirects are followed and that the returned HTML is the canonical article content. Each successful response is appended as a JSON record containing the movie ID, title, and full parsed response payload.

The parse script then loads the saved HTML from the JSONL archive and extracts the narrative section. It scans the article heading structure and collects paragraph text when a heading matches one of the expected plot-related labels, such as `Plot`, `Synopsis`, or `Premise`.

## Fetch coverage

| Metric | Value |
|---|---:|
| Linked English Wikipedia titles | 7,016 |
| Valid response records saved | 7,014 |
| Successful fetch rate | 99.97% |
| Permanent fetch failures | 1 |
| Malformed JSONL records skipped | 2 |
| Total processed pages in `wikipedia_plot.csv` | 7,014 |

### Interpretation

The fetch stage is extremely reliable. Only one title failed permanently: `36593` / `3: The Final Insult`, which returned a Wikipedia `not_found` response. The two malformed JSONL records were not valid archive entries and were skipped during parsing rather than treated as usable data.

This means the Wikipedia fetch is effectively complete for the linked set, with only minimal loss from a single unavailable page and a couple of interrupted archive writes.

## Plot extraction quality

The parse stage is judged by whether a plot section could be extracted from the HTML of each fetched article.

| Status | Count | Rate |
|---|---:|---:|
| `ok` | 6,478 | 92.36% |
| `no_plot` | 536 | 7.64% |
| Total processed pages | 7,014 | 100% |

The extraction succeeded for 6,478 pages, while 536 pages were left without usable narrative text. The `no_plot` pages are not necessarily broken fetches; they are usually articles whose structure does not expose a standard plot section or whose page content is too sparse or non-standard for the parser to detect.

## Plot-text statistics

Computed on the 6,478 extracted plot summaries:

| Metric | Value |
|---|---:|
| Mean plot length | 511 words |
| Median plot length | 580 words |
| Min plot length | 10 words |
| Max plot length | 3,253 words |
| Mean plot length (characters) | 3,010 |
| Median plot length (characters) | 3,421 |
| Min plot length (characters) | 61 |
| Max plot length (characters) | 19,138 |

These values show that the extracted plot field is substantial enough for keyword-matching and narrative retrieval. The median length is close to 580 words, and the distribution is broad, which is desirable for a collection intended to support vague memory queries and thematic matching.

## Data-quality issues and failure modes

A small fraction of the fetched pages still require attention:

- `no_plot` is the major exception, accounting for 536 records.
- Many of these cases are structurally unusual pages rather than network failures.
- Example `no_plot` titles include `Princess Mononoke`, `Fantasia (1940 film)`, `Earth (1996 film)`, and `The Holes`.
- In some cases, the article title is an older or unusual title variant, or the page does not use a conventional `Plot` heading.
- The parser is intentionally narrow: it only captures text under a known plot-like heading and stops at the next major section. This keeps the extracted text clean, but it misses pages whose narrative description is stored in a different section or presented as a lead paragraph instead.

This is a data-quality issue rather than a fetch-completion issue. The articles are available, but not all of them expose a clean plot section to the current parser.