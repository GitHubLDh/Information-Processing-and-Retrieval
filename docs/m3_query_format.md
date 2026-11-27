# Milestone 3 query configuration format

Each `queries/m3/Q*.json` file describes one information need and the **complete**
Solr request used for it. Keeping the parameters in the config (rather than in
code defaults) makes every saved run reproducible and lets each experiment be a
small copy of the baseline with one changed parameter.

```json
{
  "qid": "Q1",
  "need": "I want a comedy whose reviewers praise the subtle humor ...",
  "source": "reviews",
  "filters": ["genres:comedy"],
  "params": { "...": "full Solr select parameters" }
}
```

- `qid`, `need`, `source` and `filters` are unchanged from the M2 query files.
- `params` is sent as a form-encoded POST to `<uri>/<collection>/select`.
- The runner checks that `params.text` equals `need` and that `params.fq` is
  `doc_type:movie` plus the need's `filters`. A mismatch is an error, so the
  frozen M2 runs cannot silently drift.
- Review needs keep the `{!parent ... score=max}` join; story needs use eDisMax
  over `plot` and the M2 top-20 overview rerank.

## Baseline

`queries/m3/` starts with the **M2 Setup B** parameters, the better of the two
frozen M2 systems. It is the starting point for the C4–C7 experiments, not a new
retrieval method yet. `m3_lexical` returns a `SearchResponse` (results, params,
`num_found`) through the shared registry in `search/registry.py`.

## Running

```bash
python3 scripts/run_system.py --system m3_lexical --queries queries/m3 --run-id M3_BASE
```

Useful flags: `--runs` (output directory, default `runs/`), `--uri`,
`--collection`. `--run-id` defaults to the system name.

For each need the runner writes `runs/<run-id>_Q*.json` with the request,
`num_found`, latency in milliseconds, and the ranked results. It also writes
`runs/<run-id>.run` in TREC format, using the shared `search.write_run()` helper,
so P4's `eval/metrics.py` can evaluate it alongside A and B.

Semantic and hybrid systems are registered but not implemented until P2/P3 land;
the runner refuses them with a clear message instead of producing an empty run.
