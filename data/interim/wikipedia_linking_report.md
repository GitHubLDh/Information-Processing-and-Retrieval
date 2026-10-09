# Wikidata and Wikipedia linking

## Method and outputs

The linker joins TMDB movie IDs to Wikidata with **TMDB movie ID (P4947)**, then reads the item's English Wikipedia sitelink and **IMDb ID (P345)**. The property IDs were confirmed on [Wikidata's P4947 page](https://www.wikidata.org/wiki/Property:P4947) and [P345 page](https://www.wikidata.org/wiki/Property:P345). A hand-picked 20-movie sample query in the Wikidata Query Service returned all three fields together for all 20 sample movies.

`movies_clean.csv` contains 9,710 unique movies and has no IMDb ID column, so the full run used TMDB IDs only. The linker supports a second-pass IMDb lookup when an input has `imdb_id` or `imdb`; it was not applicable to this file.

- `movies_wikipedia_links.csv`: one row per movie with an English Wikipedia page (TMDB ID, article title and URL, IMDb ID when present, Wikidata ID, match method).
- `movies_wikipedia_unmatched.csv`: IDs without an English Wikipedia page, with a reason and Wikidata ID when an item was found.
- `movies_wikipedia_checkpoint.csv`: resumable per-ID query results. Keep this file if resuming; the script skips IDs already present there.
- `scripts/link_wikidata.py`: rerun with `python scripts/link_wikidata.py data/interim/movies_clean.csv --prefix movies`.

The SPARQL pattern tested in the website was:

```sparql
SELECT ?tmdb ?item ?itemLabel ?imdb ?article WHERE {
  VALUES ?tmdb { "157336" "27205" "24428" "155" "19995" "293660" "299536" "550" "278" "680" "118340" "13" "671" "1726" "68718" "603" "475557" "299534" "120" "597" }
  ?item wdt:P4947 ?tmdb .
  OPTIONAL { ?item wdt:P345 ?imdb }
  ?article schema:about ?item ; schema:isPartOf <https://en.wikipedia.org/> .
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}
```

## Coverage

| Outcome | Movies | Rate |
| --- | ---: | ---: |
| English Wikipedia article found | 7,016 | 72.26% |
| No article mapping | 2,694 | 27.74% |
| Total | 9,710 | 100% |

The unmatched file distinguishes **1,614** IDs with no Wikidata item found by TMDB ID and **1,080** Wikidata items that have no English Wikipedia sitelink. These counts are based on identifier lookup; a missing P4947 statement does not prove that no Wikidata item exists for the film.

### Coverage by release decade

| Release period | Linked / total | Rate |
| --- | ---: | ---: |
| Before 1950 | 285 / 364 | 78.3% |
| 1950s | 165 / 205 | 80.5% |
| 1960s | 161 / 241 | 66.8% |
| 1970s | 280 / 425 | 65.9% |
| 1980s | 497 / 674 | 73.7% |
| 1990s | 765 / 990 | 77.3% |
| 2000s | 1,289 / 1,643 | 78.5% |
| 2010s | 1,999 / 2,805 | 71.3% |
| 2020s | 1,575 / 2,363 | 66.7% |

Coverage is not monotonic by age: the 1960s and 1970s are lower than pre-1950 titles, and the 2020s are lower than the 2000s. Recent releases may have less mature Wikidata coverage, but this dataset alone does not establish why.

### Coverage by genre

Movies with multiple genres contribute to each listed genre.

| Genre | Linked / total | Rate |
| --- | ---: | ---: |
| Adventure | 1,150 / 1,265 | 90.9% |
| Western | 129 / 140 | 92.1% |
| Documentary | 107 / 286 | 37.4% |
| TV Movie | 142 / 344 | 41.3% |
| Drama | 3,158 / 4,314 | 73.2% |
| Comedy | 2,160 / 2,771 | 78.0% |
| Action | 1,672 / 1,962 | 85.2% |
| Thriller | 1,764 / 2,155 | 81.9% |
| Science Fiction | 834 / 1,004 | 83.1% |
| Animation | 524 / 676 | 77.5% |

Adventure and Western have high coverage, while documentary and TV movie records have much lower coverage. Genre counts overlap, and the smaller genres have less stable rates.

## Manual checks

Eight successful sample mappings were opened as English Wikipedia pages and checked against the expected movie: *Star Wars*, *Inception*, *Avatar*, *WALL-E*, *Titanic*, *Interstellar*, *The Dark Knight*, and *The Shawshank Redemption*. Their article titles identify the film pages, not a disambiguation page or a redirect target.

I also spot-checked 20 unmatched titles by opening their same-title English Wikipedia pages where available. The audit found concrete title-collision cases: [Rita](https://en.wikipedia.org/wiki/Rita) is a disambiguation page; [The Photographer](https://en.wikipedia.org/wiki/The_Photographer) redirects to [Photographer (disambiguation)](https://en.wikipedia.org/wiki/Photographer_(disambiguation)); [Roxanna](https://en.wikipedia.org/wiki/Roxanna) is a disambiguation page; [Scars](https://en.wikipedia.org/wiki/Scars) redirects to the medical topic [Scar](https://en.wikipedia.org/wiki/Scar); [Bardot](https://en.wikipedia.org/wiki/Bardot) is a disambiguation page; and [Ladylike](https://en.wikipedia.org/wiki/Ladylike) and [Baby Money](https://en.wikipedia.org/wiki/Baby_Money) refer to an album and a rapper, respectively. These examples support using Wikidata identifiers rather than matching on title alone. They are examples from a spot check, not a count of all failures caused by redirects or disambiguation.

## Information needs and preliminary query checks

The Wikipedia article corpus has not yet been fetched into `data/final`; these preliminary checks use the cleaned movie title and plot overview as available text. Repeat the same information needs against the merged article collection and Solr index after P3 finishes.

1. **Need:** Find science-fiction survival films about astronauts stranded away from Earth who need to survive or get home. **Query:** `astronaut stranded mars survive home`. A simple IDF-weighted lexical ranking of title plus overview placed *The Martian* first (2015; Adventure, Drama, Science Fiction), with the query terms “astronaut,” “stranded,” and “mars” in its overview.
2. **Need:** Find crime or thriller films in which an FBI agent investigates serial killings. **Query:** `fbi agent investigates a serial killer using clues`. The preliminary ranking returned *Switchback* (1997), *Longlegs* (2024), and *Solace* (2015) in its top three; all have crime/thriller or mystery genre labels and overviews describing FBI agents and serial killers.

These are functional smoke checks on the present plot metadata, not a relevance evaluation or a Solr test.
