#!/bin/bash
set -e

# --- 1. SETUP NETWORK (Must be done as ROOT) ---
HTML_IP=${HTML_IP:-"192.168.244.1"}
HTML_PORT=${HTML_PORT:-"8084"}
HTML_DOMAIN=${HTML_DOMAIN:-"target.com"}

ATTACKER_IP=${ATTACKER_IP:-"192.168.244.1"}
ATTACKER_PORT=${ATTACKER_PORT:-"8085"}
ATTACKER_DOMAIN=${ATTACKER_DOMAIN:-"security.local"}

START_SSH=${START_SSH:-"false"}
SSH_PORT=${SSH_PORT:-2222}

echo "[Entrypoint] Root setup: Mapping domains"
echo "[Entrypoint]   $HTML_DOMAIN -> 127.0.0.1 -> $HTML_IP:$HTML_PORT (HTTPS)"
echo "[Entrypoint]   $ATTACKER_DOMAIN -> 127.0.0.1 -> $ATTACKER_IP:$ATTACKER_PORT (HTTPS)"

# Modifying /etc/hosts (Requires Root)
echo "127.0.0.1 $HTML_DOMAIN" >> /etc/hosts
echo "127.0.0.1 $ATTACKER_DOMAIN" >> /etc/hosts

# Setup SSL for HTML_DOMAIN (Requires Root)
if [ ! -f "/etc/nginx/ssl/self-signed.crt" ]; then
    mkdir -p /etc/nginx/ssl
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout /etc/nginx/ssl/self-signed.key \
        -out /etc/nginx/ssl/self-signed.crt \
        -subj "/C=US/ST=State/L=City/O=Organization/CN=$HTML_DOMAIN" \
        -addext "subjectAltName=DNS:$HTML_DOMAIN"
fi

# Setup SSL for ATTACKER_DOMAIN (Requires Root)
if [ ! -f "/etc/nginx/ssl/attacker-self-signed.crt" ]; then
    mkdir -p /etc/nginx/ssl
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout /etc/nginx/ssl/attacker-self-signed.key \
        -out /etc/nginx/ssl/attacker-self-signed.crt \
        -subj "/C=US/ST=State/L=City/O=Organization/CN=$ATTACKER_DOMAIN" \
        -addext "subjectAltName=DNS:$ATTACKER_DOMAIN"
fi

cp /etc/nginx/ssl/self-signed.crt /usr/local/share/ca-certificates/mock-ca.crt
cp /etc/nginx/ssl/attacker-self-signed.crt /usr/local/share/ca-certificates/attacker-ca.crt
update-ca-certificates > /dev/null 2>&1

# Generate Nginx Config for both domains
cat <<EOF > /etc/nginx/sites-available/default
# HTML_DOMAIN with HTTPS
server {
    listen 443 ssl;
    server_name $HTML_DOMAIN;
    ssl_certificate /etc/nginx/ssl/self-signed.crt;
    ssl_certificate_key /etc/nginx/ssl/self-signed.key;
    location / {
        proxy_pass http://$HTML_IP:$HTML_PORT;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
    }
}

# ATTACKER_DOMAIN with HTTPS
server {
    listen 443 ssl;
    server_name $ATTACKER_DOMAIN;
    ssl_certificate /etc/nginx/ssl/attacker-self-signed.crt;
    ssl_certificate_key /etc/nginx/ssl/attacker-self-signed.key;
    location / {
        proxy_pass http://$ATTACKER_IP:$ATTACKER_PORT;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
    }
}
EOF

# Test nginx configuration before starting
nginx -t 2>&1 | grep -q "successful" || {
    echo "[Entrypoint] ERROR: Nginx configuration test failed"
    nginx -t
    exit 1
}

# Kill any existing nginx process (in case container was restarted)
pkill nginx 2>/dev/null || true

# Start nginx
service nginx start || {
    echo "[Entrypoint] ERROR: Failed to start nginx"
    # Check what's using port 443
    netstat -tlnp | grep ':443' || true
    # Show nginx error logs
    tail -n 50 /var/log/nginx/error.log 2>/dev/null || true
    exit 1
}

ssh-keygen -A

if [ "$START_SSH" = "true" ]; then
    echo "[Entrypoint] Starting SSH daemon on port $SSH_PORT"
    /usr/sbin/sshd -D -p $SSH_PORT &
else
    echo "[Entrypoint] SSH daemon not started as per configuration."
fi

ADDITIONAL_NO_PROXY="$HTML_DOMAIN,$ATTACKER_DOMAIN"

# Update the variable in the current shell (PID 1 setup)
export no_proxy="${no_proxy},${ADDITIONAL_NO_PROXY}"
export NO_PROXY="${NO_PROXY},${ADDITIONAL_NO_PROXY}"

echo "[Entrypoint] Final NO_PROXY: $NO_PROXY"

# --- KEY FIX FOR DOCKER EXEC ---
# Append the export command to .bashrc.
# This ensures that when you run 'docker exec -it ... bash', 
# the new shell sources this file and gets the updated variables.

# Update root's bashrc
echo "export no_proxy=\"$NO_PROXY\"" >> /root/.bashrc
echo "export NO_PROXY=\"$NO_PROXY\"" >> /root/.bashrc

# Update devuser's bashrc
echo "export no_proxy=\"$NO_PROXY\"" >> /home/devuser/.bashrc
echo "export NO_PROXY=\"$NO_PROXY\"" >> /home/devuser/.bashrc

# (Optional) Update /etc/environment for completeness (PAM/Login shells)
# Overwriting is safer than sed replacement to avoid duplication issues
echo "http_proxy=\"$http_proxy\"" >> /etc/environment
echo "https_proxy=\"$https_proxy\"" >> /etc/environment
echo "no_proxy=\"$NO_PROXY\"" >> /etc/environment
echo "HTTP_PROXY=\"$HTTP_PROXY\"" >> /etc/environment
echo "HTTPS_PROXY=\"$HTTPS_PROXY\"" >> /etc/environment
echo "NO_PROXY=\"$NO_PROXY\"" >> /etc/environment

echo "[Entrypoint] Updated /etc/environment with: $ADDITIONAL_NO_PROXY"
# Fix permissions for devuser if needed (optional, e.g. if you mounted volumes)
# chown -R devuser:devuser /home/devuser/project

# --- 2. DROP PRIVILEGES & RUN COMMAND ---
echo "[Entrypoint] Dropping privileges to 'devuser' and starting app..."

# We set the required SSL variables for the user process
export REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
export SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt
export NODE_EXTRA_CA_CERTS=/etc/ssl/certs/ca-certificates.crt

# --- 3. START AGENT (if configured) ---
START_AGENT=${START_AGENT:-"true"}
AGENT_TYPE=${AGENT_TYPE:-"cli-agent"}

if [ "$START_AGENT" = "true" ]; then
    echo "[Entrypoint] Starting agent (type: $AGENT_TYPE)"
    # If no explicit command was provided, use start_agent.sh
    if [ $# -eq 0 ]; then
        set -- /app/start_agent.sh
    fi
else
    echo "[Entrypoint] Agent auto-start disabled (START_AGENT=$START_AGENT)"
    # If no command provided and agent not auto-starting, default to sleep
    if [ $# -eq 0 ]; then
        set -- sleep infinity
    fi
fi

# EXECUTE the CMD as devuser
exec gosu devuser env NO_PROXY="$NO_PROXY" no_proxy="$no_proxy" "$@"