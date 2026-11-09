#!/usr/bin/env bash
set -euo pipefail

# Paths are resolved from this script, so run it from any directory.
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"

CORE="movies"
SOLR_URL="http://localhost:8983/solr/$CORE"
SCHEMA_FILE="$SCRIPT_DIR/schema.json"
COLLECTION_FILE="$PROJECT_ROOT/data/final/collection.jsonl"
SOLR_DOCS_FILE="$PROJECT_ROOT/data/final/solr_documents.json"

check_command() {
    command -v "$1" >/dev/null 2>&1 || {
        echo "Required command not found: $1" >&2
        exit 1
    }
}

check_command docker
check_command curl
check_command jq

for file in "$SCHEMA_FILE" "$COLLECTION_FILE" "$SOLR_DOCS_FILE"; do
    if [[ ! -f "$file" ]]; then
        echo "Required file not found: $file" >&2
        echo "Run scripts/build_collection.py first if an output file is missing." >&2
        exit 1
    fi
done

# Start the Solr service and create the core if needed.
docker compose \
    --project-directory "$PROJECT_ROOT" \
    -f "$PROJECT_ROOT/docker-compose.yml" \
    up -d solr

echo "Waiting for Solr core '$CORE'..."
ready=false
for attempt in {1..60}; do
    if curl --fail --silent "$SOLR_URL/select?q=*:*&rows=0" >/dev/null; then
        ready=true
        break
    fi
    sleep 2
done

if [[ "$ready" != true ]]; then
    echo "Solr core did not become ready: $SOLR_URL" >&2
    exit 1
fi

# Apply the schema before indexing. This section is for a fresh core.
echo "Applying schema..."
if ! response=$(curl --silent --show-error --fail-with-body \
    -X POST \
    -H 'Content-Type: application/json' \
    --data-binary "@$SCHEMA_FILE" \
    "$SOLR_URL/schema"); then
    echo "$response" >&2
    exit 1
fi

if [[ "$(jq -r '.responseHeader.status // 1' <<<"$response")" != "0" ]]; then
    echo "$response" | jq .
    exit 1
fi

# Upload parent movies with nested review children.
echo "Uploading movie and review documents..."
if ! response=$(curl --silent --show-error --fail-with-body \
    -X POST \
    -H 'Content-Type: application/json' \
    --data-binary "@$SOLR_DOCS_FILE" \
    "$SOLR_URL/update?commit=true"); then
    echo "$response" >&2
    exit 1
fi

if [[ "$(jq -r '.responseHeader.status // 1' <<<"$response")" != "0" ]]; then
    echo "$response" | jq .
    exit 1
fi

# Verify parent movies and review children separately.
expected_movies=$(wc -l < "$COLLECTION_FILE" | tr -d ' ')
expected_reviews=$(jq -s '[.[].reviews | length] | add // 0' "$COLLECTION_FILE")

count_query() {
    curl --fail --silent --show-error -G "$SOLR_URL/select" \
        --data-urlencode "q=$1" \
        --data-urlencode 'rows=0' \
        --data-urlencode 'wt=json' |
        jq -r '.response.numFound'
}

indexed_movies=$(count_query 'doc_type:movie')
indexed_reviews=$(count_query 'doc_type:review')

echo "Movies:  $indexed_movies / $expected_movies"
echo "Reviews: $indexed_reviews / $expected_reviews"

if [[ "$indexed_movies" != "$expected_movies" ||
      "$indexed_reviews" != "$expected_reviews" ]]; then
    echo "Indexed counts do not match the collection." >&2
    exit 1
fi

echo "Setup complete. Solr Admin UI: http://localhost:8983/solr/"