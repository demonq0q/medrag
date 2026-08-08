#!/bin/sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
CADDY_CONFIG=${CADDY_CONFIG:-/etc/caddy/Caddyfile}
COMPOSE_FILE=${COMPOSE_FILE:-"$ROOT_DIR/docker-compose.yml"}

API_IMAGE=${MEDRAG_API_IMAGE:-medrag-api:local}
WEB_IMAGE=${MEDRAG_WEB_IMAGE:-medrag-web:local}

if [ "${MEDRAG_SKIP_BUILD:-0}" = "1" ]; then
  docker compose -f "$COMPOSE_FILE" up -d
else
  BUILDX_VERSION=$(docker buildx version 2>/dev/null | sed -n 's/.*v\([0-9][0-9.]*\).*/\1/p' | head -n 1 || true)
  MIN_BUILDX_VERSION=$(printf '%s\n' "0.17.0" "$BUILDX_VERSION" | sort -V | head -n 1)
  if [ -n "$BUILDX_VERSION" ] && [ "$MIN_BUILDX_VERSION" = "0.17.0" ]; then
    docker compose -f "$COMPOSE_FILE" up -d --build
  else
    echo "当前 Buildx ${BUILDX_VERSION:-不可用}，使用兼容旧版 Docker 的 legacy builder" >&2
    DOCKER_BUILDKIT=0 docker build -t "$API_IMAGE" -f "$ROOT_DIR/Dockerfile" "$ROOT_DIR"
    DOCKER_BUILDKIT=0 docker build -t "$WEB_IMAGE" -f "$ROOT_DIR/frontend/Dockerfile" "$ROOT_DIR/frontend"
    docker compose -f "$COMPOSE_FILE" up -d
  fi
fi
WEB_ENDPOINT=$(docker compose -f "$COMPOSE_FILE" port web 80)
WEB_PORT=${WEB_ENDPOINT##*:}
case "$WEB_PORT" in
  *[!0-9]* | "") echo "无法解析 web 随机端口: $WEB_ENDPOINT" >&2; exit 1 ;;
esac

TMP_CONFIG=$(mktemp)
BACKUP_CONFIG="${CADDY_CONFIG}.bak.$(date +%Y%m%d%H%M%S)"
trap 'rm -f "$TMP_CONFIG"' EXIT
cp "$CADDY_CONFIG" "$BACKUP_CONFIG"

awk -v port="$WEB_PORT" '
  BEGIN { skip = 0 }
  /^# BEGIN MEDRAG XIAOHE/ { skip = 1; next }
  /^# END MEDRAG XIAOHE/ { skip = 0; next }
  !skip { print }
  END {
    print ""
    print "# BEGIN MEDRAG XIAOHE"
    print "medrag.986889.xyz {"
    print "    encode gzip zstd"
    print "    reverse_proxy 127.0.0.1:" port
    print "}"
    print "# END MEDRAG XIAOHE"
  }
' "$CADDY_CONFIG" > "$TMP_CONFIG"

caddy validate --config "$TMP_CONFIG" --adapter caddyfile
install -o root -g root -m 0644 "$TMP_CONFIG" "$CADDY_CONFIG"
caddy reload --config "$CADDY_CONFIG" --adapter caddyfile

echo "小荷已通过 Caddy 反代到 medrag.986889.xyz"
echo "web container localhost port: $WEB_PORT"
echo "Caddy backup: $BACKUP_CONFIG"
