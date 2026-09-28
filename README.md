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

_TBD as the pipeline takes shape._
