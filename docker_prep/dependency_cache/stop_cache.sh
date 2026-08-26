#!/usr/bin/env bash
set -euo pipefail
NAME="${DEPENDENCY_CACHE_NAME:-dependency-cache}"
docker rm -f "$NAME"
