#!/usr/bin/env bash
set -euo pipefail

# Validate and, where a public package URL is known, prepare the files used by
# Docker builds. Secrets and local credentials are intentionally never copied.

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
BASE_ASSETS_DIR="${SCRIPT_DIR}/base/assets"
AGENTS_DIR="${SCRIPT_DIR}/agents"
TARGET="${1:-base}"

require_file() {
    local path="$1"
    local message="$2"
    if [[ ! -f "${path}" ]]; then
        echo "Missing ${path}" >&2
        echo "${message}" >&2
        exit 1
    fi
}

require_file "${BASE_ASSETS_DIR}/node-v22.21.1-linux-x64.tar.gz" \
    "Provide the Node.js archive in docker_prep/base/assets/."
require_file "${BASE_ASSETS_DIR}/automation_server/requirements-cli.txt" \
    "Copy automation_server_appium/automation_server to docker_prep/base/assets/automation_server/."

case "${TARGET}" in
    base)
        require_file "${PUBLIC_KEY_FILE:-${BASE_ASSETS_DIR}/id_ed25519_1.pub}" \
            "Provide your SSH public key through PUBLIC_KEY_FILE or base/assets/id_ed25519_1.pub."
        ;;
    cc|claude)
        require_file "${AGENTS_DIR}/claude/.claude.json" \
            "Copy your own Claude Code .claude.json into docker_prep/agents/claude/."
        require_file "${AGENTS_DIR}/claude/.claude.json.backup" \
            "Copy your own Claude Code .claude.json.backup into docker_prep/agents/claude/."
        require_file "${AGENTS_DIR}/claude/claude-code.tgz" \
            "Place the Claude Code package in docker_prep/agents/claude/claude-code.tgz."
        ;;
    codex)
        if [[ ! -f "${AGENTS_DIR}/codex/codex.tgz" ]]; then
            mkdir -p "${AGENTS_DIR}/codex"
            curl -fL "https://registry.npmjs.org/@openai/codex/-/codex-0.130.0.tgz" \
                -o "${AGENTS_DIR}/codex/codex.tgz"
        fi
        ;;
    opencode)
        if [[ ! -f "${AGENTS_DIR}/opencode/opencode.tgz" ]]; then
            mkdir -p "${AGENTS_DIR}/opencode"
            (cd "${AGENTS_DIR}/opencode" && npm pack opencode-ai@1.1.44 >/dev/null)
            mv "${AGENTS_DIR}/opencode/opencode-ai-1.1.44.tgz" "${AGENTS_DIR}/opencode/opencode.tgz"
        fi
        ;;
    cline)
        require_file "${AGENTS_DIR}/cline/cline.tgz" \
            "Place the Cline package in docker_prep/agents/cline/cline.tgz."
        ;;
    gemini)
        require_file "${AGENTS_DIR}/gemini/gemini.tgz" \
            "Place the Gemini CLI package in docker_prep/agents/gemini/gemini.tgz."
        ;;
    *)
        echo "Usage: $0 {base|cc|codex|opencode|cline|gemini}" >&2
        exit 2
        ;;
esac

echo "Build assets are ready for: ${TARGET}"
