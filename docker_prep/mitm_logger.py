import json
import base64
import os
from mitmproxy import http

# Read the API domains to record from an environment variable, comma-separated
# e.g.: MITM_TARGET_HOSTS="api.anthropic.com,api.openai.com,openrouter.ai"
_raw = os.environ.get("MITM_TARGET_HOSTS", "")
TARGET_HOSTS = [h.strip() for h in _raw.split(",") if h.strip()]

def safe_encode_content(content):
    if not content:
        return ""
    try:
        return content.decode('utf-8', errors='ignore')
    except:
        return f"<Base64>{base64.b64encode(content).decode('ascii')}"

def response(flow: http.HTTPFlow):
    # Skip local calls
    if flow.request.host in ["127.0.0.1", "localhost"]:
        return
    if "mitmproxy" in flow.request.headers.get("User-Agent", "").lower():
        return

    # If target domains are set, only record matching ones
    if TARGET_HOSTS:
        host = flow.request.host
        if not any(host == t or host.endswith("." + t) for t in TARGET_HOSTS):
            return  # Do not record, but let the traffic pass through normally

    entry = {
        "type": "API_COMPLETE",
        "timestamp": str(flow.request.timestamp_start),
        "method": flow.request.method,
        "url": flow.request.url,
        "host": flow.request.host,
        "port": flow.request.port,
        "path": flow.request.path,
        "status_code": flow.response.status_code,
        "request_headers": dict(flow.request.headers),
        "request_body": safe_encode_content(flow.request.content),
        "response_headers": dict(flow.response.headers),
        "response_body": safe_encode_content(flow.response.content)
    }

    try:
        with open("/tmp/network_trace.jsonl", "a", encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        import sys
        print(f"Error writing to network_trace.jsonl: {e}", file=sys.stderr)