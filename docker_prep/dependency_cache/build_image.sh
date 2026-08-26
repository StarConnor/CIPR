#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
docker build -t dependency-cache:latest \
  --build-arg HTTP_PROXY="${HTTP_PROXY:-${http_proxy:-}}" \
  --build-arg HTTPS_PROXY="${HTTPS_PROXY:-${https_proxy:-}}" \
  --build-arg NO_PROXY="${NO_PROXY:-${no_proxy:-}}" \
  .
