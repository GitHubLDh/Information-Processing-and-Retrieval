# Information Processing and Retrieval

Course project for **Information Processing and Retrieval (PRI)**, M.EIC, FEUP.

## Idea

Build a searchable movie collection by combining:
- **Kaggle movies dataset** — structured metadata (title, year, genre, cast, ratings, etc.)
- **Wikipedia plot summaries** — long free-text plot descriptions, fetched via the Wikipedia/MediaWiki API and linked to each movie

The goal is a document collection suitable for text-based search, where each document = a movie's metadata + its Wikipedia plot.

## Status

- [x] Topic and data sources selected
- [ ] Data collection pipeline (Kaggle + Wikipedia API join)
- [ ] Exploratory data analysis / dataset characterization
- [ ] Information needs defined
- [ ] Solr indexing (Milestone 2)
- [ ] Semantic search (Milestone 3)

## Milestones

1. **Data Preparation** — collect, clean, and characterize the dataset
2. **Information Retrieval** — index with Solr, run and evaluate free-text queries
3. **Search System** — add semantic retrieval, compare approaches

## Repository structure

```
data/
  raw/       original Kaggle CSVs (movies, cast, crew, genres, reviews) — never edit these
  sample/    small 75-movie subset for testing scripts before running on full data
  interim/   per-stage cleaned outputs (cleaned movies/reviews, Wikidata links, Wikipedia sections)
    fetch/   raw Wikipedia API responses (one JSON file per movie)
  final/     the final joined document collection, ready for Solr indexing

scripts/
  make_sample.py    builds data/sample/ from data/raw/
  clean_movies.py   cleans movies.csv + reviews.csv -> data/interim/
  wiki_fetch.py     fetches Wikipedia articles by title, caches raw JSON in data/wikipedia/fetch/
  wiki_parse.py     extracts the plot from each article -> data/wikipedia/parse/parsed_log.csv
```