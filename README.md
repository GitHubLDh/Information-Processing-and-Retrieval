# Information Processing and Retrieval

Course project for **Information Processing and Retrieval (PRI)**, M.EIC, FEUP.

## Idea

Build a searchable movie collection by combining:
- **Kaggle movies dataset** — structured metadata (title, year, genre, cast, ratings, etc.)
- **Wikipedia plot summaries** — long free-text plot descriptions, fetched via the Wikipedia/MediaWiki API and linked to each movie

The goal is a document collection suitable for text-based search, where each document = a movie's metadata + its Wikipedia plot.

## Status

- [x] Topic and data sources selected
- [x] Data collection pipeline (Kaggle + Wikipedia API join)
- [x] Exploratory data analysis / dataset characterization
- [x] Information needs defined
- [x] Solr indexing, Setup A/B retrieval runs, pooled judgments, and evaluation metrics (Milestone 2)
- The natural-language A/B runs use the same needs and constraints. See the [retrieval experiments](docs/query_specification.md) and [current judgment coverage and results](eval/output/results.md).
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
  interim/   per-stage cleaned outputs plus cached Wikipedia API responses
  final/     the final joined document collection, ready for Solr indexing

scripts/
  make_sample.py          builds data/sample/ from data/raw/
  clean_movies.py         cleans movies.csv + reviews.csv -> data/interim/
  aggregate_cast_crew.py  aggregates cast/crew rows -> data/interim/castcrew_agg.csv
  link_wikidata.py        links movies to Wikipedia via Wikidata
  wiki_fetch.py           caches Wikipedia API responses in data/interim/wikipedia_responses.jsonl
  wiki_parse.py           extracts plots -> data/interim/wikipedia_plot.csv
  build_collection.py     joins interim files -> data/final/collection.jsonl + Solr upload file
  solr_client.py          runs Setup A or B query files and writes JSON and TREC runs
  demo_queries.py         prints a side-by-side A/B demo against the running index
  verify_index.py         checks the indexed collection against the source documents

eval/
  README.md         evaluation workflow and directory layout
  pool.py           unions A/B top-20 runs into the pooled judgment set
  judge.py          interactive relevance-judging helper
  metrics.py        computes P@k, MAP, nDCG, recall, PR curves, and tables
  data/
    pool.csv        pooled candidate set
    qrels.csv       pooled graded relevance judgments
    qrels_template.csv  blank judgment sheet
    evidence.csv    pooled evidence used in manual judging
  judging/          human-readable movie evidence sheets used during manual grading
  output/
    results.md      generated evaluation results
```

## Requirements

- Python 3.10+
- `trec_eval` on PATH for final evaluation
- Docker Desktop / Docker Engine (for Solr)
- `curl`, `jq` (Solr startup/verification)
- `latexmk` with `pdflatex` (report build)
- Python packages:

```bash
python3 -m pip install requests pandas beautifulsoup4 jsonschema
```

`matplotlib` is only needed for the optional EDA charts.

## Running the project

Run all commands from the repository root.

### 1. Build the collection

```bash
python3 scripts/clean_movies.py
python3 scripts/aggregate_cast_crew.py
python3 scripts/link_wikidata.py data/interim/movies_clean.csv
python3 scripts/wiki_fetch.py
python3 scripts/wiki_parse.py
python3 scripts/build_collection.py
```

This produces `data/final/collection.jsonl` and `data/final/solr_documents.json`.
`link_wikidata.py` and `wiki_fetch.py` call external APIs and checkpoint their
progress, so rerunning resumes instead of starting over. If `data/final/` already
exists, skip to step 2.

### 2. Start Solr and index

```bash
bash solr/startup.sh
python3 scripts/verify_index.py
```

`startup.sh` recreates the `solr_pri` container and wipes/reindexes the `movies`
core, so do not run it while an index you need is already loaded.

### 3. Run retrieval

```bash
python3 scripts/solr_client.py --queries queries/setup_a --setup A
python3 scripts/solr_client.py --queries queries/setup_b --setup B
python3 scripts/demo_queries.py
```

The two `solr_client.py` calls write `runs/A_Q*.json`, `runs/B_Q*.json`,
`runs/A.run`, and `runs/B.run`. `demo_queries.py` prints a side-by-side A/B
comparison without writing files.
B reranks the top 20 plot matches using their overviews. Review searches are identical in both setups.

### 4. Evaluate

Build the shared pool from the top 20 results of both setups, then judge the
pooled candidates. Judgments are saved to `eval/data/qrels.csv` as you go, so you
can resume later without re-entering grades:

```bash
python3 eval/pool.py
python3 eval/judge.py --judge "Your Name"
python3 eval/metrics.py
```

The judge accepts grades `0` (not relevant), `1` (partially relevant), and `2`
(highly relevant). It skips candidates already judged; use `--review` to revisit
existing grades. See [eval/README.md](eval/README.md) for the full judging
workflow and options.

### 5. Build the report

```bash
cd report
latexmk -pdf main.tex
```

The PDF is written to `report/main.pdf`.

### Shortest end-to-end path

With the indexed `movies` core running and `data/final/` available:

```bash
python3 scripts/verify_index.py
python3 scripts/solr_client.py --queries queries/setup_a --setup A
python3 scripts/solr_client.py --queries queries/setup_b --setup B
python3 eval/pool.py
python3 eval/judge.py --judge "Your Name"
python3 eval/metrics.py
cd report && latexmk -pdf main.tex
```

Rebuild the judging sheet and repeat the manual export whenever the pool changes.
