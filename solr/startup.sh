#!/bin/bash

# Run this from the repository root, after starting the Solr container (no
# volume mount needed -- indexing goes through the HTTP API from the host):
#
#   docker run -p 8983:8983 --name pri_solr -d solr:10 solr-precreate movies
#
# Then run this script to (re)apply the schema and index the collection:
#
#   ./solr/startup.sh
#
# Requires `jq` (sudo apt install jq / brew install jq).

# Schema definition via API. See solr/schema.json for field types/fields.
curl -X POST -H 'Content-type:application/json' \
    --data-binary "@./solr/schema.json" \
    http://localhost:8983/solr/movies/schema

# Solr's uniqueKey field is "id", but our documents only have "movie_id", and
# Solr won't let a copyField target the uniqueKey. So we inject a stable "id"
# per document (movie-<movie_id>) on the way in -- this also makes
# re-indexing idempotent (same id = update in place, not a duplicate).
jq -c '. + {id: ("movie-" + (.movie_id|tostring))}' data/final/collection.jsonl \
    | curl -X POST -H 'Content-type:application/json' \
        --data-binary @- \
        "http://localhost:8983/solr/movies/update/json/docs?commit=true"
