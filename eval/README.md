# Terminal relevance judging

Run these commands from the repository root. The terminal judge reads candidates
from `eval/pool.csv`, shows their evidence from `data/final/collection.jsonl`, and
saves grades to `eval/qrels.csv`.

## Prepare the candidate pool

If `eval/pool.csv` is missing or the retrieval runs have changed, rebuild it first:

```bash
python3 eval/pool.py
```

Pooling requires the Setup A and B run files under `runs/` and the collection at
`data/final/collection.jsonl`. Do not rebuild the pool after judging unless you are
ready to judge any newly added candidates.

## Judge candidates

Start an interactive session for all five queries:

```bash
python3 eval/judge.py --judge "Your Name"
```

To judge only one query:

```bash
python3 eval/judge.py --judge "Your Name" --qid Q1
```

The judge displays each movie's overview, relevant plot/review snippets, and its
ranks in Setup A and B. Enter a relevance grade:

- `2` — highly relevant
- `1` — partially relevant
- `0` — not relevant

Other commands are `s` to skip, `p` to go to the previous candidate, `q` to save
and quit, and `?` to show help. Grades are saved to `eval/qrels.csv` after each
judgment, so you can resume later. Already-graded candidates are skipped by
default.

To revisit existing judgments:

```bash
python3 eval/judge.py --judge "Your Name" --review
```

When reviewing, press Enter to keep a candidate's existing grade, or enter `0`,
`1`, or `2` to replace it. The `judge` column records the name supplied with
`--judge`.
