#!/bin/bash
# Universal Agent Startup Script with mitmproxy Network Tracing
# Supports multiple agent types through environment variables
#
# Environment Variables:
#   AGENT_TYPE          - Agent identifier (e.g., "claude-code", "cline", "copilot")
#   ENABLE_MITM         - Enable mitmproxy network capture (default: true)
#   MITM_PORT           - Port for mitmproxy (default: 8080)
#   UPSTREAM_PROXY      - Upstream proxy URL (optional)
#   LOG_LEVEL           - Logging level (default: INFO)

set -e

# Configuration with defaults
AGENT_TYPE=${AGENT_TYPE:-"generic"}
ENABLE_MITM=${ENABLE_MITM:-"true"}
MITM_PORT=${MITM_PORT:-7999}
LOG_LEVEL=${LOG_LEVEL:-"INFO"}

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_section() {
    echo -e "${BLUE}[${1}]${NC} $2"
}

# Cleanup logs
log_section "INIT" "Cleaning up old logs..."
rm -f /tmp/network_trace.jsonl /tmp/${AGENT_TYPE}.log
touch /tmp/network_trace.jsonl /tmp/${AGENT_TYPE}.log
chmod 666 /tmp/network_trace.jsonl /tmp/${AGENT_TYPE}.log

log_info "Agent Type: $AGENT_TYPE"
log_info "Network Capture: $ENABLE_MITM"
log_info "Log Level: $LOG_LEVEL"

