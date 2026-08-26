#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/../.." && pwd)"
DATA_DIR="${REPO_ROOT}/data/ipi_web_dataset/html_pages"

if [[ ! -d "${DATA_DIR}" ]]; then
    echo "Dataset directory not found: ${DATA_DIR}" >&2
    echo "Run 'git submodule update --init --recursive' from the repository root." >&2
    exit 1
fi

cd "${SCRIPT_DIR}"
rm -rf html_pages
cp -r "${DATA_DIR}" html_pages

docker build -t web-server:latest -f Dockerfile .
