#!/bin/sh
set -eu

if [ "${MEDRAG_REBUILD:-0}" = "1" ] || [ ! -s "${MEDRAG_DB_PATH:-/app/artifacts/medrag.sqlite3}" ]; then
  python -m medrag.cli build
fi

exec uvicorn medrag.app:app --host "${MEDRAG_API_HOST:-0.0.0.0}" --port "${MEDRAG_API_PORT:-8000}"

