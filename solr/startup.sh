#!/bin/bash

# Run this from the repository root, after starting the Solr container:
#
#   docker run -p 8983:8983 --name pri_solr -v "${PWD}/data:/data" -d solr:10 solr-precreate movies
#
# Then run this script to (re)apply the schema and index the collection:
#
#   ./solr/startup.sh

# Schema definition via API. solr/schema.json is currently empty (schemaless
# mode) -- fill in add-field-type / add-field entries here as the schema gets
# designed for Milestone 2.
curl -X POST -H 'Content-type:application/json' \
    --data-binary "@./solr/schema.json" \
    http://localhost:8983/solr/movies/schema

# Populate the collection using the path mounted inside the container.
docker exec -it pri_solr solr post -c movies /data/final/collection.jsonl
