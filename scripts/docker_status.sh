#!/bin/sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
docker compose -f "$ROOT_DIR/docker-compose.yml" ps
printf 'api: '
docker compose -f "$ROOT_DIR/docker-compose.yml" port api 8000 || true
printf 'web: '
docker compose -f "$ROOT_DIR/docker-compose.yml" port web 80 || true

