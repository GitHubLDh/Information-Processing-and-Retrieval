# Demo runbook (Milestone 2)

Reproducible walkthrough for the indexing/retrieval demo. The demo shows that the
collection can be indexed from scratch, that the index matches the collection, how
the analyzer works, and how Setup A and Setup B differ on the same information
need.

## What the demo covers

1. Starting Solr and indexing the final collection.
2. Verifying the document counts and the parent/child review model.
3. Inspecting the schema and the `textFoldLower` analyzer in Solr Admin.
4. Running the automated index verification.
5. Comparing Setup A and Setup B on one plot need and one review need.

## Prerequisites

| Requirement | Check |
|---|---|
| Docker Desktop / Docker Engine | `docker info` |
| `curl`, `jq` | `command -v curl jq` |
| Python 3.10+ with `requests` | `python3 -c "import requests"` |
| Port 8983 free | `lsof -i :8983` (or `curl localhost:8983`) |
| Repository root as working directory | `pwd` |

The `solr:10` image is normally already present. To pre-pull it:

```bash
docker pull solr:10
```

## 1. Start and index

```bash
bash solr/startup.sh
```

Expected final lines:

```text
Movies:  6104 / 6104
Reviews: 12057 / 12057
Setup complete. Solr Admin UI: http://localhost:8983/solr/
```

The script recreates the `solr_pri` container, so it **wipes any existing index**
and reindexes from `data/final/solr_documents.json`. Do not run it during Q&A if
the demo is already in progress.

## 2. Verify the index

```bash
python3 scripts/verify_index.py
```

Expected summary:

```text
SUMMARY: 25 passed, 0 failed, 2 warning(s)
```

The two warnings are expected: `crew_roles.job` and `cast.order` are
`indexed=false`, but docValues still allow exact-value queries. The script exits
non-zero if a required check fails.

## 3. Admin UI tour

Open `http://localhost:8983/solr/` and select the `movies` core.

| Screen | What to show |
|---|---|
| **Dashboard** | Core health and document counts |
| **Schema** | `plot` as `textFoldLower`; `crew_roles.job` as `string`, `indexed=false`; `movie_id` as `plong` |
| **Analysis** | Field type `textFoldLower`, value `Amélie investigating the Matrix`; show `amelie`, `investigate`, `matrix` and removed stopwords |
| **Query** | `q=plot:astronaut`, `rows=5`, `fl=movie_id,title,year,score` |

Direct links:

```text
http://localhost:8983/solr/#/movies
http://localhost:8983/solr/#/movies/schema
http://localhost:8983/solr/#/movies/analysis
http://localhost:8983/solr/#/movies/query
```

## 4. A/B retrieval demo

```bash
python3 scripts/demo_queries.py
```

The script prints the index counts and the top five results for:

- **Q3** (astronauts stranded away from Earth) under Setup A and Setup B;
- **Q1** (reviews call the comedy clever/witty) under Setup A and Setup B.

It reads the current query definitions from `queries/setup_a/` and
`queries/setup_b/`, so it always reflects the saved configuration. It does not
write run files.

## 5. Manual sanity queries

```bash
S='http://localhost:8983/solr/movies/select'

# total, parents, children
for q in '*:*' 'doc_type:movie' 'doc_type:review'; do
  printf '%-16s ' "$q"
  curl -sG "$S" --data-urlencode "q=$q" --data-urlencode 'rows=0' \
    --data-urlencode 'wt=json' | jq -r '.response.numFound'
done

# one movie
curl -sG "$S" \
  --data-urlencode 'q=movie_id:11' \
  --data-urlencode 'fl=movie_id,title,year,genres,score' \
  --data-urlencode 'rows=5' \
  --data-urlencode 'wt=json' | jq '.response.docs'

# review text -> parent movies
curl -sG "$S" \
  --data-urlencode 'q={!parent which="doc_type:movie" score=max}review_text:clever' \
  --data-urlencode 'fq=genres:comedy' \
  --data-urlencode 'fl=movie_id,title,score' \
  --data-urlencode 'rows=5' \
  --data-urlencode 'wt=json' | jq '.response.docs'

# review children of one movie
curl -sG "$S" \
  --data-urlencode 'q={!child of="doc_type:movie"}id:movie-11' \
  --data-urlencode 'rows=0' \
  --data-urlencode 'wt=json' | jq '.response.numFound'
```

Expected counts: `18161`, `6104`, `12057`; `movie_id:11` is *Star Wars*; the
nested review query returns parent movies; `movie-11` has 7 children.

## Suggested timing (5–7 minutes)

| Time | Step |
|---:|---|
| 0:00–0:30 | Explain the collection: 6,104 movies, 12,057 reviews |
| 0:30–1:30 | `bash solr/startup.sh`; show indexed counts |
| 1:30–2:30 | Admin UI: Schema and Analysis |
| 2:30–3:30 | `python3 scripts/verify_index.py` |
| 3:30–5:30 | `python3 scripts/demo_queries.py` (Q3 and Q1, A vs B) |
| 5:30–6:30 | Explain one result and the parent/child scoring |

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `Cannot connect to the Docker daemon` | Docker not running | start Docker Desktop / `sudo systemctl start docker` |
| `port is already allocated` | another process on 8983 | `docker rm -f solr_pri`; check `lsof -i :8983` |
| `docker: error pulling image` | network/registry issue | use the existing `solr:10` image or retry `docker pull solr:10` |
| `Solr core did not become ready` | container failed or slow start | `docker logs solr_pri`; wait and rerun |
| `404` / unknown core | wrong core name or stale container | use `movies`; rerun `bash solr/startup.sh` |
| `400 undefined field` | typo or field not in schema | check the Schema screen; use the exact field names |
| Query returns 0 | stopword, wrong field, case-sensitive `string`, or too-narrow filter | try another field; use the Analysis screen |
| `Parent query must not match any docs besides parent filter` | wrong `{!child}` direction | put a **parent** query after `{!child of=...}`, e.g. `id:movie-11` |
| `runs/B_*.json` fails to load | saved B runs contain non-UTF-8 bytes | rerun B with UTF-8 decoding before using saved runs |
| Changes not visible | no commit | use `commit=true` (the startup script already does) |

## Teardown

```bash
docker rm -f solr_pri
```

## Screenshot checklist

Capture these for the presentation (`demo-gg`):

1. Core dashboard with 6,104 parents and 12,057 children.
2. Schema browser showing `plot` (`textFoldLower`) or `crew_roles.job`
   (`indexed=false`).
3. Analysis screen with `Amélie investigating the Matrix`.
4. Query screen with `plot:astronaut`.
5. `verify_index.py` summary in the terminal.
6. `demo_queries.py` output for Q3 A vs B.

## Notes for the speaker

- Do not claim that Setup B is better before the qrels are complete; the demo
  shows **configuration differences and candidate results**, not measured
  improvements.
- The index is the artifact being demonstrated; the evaluation numbers belong to
  the evaluation section.
- If time is short, skip the manual `curl` block and run
  `python3 scripts/demo_queries.py` directly.
