#!/usr/bin/env bash
set -euo pipefail

# End-to-end smoke test for the Codex CLI image and standalone runner.
# The command builds the image first, then runs the fixed file-listing request.

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
REQUEST_JSON="${REQUEST_JSON:-${PROJECT_ROOT}/standalone/codex_smoke_request.json}"
RUN_NAME="${RUN_NAME:-standalone-codex-smoke}"

cd "${PROJECT_ROOT}"

if [[ ! -f "${REQUEST_JSON}" ]]; then
    echo "Missing standalone request: ${REQUEST_JSON}" >&2
    exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
    echo "docker is required." >&2
    exit 1
fi
if ! command -v uv >/dev/null 2>&1; then
    echo "uv is required to run standalone/run_local_exp.py." >&2
    exit 1
fi
if [[ -z "${CODEX_API_KEY:-}" ]]; then
    echo "Set CODEX_API_KEY before running the Codex smoke test." >&2
    echo "CODEX_BASE_URL may also be required for an OpenAI-compatible endpoint." >&2
    exit 1
fi

if [[ "${SKIP_BUILD:-0}" != "1" ]]; then
    echo "Building base-env and cli-env:codex..."
    bash "${SCRIPT_DIR}/build.sh" codex
else
    echo "SKIP_BUILD=1: using the existing cli-env:codex image."
fi

echo "Running standalone smoke experiment..."
exec uv run python standalone/run_local_exp.py \
    --request-json "${REQUEST_JSON}" \
    --run-name "${RUN_NAME}" \
    --workspace-path "${PROJECT_ROOT}/temp_workspace" \
    --results-path "${PROJECT_ROOT}/results" \
    --verbose
