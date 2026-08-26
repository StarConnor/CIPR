#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
docker build -t cli-env:trae -f "${SCRIPT_DIR}/Dockerfile.trae" "${SCRIPT_DIR}/.."
