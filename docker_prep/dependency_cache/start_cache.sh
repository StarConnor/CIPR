#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

IMAGE="${DEPENDENCY_CACHE_IMAGE:-dependency-cache:latest}"
NAME="${DEPENDENCY_CACHE_NAME:-dependency-cache}"
CACHE_DIR="${DEPENDENCY_CACHE_DIR:-$PWD/cache-data}"
HOST_IP="${DEPENDENCY_CACHE_BIND:-0.0.0.0}"
PYTHON_PORT="${DEPENDENCY_CACHE_PYTHON_PORT:-3141}"
APT_PORT="${DEPENDENCY_CACHE_APT_PORT:-3142}"
NPM_PORT="${DEPENDENCY_CACHE_NPM_PORT:-4873}"
GO_PORT="${DEPENDENCY_CACHE_GO_PORT:-3010}"
MAVEN_PORT="${DEPENDENCY_CACHE_MAVEN_PORT:-18082}"
CARGO_PORT="${DEPENDENCY_CACHE_CARGO_PORT:-18083}"
PACKAGIST_PORT="${DEPENDENCY_CACHE_PACKAGIST_PORT:-18084}"
RUBYGEMS_PORT="${DEPENDENCY_CACHE_RUBYGEMS_PORT:-9292}"

check_port_free() {
  local port="$1"
  if command -v ss >/dev/null 2>&1; then
    if ss -ltn "( sport = :$port )" 2>/dev/null | awk 'NR>1 {found=1} END {exit found?0:1}'; then
      echo "[cache] ERROR: host port $port is already in use" >&2
      return 1
    fi
  elif command -v lsof >/dev/null 2>&1; then
    if lsof -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
      echo "[cache] ERROR: host port $port is already in use" >&2
      return 1
    fi
  fi
}

mkdir -p "$CACHE_DIR"

if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
  echo "[cache] image $IMAGE not found; building..."
  ./build_image.sh
fi

if docker ps -a --format '{{.Names}}' | grep -qx "$NAME"; then
  echo "[cache] removing existing container $NAME"
  docker rm -f "$NAME" >/dev/null
fi

echo "[cache] starting $NAME with cache dir $CACHE_DIR"
for port in "$PYTHON_PORT" "$APT_PORT" "$NPM_PORT" "$GO_PORT" "$MAVEN_PORT" "$CARGO_PORT" "$PACKAGIST_PORT" "$RUBYGEMS_PORT"; do
  check_port_free "$port"
done

# The image may have been built on another host with HTTP_PROXY/HTTPS_PROXY
# baked into Dockerfile ENV. Always override those at container start: use the
# current host's proxy env if present, otherwise pass empty values to clear the
# image defaults. A running container's env cannot be changed; restart it.
RUNTIME_HTTP_PROXY="${DEPENDENCY_CACHE_HTTP_PROXY:-${HTTP_PROXY:-${http_proxy:-}}}"
RUNTIME_HTTPS_PROXY="${DEPENDENCY_CACHE_HTTPS_PROXY:-${HTTPS_PROXY:-${https_proxy:-}}}"
RUNTIME_NO_PROXY="${DEPENDENCY_CACHE_NO_PROXY:-${NO_PROXY:-${no_proxy:-localhost,127.0.0.1,::1}}}"

docker run -d \
  --name "$NAME" \
  --restart unless-stopped \
  -v "$CACHE_DIR:/cache" \
  -p "${HOST_IP}:${PYTHON_PORT}:3141" \
  -p "${HOST_IP}:${APT_PORT}:3142" \
  -p "${HOST_IP}:${NPM_PORT}:4873" \
  -p "${HOST_IP}:${GO_PORT}:3010" \
  -p "${HOST_IP}:${MAVEN_PORT}:18082" \
  -p "${HOST_IP}:${CARGO_PORT}:18083" \
  -p "${HOST_IP}:${PACKAGIST_PORT}:18084" \
  -p "${HOST_IP}:${RUBYGEMS_PORT}:9292" \
  -e "http_proxy=${RUNTIME_HTTP_PROXY}" \
  -e "https_proxy=${RUNTIME_HTTPS_PROXY}" \
  -e "HTTP_PROXY=${RUNTIME_HTTP_PROXY}" \
  -e "HTTPS_PROXY=${RUNTIME_HTTPS_PROXY}" \
  -e "no_proxy=${RUNTIME_NO_PROXY}" \
  -e "NO_PROXY=${RUNTIME_NO_PROXY}" \
  "$IMAGE"

echo "[cache] waiting for services to become reachable..."
for spec in \
  "Python/devpi:$PYTHON_PORT:/" \
  "npm/Verdaccio:$NPM_PORT:/-/ping" \
  "Go proxy:$GO_PORT:/golang.org/x/text/@v/list" \
  "Maven proxy:$MAVEN_PORT:/junit/junit/maven-metadata.xml" \
  "Cargo proxy:$CARGO_PORT:/se/rd/serde" \
  "Packagist proxy:$PACKAGIST_PORT:/packages.json" \
  "RubyGems proxy:$RUBYGEMS_PORT:/specs.4.8.gz"; do
  IFS=: read -r label port path <<<"$spec"
  ready=false
  for _ in $(seq 1 30); do
    if curl --noproxy "*" -fsS --connect-timeout 2 --max-time 5 "http://127.0.0.1:${port}${path}" >/dev/null 2>&1; then
      ready=true
      break
    fi
    sleep 1
  done
  if [[ "$ready" != true ]]; then
    echo "[cache] WARN: $label did not become reachable on port $port within timeout" >&2
  fi
done

cat <<INFO
[cache] started.
Endpoints from experiment containers, assuming host IP is 192.168.244.1:
  Python/devpi:        http://192.168.244.1:${PYTHON_PORT}/root/pypi/+simple
  apt-cacher-ng:       http://192.168.244.1:${APT_PORT}
  npm/Verdaccio:       http://192.168.244.1:${NPM_PORT}
  Go GOPROXY:          http://192.168.244.1:${GO_PORT},direct
  Maven Central proxy: http://192.168.244.1:${MAVEN_PORT}/
  Cargo sparse index:  sparse+http://192.168.244.1:${CARGO_PORT}/
  Packagist metadata:  http://192.168.244.1:${PACKAGIST_PORT}
  RubyGems proxy:      http://192.168.244.1:${RUBYGEMS_PORT}

Enable in experiments with:
  export ENABLE_DEPENDENCY_CACHE=true
  export DEPENDENCY_CACHE_HOST=192.168.244.1
INFO
