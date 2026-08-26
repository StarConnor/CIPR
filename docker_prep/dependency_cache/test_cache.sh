#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  bash docker_prep/dependency_cache/test_cache.sh [--docker] [--host HOST]

Examples:
  bash docker_prep/dependency_cache/test_cache.sh
  bash docker_prep/dependency_cache/test_cache.sh --host 192.168.244.1
  bash docker_prep/dependency_cache/test_cache.sh --docker --host 192.168.244.1

Environment:
  DEPENDENCY_CACHE_HOST              default: 192.168.244.1
  DEPENDENCY_CACHE_NAME              default: dependency-cache
  DEPENDENCY_CACHE_TEST_IMAGE        default: base-env
  DEPENDENCY_CACHE_PYTHON_PORT       default: 3141
  DEPENDENCY_CACHE_APT_PORT          default: 3142
  DEPENDENCY_CACHE_NPM_PORT          default: 4873
  DEPENDENCY_CACHE_GO_PORT           default: 3010
  DEPENDENCY_CACHE_MAVEN_PORT        default: 18082
  DEPENDENCY_CACHE_CARGO_PORT        default: 18083
  DEPENDENCY_CACHE_PACKAGIST_PORT    default: 18084
  DEPENDENCY_CACHE_RUBYGEMS_PORT     default: 9292

What it does:
  Sends two requests per ecosystem. For nginx-backed caches it checks
  X-Cache-Status, where the second request should usually become HIT.
  For devpi/Verdaccio/apt-cacher-ng, it checks successful responses and,
  when the cache container is visible, reports file counts under /cache.
USAGE
}

HOST="${DEPENDENCY_CACHE_HOST:-192.168.244.1}"
CACHE_NAME="${DEPENDENCY_CACHE_NAME:-dependency-cache}"
TEST_IMAGE="${DEPENDENCY_CACHE_TEST_IMAGE:-base-env}"
USE_DOCKER=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host)
      HOST="$2"; shift 2 ;;
    --docker)
      USE_DOCKER=true; shift ;;
    -h|--help)
      usage; exit 0 ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 1 ;;
  esac
done

PYTHON_PORT="${DEPENDENCY_CACHE_PYTHON_PORT:-3141}"
APT_PORT="${DEPENDENCY_CACHE_APT_PORT:-3142}"
NPM_PORT="${DEPENDENCY_CACHE_NPM_PORT:-4873}"
GO_PORT="${DEPENDENCY_CACHE_GO_PORT:-3010}"
MAVEN_PORT="${DEPENDENCY_CACHE_MAVEN_PORT:-18082}"
CARGO_PORT="${DEPENDENCY_CACHE_CARGO_PORT:-18083}"
PACKAGIST_PORT="${DEPENDENCY_CACHE_PACKAGIST_PORT:-18084}"
RUBYGEMS_PORT="${DEPENDENCY_CACHE_RUBYGEMS_PORT:-9292}"

if ! command -v curl >/dev/null 2>&1; then
  echo "curl is required on host" >&2
  exit 1
fi

TMPDIR="$(mktemp -d)"
chmod 777 "$TMPDIR"
trap 'rm -rf "$TMPDIR"' EXIT

container_exists=false
if command -v docker >/dev/null 2>&1 && docker ps --format '{{.Names}}' | grep -qx "$CACHE_NAME"; then
  container_exists=true
fi

cache_file_count() {
  local dir="$1"
  if [[ "$container_exists" == true ]]; then
    docker exec "$CACHE_NAME" sh -lc "find '$dir' -type f 2>/dev/null | wc -l" 2>/dev/null | tr -d '[:space:]' || true
  fi
}

run_curl_host() {
  # args are curl args. Bypass ambient HTTP_PROXY/HTTPS_PROXY for cache endpoint tests.
  curl --noproxy "*" "$@"
}

run_curl_host_with_proxy() {
  # args are curl args. Clear ambient proxies but allow explicit -x.
  env -u http_proxy -u https_proxy -u HTTP_PROXY -u HTTPS_PROXY curl "$@"
}

run_curl_docker() {
  # Pass curl args as quoted command through printf %q.
  local cmd="curl --noproxy '*'"
  local arg
  for arg in "$@"; do
    cmd+=" $(printf '%q' "$arg")"
  done
  docker run --rm \
    --entrypoint /bin/bash \
    --add-host host.docker.internal:host-gateway \
    -v "$TMPDIR:$TMPDIR" \
    "$TEST_IMAGE" \
    -lc "$cmd"
}

run_curl() {
  if [[ "$USE_DOCKER" == true ]]; then
    run_curl_docker "$@"
  else
    run_curl_host "$@"
  fi
}

run_curl_with_explicit_proxy() {
  if [[ "$USE_DOCKER" == true ]]; then
    # In this case we want curl to use the explicit apt-cacher-ng proxy (-x), so do not add --noproxy.
    local cmd="env -u http_proxy -u https_proxy -u HTTP_PROXY -u HTTPS_PROXY curl"
    local arg
    for arg in "$@"; do
      cmd+=" $(printf '%q' "$arg")"
    done
    docker run --rm --entrypoint /bin/bash --add-host host.docker.internal:host-gateway -v "$TMPDIR:$TMPDIR" "$TEST_IMAGE" -lc "$cmd"
  else
    run_curl_host_with_proxy "$@"
  fi
}

check_port() {
  local label="$1" port="$2"
  if run_curl -fsS --connect-timeout 3 --max-time 5 "http://$HOST:$port/" >/dev/null 2>&1; then
    echo "[port] OK   $label on $HOST:$port"
  else
    # Some services return non-2xx at /; test raw TCP via bash/curl not portable here, so warn only.
    echo "[port] WARN $label root URL did not return 2xx on $HOST:$port; detailed test will decide"
  fi
}

