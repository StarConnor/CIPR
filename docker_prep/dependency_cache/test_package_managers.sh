#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  bash docker_prep/dependency_cache/test_package_managers.sh [--host HOST] [--languages LIST] [--rounds N] [--no-pull]

Examples:
  bash docker_prep/dependency_cache/test_package_managers.sh --host 192.168.244.1
  bash docker_prep/dependency_cache/test_package_managers.sh --languages python,npm,ruby --rounds 2

Purpose:
  Run real package-manager commands from fresh Docker containers against the
  dependency cache. This complements test_cache.sh, which is mostly an HTTP
  endpoint/cache-header smoke test.

Languages/ecosystems:
  python,npm,apt,go,maven,cargo,composer,rubygems

Environment overrides:
  DEPENDENCY_CACHE_HOST              default: 192.168.244.1
  DEPENDENCY_CACHE_NAME              default: dependency-cache
  DEPENDENCY_CACHE_PYTHON_PORT       default: 3141
  DEPENDENCY_CACHE_APT_PORT          default: 3142
  DEPENDENCY_CACHE_NPM_PORT          default: 4873
  DEPENDENCY_CACHE_GO_PORT           default: 3010
  DEPENDENCY_CACHE_MAVEN_PORT        default: 18082
  DEPENDENCY_CACHE_CARGO_PORT        default: 18083
  DEPENDENCY_CACHE_PACKAGIST_PORT    default: 18084
  DEPENDENCY_CACHE_RUBYGEMS_PORT     default: 9292
USAGE
}

HOST="${DEPENDENCY_CACHE_HOST:-192.168.244.1}"
CACHE_NAME="${DEPENDENCY_CACHE_NAME:-dependency-cache}"
LANGUAGES="python,npm,apt,go,maven,cargo,composer,rubygems"
ROUNDS=2
PULL=true

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host) HOST="$2"; shift 2 ;;
    --languages) LANGUAGES="$2"; shift 2 ;;
    --rounds) ROUNDS="$2"; shift 2 ;;
    --no-pull) PULL=false; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 1 ;;
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

if ! command -v docker >/dev/null 2>&1; then
  echo "docker command not found" >&2
  exit 1
fi

if ! docker ps --format '{{.Names}}' | grep -qx "$CACHE_NAME"; then
  echo "Cache container '$CACHE_NAME' is not running" >&2
  exit 1
fi

TMPROOT="$(mktemp -d)"
chmod 777 "$TMPROOT"
trap 'rm -rf "$TMPROOT"' EXIT

base_docker_args=(
  --rm
  --add-host host.docker.internal:host-gateway
  -e "NO_PROXY=$HOST,host.docker.internal,localhost,127.0.0.1"
  -e "no_proxy=$HOST,host.docker.internal,localhost,127.0.0.1"
  -e "DEPENDENCY_CACHE_HOST=$HOST"
)

pull_image() {
  local image="$1"
  if docker image inspect "$image" >/dev/null 2>&1; then
    return 0
  fi
  if [[ "$PULL" == true ]]; then
    echo "[pull] $image"
    docker pull "$image" >/dev/null
  else
    echo "Image missing and --no-pull set: $image" >&2
    return 1
  fi
}

cache_count() {
  local dir="$1"
  docker exec "$CACHE_NAME" sh -lc "find '$dir' -type f 2>/dev/null | wc -l" 2>/dev/null | tr -d '[:space:]' || true
}

run_case() {
  local name="$1" image="$2" cache_dir="$3" script="$4"
  local before after round
  echo
  echo "===== $name ====="
  echo "image: $image"
  before="$(cache_count "$cache_dir")"
  [[ -n "$before" ]] && echo "cache files before: $before ($cache_dir)"
  pull_image "$image"

  for round in $(seq 1 "$ROUNDS"); do
    echo "--- round $round/$ROUNDS: real package-manager install with fresh container/home ---"
    local log_file="$TMPROOT/${name//[^a-zA-Z0-9]/_}.${round}.log"
    set +e
    docker run "${base_docker_args[@]}" \
      -v "$TMPROOT:$TMPROOT" \
      "$image" \
      bash -c "set -euo pipefail
export HOME=/tmp/pm-home
rm -rf /tmp/pm-home /tmp/pm-work
mkdir -p /tmp/pm-home /tmp/pm-work
cd /tmp/pm-work
$script" 2>&1 | tee "$log_file"
    local status="${PIPESTATUS[0]}"
    set -e
    if [[ "$status" -ne 0 ]]; then
      after="$(cache_count "$cache_dir")"
      [[ -n "$after" ]] && echo "cache files after failed round: $after ($cache_dir)"
      echo "result: FAIL real $name package-manager command failed in round $round with exit $status" >&2
      echo "log: $log_file" >&2
      return "$status"
    fi
  done

  after="$(cache_count "$cache_dir")"
  [[ -n "$after" ]] && echo "cache files after:  $after ($cache_dir)"
  if [[ -n "$before" && -n "$after" && "$after" -gt "$before" ]]; then
    echo "cache files added:  $((after - before))"
  fi
  echo "result: OK real $name package-manager command completed via cache configuration"
}

case_python() {
  run_case "python/pip" "dockerhub.zjusct.io/library/python:3.12-slim-bookworm" "/cache/devpi" "
python -m pip install --disable-pip-version-check --no-cache-dir \\
  --index-url http://$HOST:$PYTHON_PORT/root/pypi/+simple \\
  --trusted-host $HOST 'attrs==23.2.0'
python - <<'PY'
import attrs
print('attrs', attrs.__version__)
PY
"
}

