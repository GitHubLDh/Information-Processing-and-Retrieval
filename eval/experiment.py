"""Compare single retrieval changes on the previously judged candidate set.

The scratch core must contain the collection and the auxiliary trigram fields
described in docs/query_specification.md. Only --prepare modifies the scratch core.
"""

import argparse
import re
import sys

import common
import metrics
import requests

sys.path.insert(0, str(common.ROOT / "scripts"))
from solr_client import fetch_solr_results, query_params, to_run_format


MEASURES = ("P@5", "P@10", "AP", "nDCG@10", "Recall@20", "MRR@10")
MISSPELLINGS = {
    "witty": "wity", "heartwarming": "heartwaming", "astronauts": "astronatus",
    "killer": "kiler", "Mafia": "Maifa",
}
# Plot-only, sense-reviewed alternatives from the English WordNet extraction.
EXPANSIONS = {"astronauts": "cosmonaut spaceman", "serial killer": '"serial murderer"'}
EXTRA_STOPS = re.compile(r"\b(?:want|films?|movies?|reviewers?)\b", re.I)


def variant(query, fields=False, phrases=False, stops=False, synonyms=False,
            typo=False, grams=False, rerank=False):
    params = query_params(query, "B" if rerank else "A")
    if fields and query["source"] == "story":
        params["qf"] = "overview^3 plot"
    if phrases:
        params.update(pf2=params["qf"], ps2=1)
    if stops:
        params["text"] = EXTRA_STOPS.sub(" ", params["text"])
    if synonyms and query["source"] == "story":
        for term, alternatives in EXPANSIONS.items():
            if re.search(r"\b" + term + r"\b", query["need"], re.I):
                params["text"] += " " + alternatives
    if typo:
        for correct, wrong in MISSPELLINGS.items():
            params["text"] = params["text"].replace(correct, wrong)
    if grams:
        for field in params["qf"].split():
            name, _, weight = field.partition("^")
            params["qf"] += f" {name}_gram^{0.1 * float(weight or 1):.2f}"
    return params


def prepare_empty_core(uri, collection):
    if collection != "typo_eval":
        raise ValueError("Use a disposable core named typo_eval for preparation")
    check = fetch_solr_results({"q": "*:*", "rows": 0}, uri, collection)
    if check["response"]["numFound"]:
        raise ValueError("Scratch core already contains documents")
    schema = common.load_json(common.ROOT / "solr/schema.json")
    analyzer = schema["add-field-type"][0]["indexAnalyzer"]
    filters = [f for f in analyzer["filters"] if f["class"] != "solr.KStemFilterFactory"]
    filters.append({"class": "solr.NGramFilterFactory", "minGramSize": 3, "maxGramSize": 3})
    schema["add-field-type"].append({"name": "typo_trigram", "class": "solr.TextField",
                                    "analyzer": {"tokenizer": analyzer["tokenizer"], "filters": filters}})
    schema["add-copy-field"] = []
    for field in ("plot", "overview", "review_text"):
        target = field + "_gram"
        schema["add-field"].append({"name": target, "type": "typo_trigram", "indexed": True,
                                    "stored": False, "multiValued": False})
        schema["add-copy-field"].append({"source": field, "dest": [target]})
    core = f"{uri}/{collection}"
    response = requests.post(core + "/schema", json=schema, timeout=60)
    response.raise_for_status()
    with (common.COLLECTION_PATH.parent / "solr_documents.json").open("rb") as docs:
        response = requests.post(core + "/update", params={"commit": "true"}, data=docs,
                                 headers={"Content-Type": "application/json"}, timeout=300)
    response.raise_for_status()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--uri", default="http://127.0.0.1:18983/solr")
    parser.add_argument("--collection", default="typo_eval")
    parser.add_argument("--qrels", default=common.EVAL_DIR / "milestone2/qrels.csv")
    parser.add_argument("--prepare", action="store_true", help="initialize an empty disposable typo_eval core first")
    args = parser.parse_args()
    if args.prepare:
        prepare_empty_core(args.uri, args.collection)
    qrels = common.load_qrels(args.qrels)
    queries = [common.load_json(p) for p in sorted((common.QUERIES_DIR / "setup_a").glob("Q*.json"))]
    print("trial qid P@5 P@10 AP nDCG@10 Recall@20 RR@10")
    for name, flags in TRIALS.items():
        rankings = {}
        for query in queries:
            qid = query["qid"]
            params = variant(query, **flags)
            # Grades never enter scoring. The filter limits this diagnostic to
            # candidates assessed before the experiment, with corpus-wide IDF.
            params["fq"].append("{!terms f=id}" + ",".join("movie-" + i for i in qrels[qid]))
            response = fetch_solr_results(params, args.uri, args.collection)
            rankings[qid] = [{"docid": str(r["movie_id"])} for r in to_run_format(response, qid)]
        results = metrics.evaluate_setup(rankings, qrels)
        for qid, row in results.items():
            print(name, qid, *(metrics.fmt(row[m]) for m in MEASURES))
        print(name, "mean", *(metrics.fmt(metrics.mean_metric(results, m)) for m in MEASURES))


TRIALS = {
    "A": {},
    "fields": {"fields": True},
    "phrases": {"phrases": True},
    "fields+phrases": {"fields": True, "phrases": True},
    "fields+stops": {"fields": True, "stops": True},
    "fields+synonyms": {"fields": True, "synonyms": True},
    "fields+grams": {"fields": True, "grams": True},
    "fields/typos": {"fields": True, "typo": True},
    "fields+grams/typos": {"fields": True, "typo": True, "grams": True},
    "rerank": {"rerank": True},
}

if __name__ == "__main__":
    main()
