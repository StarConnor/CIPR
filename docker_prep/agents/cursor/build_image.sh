#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
docker build -t cli-env:cursor -f "${SCRIPT_DIR}/Dockerfile.cursor" "${SCRIPT_DIR}/.."