case_npm() {
  run_case "npm" "dockerhub.zjusct.io/library/node:22-bookworm-slim" "/cache/verdaccio/storage" "
npm config set registry http://$HOST:$NPM_PORT/
npm config set strict-ssl false
npm config set cache /tmp/pm-home/.npm
npm init -y >/dev/null
npm install is-number@7.0.0 --prefer-online --no-audit --fund=false
node -e \"console.log('is-number', require('is-number')(42))\"
"
}

case_apt() {
  run_case "apt" "dockerhub.zjusct.io/library/ubuntu:22.04" "/cache/apt-cacher-ng" "
export DEBIAN_FRONTEND=noninteractive
printf 'Acquire::http::Proxy \"http://$HOST:$APT_PORT\";\nAcquire::https::Proxy \"false\";\n' >/etc/apt/apt.conf.d/01dependency-cache
apt-get update
apt-get install -y --no-install-recommends sl
/usr/games/sl -V >/dev/null 2>&1 || true
"
}

case_go() {
  run_case "go" "golang:1.22-bookworm" "/cache/nginx/go" "
export PATH=/usr/local/go/bin:$PATH
command -v go
export GOPROXY=http://$HOST:$GO_PORT,direct
export GOMODCACHE=/tmp/pm-home/go/pkg/mod
export GOCACHE=/tmp/pm-home/.cache/go-build
go mod init cachetest.example
go get golang.org/x/text@v0.14.0
go list -m golang.org/x/text
"
}

case_maven() {
  run_case "maven" "maven:3.9-eclipse-temurin-21" "/cache/nginx/maven" "
mkdir -p /tmp/pm-home/.m2
cat >/tmp/pm-home/.m2/settings.xml <<XML
<settings><mirrors><mirror><id>redteam-cache</id><mirrorOf>central</mirrorOf><url>http://$HOST:$MAVEN_PORT/</url></mirror></mirrors></settings>
XML
cat >pom.xml <<XML
<project xmlns=\"http://maven.apache.org/POM/4.0.0\" xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\" xsi:schemaLocation=\"http://maven.apache.org/POM/4.0.0 https://maven.apache.org/xsd/maven-4.0.0.xsd\"><modelVersion>4.0.0</modelVersion><groupId>cachetest</groupId><artifactId>cachetest</artifactId><version>1.0</version><dependencies><dependency><groupId>junit</groupId><artifactId>junit</artifactId><version>4.13.2</version><scope>test</scope></dependency></dependencies></project>
XML
mvn -q -s /tmp/pm-home/.m2/settings.xml -Dmaven.repo.local=/tmp/pm-home/.m2/repository dependency:go-offline
"
}

case_cargo() {
  run_case "cargo" "rust:1-bookworm" "/cache/nginx/cargo" "
export PATH=/usr/local/cargo/bin:$PATH
command -v cargo
export CARGO_HOME=/tmp/pm-home/.cargo
mkdir -p \$CARGO_HOME
cat >\$CARGO_HOME/config.toml <<TOML
[source.crates-io]
replace-with = \"redteam-cache\"
[source.redteam-cache]
registry = \"sparse+http://$HOST:$CARGO_PORT/\"
[http]
check-revoke = false
TOML
cargo new --bin cachetest >/dev/null
cd cachetest
cargo add serde@1.0.197
cargo fetch
"
}

case_composer() {
  run_case "composer" "composer:2" "/cache/nginx/packagist" "
composer config -g secure-http false
composer config -g repo.packagist composer http://$HOST:$PACKAGIST_PORT
composer init --no-interaction --name cachetest/cachetest
composer require psr/log:3.0.0 --no-interaction --no-progress
php -r \"require 'vendor/autoload.php'; echo Psr\\\\Log\\\\LogLevel::INFO, PHP_EOL;\"
"
}

case_rubygems() {
  run_case "rubygems" "ruby:3.3-bookworm" "/cache/nginx/rubygems" "
export GEM_HOME=/tmp/pm-home/.gem
export GEM_PATH=\$GEM_HOME
export BUNDLE_USER_HOME=/tmp/pm-home/.bundle
export BUNDLE_PATH=/tmp/pm-home/.bundle/vendor
export BUNDLE_CACHE_PATH=/tmp/pm-home/.bundle/cache
gem sources --clear-all --add http://$HOST:$RUBYGEMS_PORT/
gem install i18n -v 1.14.7 --no-document --source http://$HOST:$RUBYGEMS_PORT/ --clear-sources
ruby -ri18n -e \"puts I18n::VERSION\"
"
}

failures=0
IFS=',' read -r -a requested <<< "${LANGUAGES//;/,}"
for raw in "${requested[@]}"; do
  lang="$(echo "$raw" | tr '[:upper:]' '[:lower:]' | xargs)"
  case "$lang" in
    python|pip) case_python || failures=$((failures+1)) ;;
    npm|node|javascript|typescript) case_npm || failures=$((failures+1)) ;;
    apt|ubuntu) case_apt || failures=$((failures+1)) ;;
    go|golang) case_go || failures=$((failures+1)) ;;
    maven|java) case_maven || failures=$((failures+1)) ;;
    cargo|rust) case_cargo || failures=$((failures+1)) ;;
    composer|php|packagist) case_composer || failures=$((failures+1)) ;;
    ruby|rubygems|bundler) case_rubygems || failures=$((failures+1)) ;;
    *) echo "Unsupported language/ecosystem: $raw" >&2; failures=$((failures+1)) ;;
  esac
done

echo
if [[ "$failures" -eq 0 ]]; then
  echo "All real package-manager cache tests passed."
else
  echo "$failures real package-manager cache test(s) failed." >&2
  exit 1
fi
