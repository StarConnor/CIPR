#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
TARGET="${1:-all}"

configure_build_proxy() {
    export BUILD_HTTP_PROXY="${HTTP_PROXY:-${http_proxy:-}}"
    export BUILD_HTTPS_PROXY="${HTTPS_PROXY:-${https_proxy:-}}"
    if [[ -z "${BUILD_HTTP_PROXY}" || -z "${BUILD_HTTPS_PROXY}" ]]; then
        echo "Set HTTP_PROXY and HTTPS_PROXY before running this script." >&2
        exit 1
    fi
}

configure_build_proxy

render_dockerfile_with_proxy() {
    local source="$1"
    local destination="$2"
    local http_proxy_escaped
    local https_proxy_escaped

    http_proxy_escaped="$(printf '%s' "${BUILD_HTTP_PROXY}" | sed 's/[&|]/\\&/g')"
    https_proxy_escaped="$(printf '%s' "${BUILD_HTTPS_PROXY}" | sed 's/[&|]/\\&/g')"
    sed \
        -e "s|__BUILD_HTTP_PROXY__|${http_proxy_escaped}|g" \
        -e "s|__BUILD_HTTPS_PROXY__|${https_proxy_escaped}|g" \
        "${source}" > "${destination}"
}

build_base() {
    bash "${SCRIPT_DIR}/prepare_build_assets.sh" base

    local public_key_file="${PUBLIC_KEY_FILE:-${SCRIPT_DIR}/base/assets/id_ed25519_1.pub}"
    if [[ ! -f "${public_key_file}" ]]; then
        echo "Missing SSH public key: ${public_key_file}" >&2
        echo "Provide PUBLIC_KEY_FILE or copy your public key to base/assets/id_ed25519_1.pub." >&2
        exit 1
    fi

    test -f "${SCRIPT_DIR}/base/assets/node-v22.21.1-linux-x64.tar.gz" || {
        echo "Missing base/assets/node-v22.21.1-linux-x64.tar.gz" >&2
        exit 1
    }
    test -f "${SCRIPT_DIR}/base/assets/automation_server/requirements-cli.txt" || {
        echo "Missing base/assets/automation_server; run prepare_build_assets.sh." >&2
        exit 1
    }

    local tmp_dockerfile
    tmp_dockerfile="$(mktemp)"
    render_dockerfile_with_proxy "${SCRIPT_DIR}/Dockerfile.base" "${tmp_dockerfile}"

    docker build -t base-env \
        --build-arg USERNAME="${USERNAME:-devuser}" \
        --build-arg PUBLIC_KEY="$(<"${public_key_file}")" \
        -f "${tmp_dockerfile}" "${SCRIPT_DIR}" || {
        local status=$?
        rm -f "${tmp_dockerfile}"
        return "${status}"
    }
    rm -f "${tmp_dockerfile}"
}

build_no_proxy() {
    local public_key_file="${PUBLIC_KEY_FILE:-${SCRIPT_DIR}/base/assets/id_ed25519_1.pub}"
    if [[ ! -f "${public_key_file}" ]]; then
        echo "Missing SSH public key: ${public_key_file}" >&2
        exit 1
    fi

    local tmp_dockerfile
    tmp_dockerfile="$(mktemp)"
    render_dockerfile_with_proxy "${SCRIPT_DIR}/Dockerfile.no_proxy" "${tmp_dockerfile}"

    docker build -t ide-env:no_proxy \
        --build-arg USERNAME="${USERNAME:-devuser}" \
        --build-arg PUBLIC_KEY="$(<"${public_key_file}")" \
        -f "${tmp_dockerfile}" "${SCRIPT_DIR}" || {
        local status=$?
        rm -f "${tmp_dockerfile}"
        return "${status}"
    }
    rm -f "${tmp_dockerfile}"
}

build_agent() {
    local name="$1"
    local dockerfile="$2"
    local tag="$3"
    bash "${SCRIPT_DIR}/prepare_build_assets.sh" "${name}"
    docker build -t "${tag}" -f "${SCRIPT_DIR}/${dockerfile}" "${SCRIPT_DIR}/agents/${name}"
}

case "${TARGET}" in
    base)
        build_base
        ;;
    cli)
        build_base
        docker build -t cli-env -f "${SCRIPT_DIR}/Dockerfile.cli" "${SCRIPT_DIR}"
        ;;
    no_proxy)
        build_no_proxy
        ;;
    cc|claude)
        build_base
        build_agent claude agents/claude/Dockerfile.cc cli-env:cc
        ;;
    codex)
        build_base
        build_agent codex agents/codex/Dockerfile.codex cli-env:codex
        ;;
    opencode)
        build_base
        build_agent opencode agents/opencode/Dockerfile.opencode cli-env:opencode
        ;;
    cline)
        build_base
        build_agent cline agents/cline/Dockerfile.cline cli-env:cline
        ;;
    gemini)
        build_base
        build_agent gemini agents/gemini/Dockerfile.gemini cli-env:gemini
        ;;
    all)
        build_base
        build_agent claude agents/claude/Dockerfile.cc cli-env:cc
        build_agent codex agents/codex/Dockerfile.codex cli-env:codex
        build_agent opencode agents/opencode/Dockerfile.opencode cli-env:opencode
        build_agent cline agents/cline/Dockerfile.cline cli-env:cline
        build_agent gemini agents/gemini/Dockerfile.gemini cli-env:gemini
        ;;
    *)
        echo "Usage: $0 {base|cli|no_proxy|cc|codex|opencode|cline|gemini|all}" >&2
        exit 2
        ;;
esac