# --- START MITM PROXY (if enabled) ---
if [ "$ENABLE_MITM" = "true" ]; then
    log_section "MITM" "Starting mitmproxy on port $MITM_PORT..."
    
    # Determine upstream proxy
    EFFECTIVE_UPSTREAM_PROXY="${UPSTREAM_PROXY:-$HTTPS_PROXY}"
    
    # Avoid circular proxy reference
    if [ "$EFFECTIVE_UPSTREAM_PROXY" = "http://127.0.0.1:$MITM_PORT" ] || \
       [ "$EFFECTIVE_UPSTREAM_PROXY" = "http://localhost:$MITM_PORT" ]; then
        EFFECTIVE_UPSTREAM_PROXY=""
    fi
    build_ignore_hosts() {
        # Ignore everything except the target hosts.
        # Strategy: do not ignore the target domains; ignore everything else
        # (match with .+ as a catch-all, then exclude the targets).
        # mitmproxy's ignore_hosts is a regex; matched traffic is tunneled without decryption.

        local targets="${MITM_TARGET_HOSTS:-}"
        if [ -z "$targets" ]; then
            echo ""
            return
        fi

        # Convert the target domains into a "negative" regex — i.e. ignore anything not in the target list.
        # Simplest approach: generate it with a Python helper.
        python3 - <<PYEOF
import os, re
targets = [t.strip() for t in "${targets}".split(",") if t.strip()]
# Build the regex for each target (matches the host itself and its subdomains)
patterns = [re.escape(t).replace(r"\.","[.]") for t in targets]
# ignore_hosts matches mean traffic is not decrypted, so we ignore "everything that is not a target"
# using a negative lookahead
combined = "|".join(f"({p})" for p in patterns)
print(f"^(?!.*({combined})).*$")
PYEOF
    }

    IGNORE_PATTERN=$(build_ignore_hosts)
    log_info "Generated mitmproxy ignore pattern: $IGNORE_PATTERN"
    
    if [ -n "$EFFECTIVE_UPSTREAM_PROXY" ]; then
        if [ -n "$IGNORE_PATTERN" ]; then
            nohup mitmdump -p $MITM_PORT --mode upstream:$EFFECTIVE_UPSTREAM_PROXY \
                --ignore-hosts "$IGNORE_PATTERN" \
                -s /opt/mitm_logger.py -q > /tmp/mitmdump.log 2>&1 &
        else
            nohup mitmdump -p $MITM_PORT --mode upstream:$EFFECTIVE_UPSTREAM_PROXY \
                -s /opt/mitm_logger.py -q > /tmp/mitmdump.log 2>&1 &
        fi
    else
        if [ -n "$IGNORE_PATTERN" ]; then
            nohup mitmdump -p $MITM_PORT \
                --ignore-hosts "$IGNORE_PATTERN" \
                -s /opt/mitm_logger.py -q > /tmp/mitmdump.log 2>&1 &
        else
            nohup mitmdump -p $MITM_PORT -s /opt/mitm_logger.py -q \
                > /tmp/mitmdump.log 2>&1 &
        fi
    fi
    
    MITM_PID=$!
    log_info "mitmproxy started with PID $MITM_PID"
    
    # Wait for mitmproxy to initialize
    log_info "Waiting for mitmproxy to become ready..."
    MITM_READY=0
    for i in {1..30}; do
        if [ -f ~/.mitmproxy/mitmproxy-ca-cert.pem ] && netstat -tln 2>/dev/null | grep -q ":$MITM_PORT "; then
            log_info "mitmproxy is ready (certificates generated, port listening)"
            MITM_READY=1
            break
        fi
        sleep 0.5
    done
    
    if [ $MITM_READY -eq 0 ]; then
        log_error "mitmproxy failed to become ready. Check /tmp/mitmdump.log:"
        cat /tmp/mitmdump.log
        exit 1
    fi
    
    # Verify mitmproxy is still running
    if ! kill -0 $MITM_PID 2>/dev/null; then
        log_error "mitmproxy process died. Check /tmp/mitmdump.log:"
        cat /tmp/mitmdump.log
        exit 1
    fi
    
    # --- CONFIGURE TRUST ---
    log_section "TRUST" "Configuring certificate trust..."
    mkdir -p /home/devuser/.mitmproxy
    
    if [ -f ~/.mitmproxy/mitmproxy-ca-cert.pem ]; then
        if [ -f /home/devuser/.mitmproxy/mitmproxy-ca-cert.pem ]; then
            log_info "CA certificate already exists in /home/devuser/.mitmproxy/"
        else
            cp ~/.mitmproxy/mitmproxy-ca-cert.pem /home/devuser/.mitmproxy/
        fi
        
        # Add to system trust store
        if command -v update-ca-certificates > /dev/null; then
            sudo cp ~/.mitmproxy/mitmproxy-ca-cert.pem /usr/local/share/ca-certificates/mitmproxy-ca.crt
            sudo update-ca-certificates > /dev/null 2>&1
        fi
        
        log_info "mitmproxy CA certificate installed"
    else
        log_warn "mitmproxy CA certificate not found"
    fi
    
    # Configure proxy environment
    export http_proxy=http://127.0.0.1:$MITM_PORT
    export https_proxy=http://127.0.0.1:$MITM_PORT
    export HTTP_PROXY=http://127.0.0.1:$MITM_PORT
    export HTTPS_PROXY=http://127.0.0.1:$MITM_PORT

    sudo sh -c 'echo "http_proxy=\"$http_proxy\"" >> /etc/environment'
    sudo sh -c 'echo "https_proxy=\"$https_proxy\"" >> /etc/environment'
    sudo sh -c 'echo "HTTP_PROXY=\"$HTTP_PROXY\"" >> /etc/environment'
    sudo sh -c 'echo "HTTPS_PROXY=\"$HTTPS_PROXY\"" >> /etc/environment'
    
    # Trust the mitmproxy certificate for Node.js
    export NODE_EXTRA_CA_CERTS=/home/devuser/.mitmproxy/mitmproxy-ca-cert.pem
    export SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt
    export REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
    
    # Note: NODE_TLS_REJECT_UNAUTHORIZED=0 should only be used for debugging
    # It's better to properly trust the certificate
    # export NODE_TLS_REJECT_UNAUTHORIZED=0
    
    log_section "PROXY" "Proxy configuration:"
    log_info "  http_proxy=$http_proxy"
    log_info "  https_proxy=$https_proxy"
    log_info "  NODE_EXTRA_CA_CERTS=$NODE_EXTRA_CA_CERTS"
    
    # Verify network trace file is writable
    log_section "CHECK" "Testing network trace file..."
    if echo '{"test":"init","timestamp":"'"$(date -Iseconds)"'","agent":"'"$AGENT_TYPE"'"}' >> /tmp/network_trace.jsonl; then
        log_info "Network trace file is writable"
        ls -lh /tmp/network_trace.jsonl
    else
        log_error "Cannot write to network trace file"
    fi
else
    log_warn "Network capture disabled (ENABLE_MITM=false)"
fi

# --- START EBPF TRACING ---
log_section AUTOMATION SERVER ---
log_section "START" "Starting automation server..."
AUTOMATION_PYTHON="/opt/mitmproxy-env/bin/python3"
log_info "Command: ${AUTOMATION_PYTHON} -m automation_server"
log_info "Working directory: $(pwd)"
log_info "User: $(whoami)"
log_info "Logging to: /tmp/${AGENT_TYPE}.log"

# Export agent type for the automation server
export AGENT_TYPE

exec "$AUTOMATION_PYTHON" -m automation_server 2>&1 | tee -a /tmp/${AGENT_TYPE}.log