fetch_twice() {
  local label="$1" cache_dir="$2" url="$3" mode="${4:-direct}"
  local h1="$TMPDIR/${label//[^a-zA-Z0-9]/_}.1.headers"
  local h2="$TMPDIR/${label//[^a-zA-Z0-9]/_}.2.headers"
  local b1="$TMPDIR/${label//[^a-zA-Z0-9]/_}.1.body"
  local b2="$TMPDIR/${label//[^a-zA-Z0-9]/_}.2.body"
  local before after code1 code2 cache1 cache2

  before="$(cache_file_count "$cache_dir")"
  echo
  echo "== $label =="
  echo "URL: $url"
  [[ -n "$before" ]] && echo "cache files before: $before ($cache_dir)"

  set +e
  if [[ "$mode" == "apt-proxy" ]]; then
    run_curl_with_explicit_proxy -fsSL --connect-timeout 10 --max-time 90 -D "$h1" -o "$b1" -x "http://$HOST:$APT_PORT" "$url"
    code1=$?
    run_curl_with_explicit_proxy -fsSL --connect-timeout 10 --max-time 90 -D "$h2" -o "$b2" -x "http://$HOST:$APT_PORT" "$url"
    code2=$?
  else
    run_curl -fsSL --connect-timeout 10 --max-time 90 -D "$h1" -o "$b1" "$url"
    code1=$?
    run_curl -fsSL --connect-timeout 10 --max-time 90 -D "$h2" -o "$b2" "$url"
    code2=$?
  fi
  set -e

  cache1="$(awk 'BEGIN{IGNORECASE=1} /^X-Cache-Status:/ {gsub("\r", ""); print $2}' "$h1" 2>/dev/null | tail -1 || true)"
  cache2="$(awk 'BEGIN{IGNORECASE=1} /^X-Cache-Status:/ {gsub("\r", ""); print $2}' "$h2" 2>/dev/null | tail -1 || true)"
  after="$(cache_file_count "$cache_dir")"

  if [[ "$code1" -eq 0 && "$code2" -eq 0 ]]; then
    echo "request: OK twice"
    [[ -s "$b2" ]] && echo "second response bytes: $(wc -c < "$b2")"
    [[ -n "$cache1$cache2" ]] && echo "X-Cache-Status: first=${cache1:-none} second=${cache2:-none}"
    [[ -n "$after" ]] && echo "cache files after:  $after ($cache_dir)"
    if [[ "$cache2" == "HIT" || "$cache1" == "HIT" ]]; then
      echo "result: OK cache HIT observed"
    elif [[ -n "$cache2" ]]; then
      echo "result: OK response through cache proxy; HIT not observed yet (status=$cache2)"
    else
      echo "result: OK response through cache service"
    fi
    return 0
  fi

  echo "request: FAIL first_exit=$code1 second_exit=$code2"
  echo "hint: if this is the first run, check cache container logs and upstream internet/proxy access"
  return 1
}

if [[ "$USE_DOCKER" == true ]]; then
  if ! command -v docker >/dev/null 2>&1; then
    echo "--docker requires docker command" >&2
    exit 1
  fi
  if ! docker image inspect "$TEST_IMAGE" >/dev/null 2>&1; then
    echo "Docker test image '$TEST_IMAGE' not found. Set DEPENDENCY_CACHE_TEST_IMAGE or omit --docker." >&2
    exit 1
  fi
  echo "Running tests from Docker container image: $TEST_IMAGE"
else
  echo "Running tests from host. Use --docker to test from an experiment-like container."
fi

echo "Cache host: $HOST"
echo "Cache container visible: $container_exists ($CACHE_NAME)"

check_port "Python/devpi" "$PYTHON_PORT"
check_port "apt-cacher-ng" "$APT_PORT"
check_port "npm/Verdaccio" "$NPM_PORT"
check_port "Go proxy" "$GO_PORT"
check_port "Maven proxy" "$MAVEN_PORT"
check_port "Cargo sparse proxy" "$CARGO_PORT"
check_port "Packagist proxy" "$PACKAGIST_PORT"
check_port "RubyGems proxy" "$RUBYGEMS_PORT"

failures=0
fetch_twice "python-devpi" "/cache/devpi" "http://$HOST:$PYTHON_PORT/root/pypi/+simple/pip/" || failures=$((failures+1))
fetch_twice "npm-verdaccio" "/cache/verdaccio/storage" "http://$HOST:$NPM_PORT/lodash" || failures=$((failures+1))
fetch_twice "apt-cacher-ng" "/cache/apt-cacher-ng" "http://archive.ubuntu.com/ubuntu/dists/jammy/Release" "apt-proxy" || failures=$((failures+1))
fetch_twice "go-proxy" "/cache/nginx/go" "http://$HOST:$GO_PORT/golang.org/x/text/@v/list" || failures=$((failures+1))
fetch_twice "maven-central" "/cache/nginx/maven" "http://$HOST:$MAVEN_PORT/junit/junit/maven-metadata.xml" || failures=$((failures+1))
fetch_twice "cargo-sparse" "/cache/nginx/cargo" "http://$HOST:$CARGO_PORT/se/rd/serde" || failures=$((failures+1))
fetch_twice "packagist" "/cache/nginx/packagist" "http://$HOST:$PACKAGIST_PORT/packages.json" || failures=$((failures+1))
fetch_twice "rubygems" "/cache/nginx/rubygems" "http://$HOST:$RUBYGEMS_PORT/specs.4.8.gz" || failures=$((failures+1))

echo
if [[ "$failures" -eq 0 ]]; then
  echo "All dependency cache smoke tests passed."
else
  echo "$failures dependency cache smoke test(s) failed." >&2
  exit 1
fi
