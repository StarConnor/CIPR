import docker
import tarfile
import io
import re
import json
import pdb
from typing import List, Dict, Any
from datetime import datetime
import base64
import struct
import blackboxprotobuf 
from ..custom_types import ChatMessage

# ==========================================
# 1. Docker File Fetcher
# ==========================================
def fetch_file_content(container, remote_path):
    """Fetches a file from a container and returns bytes."""
    try:
        stream, _ = container.get_archive(remote_path)
        raw_tar = b"".join([chunk for chunk in stream])
        
        with tarfile.open(fileobj=io.BytesIO(raw_tar), mode='r|*') as tar:
            for member in tar:
                if member.isfile():
                    f = tar.extractfile(member)
                    if f:
                        return f.read()
    except Exception as e:
        print(f"[Warning] Could not fetch {remote_path}: {e}")
        return None

# ==========================================
# 2. eBPF/bpftrace Log Parser (JSON Format)
# ==========================================
def parse_ebpf_trace(log_content_bytes):
    """Parses bpftrace JSON output for system calls."""
    if not log_content_bytes:
        return []

    events = []
    log_text = log_content_bytes.decode('utf-8', errors='replace')
    
    for line_num, line in enumerate(log_text.splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("Attaching"):
            continue
        
        try:
            entry = json.loads(line)
        except json.JSONDecodeError as e:
            # print(f"[Warning] Line {line_num}: Invalid JSON - {e}")
            continue
        
        event_type = entry.get("t", "")
        ts_nsecs = entry.get("ts", 0)
        pid = entry.get("pid", 0)
        comm = entry.get("comm", "")
        
        # Convert nanoseconds timestamp to HH:MM:SS.us format
        try:
            ts_secs = ts_nsecs / 1_000_000_000.0
            dt = datetime.fromtimestamp(ts_secs)
            ts_str = dt.strftime('%H:%M:%S.%f')
        except:
            ts_str = "00:00:00.000000"
        
        # Parse different event types
        if event_type == "CMD":
            args = entry.get("args", "")
            # Filter noise
            if any(x in comm for x in ["bpftrace", "grep", "sleep", "tee", "cat"]):
                continue
            
            events.append({
                "timestamp": ts_str,
                "type": "COMMAND",
                "summary": f"EXEC: {comm}",
                "details": {"command": comm, "args": args, "pid": pid}
            })
        
        elif event_type == "FILE_OPEN":
            path = entry.get("path", "")
            flags = entry.get("flags", 0)
            
            # Filter noise
            if any(x in path for x in ["/dev/", "/proc/", "/sys/", ".pyc", ".so"]):
                continue
            
            events.append({
                "timestamp": ts_str,
                "type": "FILE_OPEN",
                "summary": f"OPEN: {path}",
                "details": {"path": path, "flags": flags, "pid": pid, "comm": comm}
            })
        
        elif event_type == "FILE_WRITE":
            fd = entry.get("fd", -1)
            size = entry.get("size", 0)
            
            # Handle both old 'content' and new 'content_hex' fields
            content_hex = entry.get("content_hex", "")
            content = entry.get("content", "")
            
            # Filter noise - stdout/stderr and log files
            if fd in [1, 2] or any(x in str(fd) for x in ["pipe:", "socket:", "anon_inode"]):
                continue
            
            # Decode content (hex-encoded from bpftrace with %r format)
            if content_hex:
                # The %r format gives us escape sequences like \x0a for newline
                # Python's decode with 'unicode_escape' handles this
                try:
                    decoded_content = content_hex.encode('utf-8').decode('unicode_escape')
                except:
                    decoded_content = content_hex
            else:
                # Fallback for old format
                try:
                    decoded_content = content.encode('utf-8').decode('unicode_escape')
                except:
                    decoded_content = content
            
            events.append({
                "timestamp": ts_str,
                "type": "FILE_WRITE",
                "summary": f"WRITE: fd={fd} ({size} bytes)",
                "details": {"fd": fd, "size": size, "content": decoded_content[:1000], "pid": pid, "comm": comm}
            })
        
        elif event_type == "FILE_READ":
            bytes_read = entry.get("bytes", 0)
            # Handle both old 'content' and new 'content_hex' fields
            content_hex = entry.get("content_hex", "")
            content = entry.get("content", "")
            
            if bytes_read <= 0:
                continue
            
            # Decode content (hex-encoded from bpftrace with %r format)
            if content_hex:
                # The %r format gives us escape sequences like \x0a for newline
                # Python's decode with 'unicode_escape' handles this
                try:
                    decoded_content = content_hex.encode('utf-8').decode('unicode_escape')
                except:
                    decoded_content = content_hex
            else:
                # Fallback for old format
                try:
                    decoded_content = content.encode('utf-8').decode('unicode_escape')
                except:
                    decoded_content = content

            events.append({
                "timestamp": ts_str,
                "type": "FILE_READ",
                "summary": f"READ: {bytes_read} bytes",
                "details": {"bytes": bytes_read, "pid": pid, "comm": comm, "content": decoded_content[:1000]}
            })
        
        elif event_type == "FILE_RENAME":
            oldpath = entry.get("oldpath", "")
            newpath = entry.get("newpath", "")
            
            events.append({
                "timestamp": ts_str,
                "type": "FILE_RENAME",
                "summary": f"RENAME: {oldpath} -> {newpath}",
                "details": {"oldpath": oldpath, "newpath": newpath, "pid": pid, "comm": comm}
            })
        
        elif event_type == "NET_CONNECT" or event_type == "TCP_CONNECT":
            fd = entry.get("fd", -1)
            
            events.append({
                "timestamp": ts_str,
                "type": "NETWORK_CONNECT",
                "summary": f"CONNECT: {comm} (fd={fd})",
                "details": {"fd": fd, "pid": pid, "comm": comm}
            })
        
        elif event_type == "PROC_EXIT":
            events.append({
                "timestamp": ts_str,
                "type": "PROC_EXIT",
                "summary": f"EXIT: {comm}",
                "details": {"pid": pid, "comm": comm}
            })

    return events


# ==========================================
# 3. Strace Log Parser (File IO & Cmds) [Legacy]
# ==========================================
def parse_system_trace(log_content_bytes):
    """Parses the strace -tt output for execve, write, read, file operations, and connect."""
    if not log_content_bytes:
        return []

    events = []
    log_text = log_content_bytes.decode('utf-8', errors='replace')
    
    # Regex patterns for different system calls
    # execve: 16:46:39.123456 [pid 123] execve("cmd", [args])
    re_exec = re.compile(r'(\d+:\d+:\d+\.\d+).*?execve\("([^"]+)", \[(.*?)\]')
    
    # write: 16:46:39.123456 [pid 123] write(4</path>, "content", len)
    re_write = re.compile(r'(\d+:\d+:\d+\.\d+).*?write\(\d+<([^>]+)>, "(.*)", \d+\)')
    
    # read: 16:46:39.123456 [pid 123] read(3</path>, "content", 4096) = bytes_read
    re_read = re.compile(r'(\d+:\d+:\d+\.\d+).*?read\(\d+<([^>]+)>, "(.*?)"(?:\.{3})?, \d+\).*?= (\d+|-?\d+)')
    
    # mmap: 16:46:39.123456 [pid 123] mmap(NULL, length, PROT_READ, MAP_PRIVATE, fd</path>, offset) = 0xaddress
    re_mmap = re.compile(r'(\d+:\d+:\d+\.\d+).*?mmap\([^,]+,\s*(\d+),\s*[^,]+,\s*[^,]+,\s*\d+<([^>]+)>')
    
    # connect: 16:46:39.123456 [pid 123] connect(3, {sa_family=AF_INET, sin_port=htons(443), sin_addr=inet_addr("1.2.3.4")}, 16) = 0
    re_connect = re.compile(r'(\d+:\d+:\d+\.\d+).*?connect\(\d+.*?sin_addr=inet_addr\("([^"]+)"\).*?sin_port=htons\((\d+)\)')

    for line in log_text.splitlines():
        line = line.strip()
        if not line or "resumed" in line:
            continue

        # --- Parse Commands (execve) ---
        if "execve(" in line:
            match = re_exec.search(line)
            if match:
                ts, cmd, args = match.groups()
                # Filter noise
                if any(x in cmd for x in ["strace", "grep", "sleep", "tee", "cat"]):
                    continue
                
                events.append({
                    "timestamp": ts,
                    "type": "COMMAND",
                    "summary": f"EXEC: {cmd}",
                    "details": {"command": cmd, "args": args[:500]}
                })

        # --- Parse File Writes ---
        elif "write(" in line:
            match = re_write.search(line)
            if match:
                ts, filename, content = match.groups()
                
                # Filter noise
                if any(x in filename for x in ["pipe:", "socket:", "anon_inode", ".log", "/dev/", "/proc/"]):
                    continue

                # Unescape Strace String (e.g. \n -> actual newline)
                try:
                    decoded_content = content.encode('utf-8').decode('unicode_escape')
                except:
                    decoded_content = content

                events.append({
                    "timestamp": ts,
                    "type": "FILE_WRITE",
                    "summary": f"WRITE: {filename}",
                    "details": {"path": filename, "content": decoded_content[:1000]}  # Limit content size
                })

        # --- Parse File Reads ---
        elif "read(" in line:
            match = re_read.search(line)
            if match:
                ts, filename, content, bytes_read = match.groups()
                
                # Filter noise
                if any(x in filename for x in ["pipe:", "socket:", "anon_inode", ".log", "/dev/", "/proc/"]):
                    continue
                
                # Skip binary files by extension
                binary_extensions = [
                    ".so", ".a", ".o",  # Libraries and object files
                    ".pyc", ".pyo",     # Python bytecode
                    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".svg", ".webp",  # Images
                    ".ttf", ".otf", ".woff", ".woff2", ".eot",  # Fonts
                    ".db", ".sqlite", ".sqlite3",  # Databases
                    ".bin", ".dat", ".exe", ".dll",  # Binary data
                    ".zip", ".tar", ".gz", ".bz2", ".xz",  # Archives
                    ".pdf", ".doc", ".docx",  # Documents
                ]
                if any(filename.lower().endswith(ext) for ext in binary_extensions):
                    continue
                
                # Skip reads that failed or returned 0 bytes
                if int(bytes_read) <= 0:
                    continue

                # Unescape content
                try:
                    decoded_content = content.encode('utf-8').decode('unicode_escape')
                except:
                    decoded_content = content
                
                # Check if content looks binary (too many non-printable characters)
                if decoded_content:
                    # Count printable vs non-printable characters
                    printable_count = sum(1 for c in decoded_content if c.isprintable() or c in '\n\r\t')
                    total_count = len(decoded_content)
                    if total_count > 0 and printable_count / total_count < 0.7:
                        # Less than 70% printable characters, likely binary
                        continue

                events.append({
                    "timestamp": ts,
                    "type": "FILE_READ",
                    "summary": f"READ: {filename} ({bytes_read} bytes)",
                    "details": {"path": filename, "content": decoded_content[:1000], "bytes": bytes_read}
                })

        # --- Parse Memory Mapped Files (mmap) ---
        elif "mmap(" in line:
            match = re_mmap.search(line)
            if match:
                ts, length, filepath = match.groups()
                
                # Filter noise
                if any(x in filepath for x in ["/dev/", "/proc/", "/sys/", "anon"]):
                    continue
                
                # Skip binary files by extension (same as read)
                binary_extensions = [
                    ".so", ".a", ".o",
                    ".pyc", ".pyo",
                    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".svg", ".webp",
                    ".ttf", ".otf", ".woff", ".woff2", ".eot",
                    ".db", ".sqlite", ".sqlite3",
                    ".bin", ".dat", ".exe", ".dll",
                    ".zip", ".tar", ".gz", ".bz2", ".xz",
                    ".pdf", ".doc", ".docx",
                ]
                if any(filepath.lower().endswith(ext) for ext in binary_extensions):
                    continue

                events.append({
                    "timestamp": ts,
                    "type": "FILE_MMAP",
                    "summary": f"MMAP: {filepath} ({length} bytes)",
                    "details": {"path": filepath, "length": length, "method": "mmap"}
                })

        # --- Parse Network Connections ---
        elif "connect(" in line and "sin_addr" in line:
            match = re_connect.search(line)
            if match:
                ts, ip_addr, port = match.groups()
                
                # Skip localhost connections (already handled by mitmproxy)
                if ip_addr.startswith("127.") or ip_addr == "::1":
                    continue

                events.append({
                    "timestamp": ts,
                    "type": "NETWORK_CONNECT",
                    "summary": f"CONNECT: {ip_addr}:{port}",
                    "details": {"ip": ip_addr, "port": port}
                })

    return events

# ==========================================
# 4. mitmproxy JSONL Parser (Network/API)
# ==========================================
def _decode_base64_content(content_str):
    """Decodes base64-encoded content if present."""
    import base64
    
    if isinstance(content_str, str) and content_str.startswith("<Base64>"):
        try:
            base64_data = content_str[8:]  # Remove "<Base64>" prefix
            decoded = base64.b64decode(base64_data)
            # Try to decode as UTF-8
            try:
                return decoded.decode('utf-8')
            except:
                return f"<Binary: {len(decoded)} bytes>"
        except:
            return content_str
    return content_str

def _parse_json_body(body_str):
    """Attempts to parse JSON from body string."""
    if not body_str or not isinstance(body_str, str):
        return body_str
    
    # Skip if it's binary marker
    if body_str.startswith("<Binary:") or body_str.startswith("<Base64>"):
        return body_str
    
    try:
        return json.loads(body_str)
    except:
        return body_str


def parse_sse_events(sse_body: str) -> List[Dict[str, Any]]:
    """Parse Server-Sent Events from chunked response body."""
    events = []
    current_event = {}
    
    for line in sse_body.split('\n'):
        line = line.strip()
        
        if not line:
            # Empty line marks end of an event
            if current_event:
                events.append(current_event)
                current_event = {}
            continue
        
        if line.startswith('event:'):
            current_event['event'] = line[6:].strip()
        elif line.startswith('data:'):
            data_str = line[5:].strip()
            try:
                current_event['data'] = json.loads(data_str)
            except json.JSONDecodeError:
                current_event['data'] = data_str
    
    # Don't forget the last event
    if current_event:
        events.append(current_event)
    
    return events


def extract_text_from_sse(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Extract structured data from SSE events (supports both Anthropic and OpenAI formats).
    
    Returns a dictionary containing:
    - role: The assistant role (if present)
    - content: Concatenated text content
    - tool_calls: List of tool calls with their details
    - thinking: Thinking/reasoning content (if present)
    - finish_reason: Why the completion finished (if present)
    """
    result = {
        'role': None,
        'content': '',
        'tool_calls': [],
        'thinking': '',
        'finish_reason': None,
        'model': None
    }
    
    content_parts = []
    thinking_parts = []
    tool_calls_by_index = {}  # For OpenAI streaming tool calls
    
    for event in events:
        if 'data' not in event or not isinstance(event['data'], dict):
            continue
        
        data = event['data']
        
        # Extract model info if available
        if 'model' in data and not result['model']:
            result['model'] = data['model']
        
        # OpenAI format: check for 'choices' array
        if 'choices' in data and isinstance(data['choices'], list):
            for choice in data['choices']:
                if 'delta' not in choice:
                    continue
                    
                delta = choice['delta']
                if isinstance(delta, dict):
                    # Extract role
                    if 'role' in delta and not result['role']:
                        result['role'] = delta['role']
                    
                    # Extract text content
                    if 'content' in delta and delta['content']:
                        content_parts.append(delta['content'])
                    
                    # Extract tool_calls (OpenAI format - streaming chunks)
                    if 'tool_calls' in delta:
                        for tool_call_chunk in delta['tool_calls']:
                            if not isinstance(tool_call_chunk, dict):
                                continue
                            
                            index = tool_call_chunk.get('index', 0)
                            
                            # Initialize tool call at this index if needed
                            if index not in tool_calls_by_index:
                                tool_calls_by_index[index] = {
                                    'id': '',
                                    'type': '',
                                    'function': {
                                        'name': '',
                                        'arguments': ''
                                    }
                                }
                            
                            # Merge chunks
                            if 'id' in tool_call_chunk:
                                tool_calls_by_index[index]['id'] = tool_call_chunk['id']
                            if 'type' in tool_call_chunk:
                                tool_calls_by_index[index]['type'] = tool_call_chunk['type']
                            if 'function' in tool_call_chunk:
                                func = tool_call_chunk['function']
                                if 'name' in func:
                                    tool_calls_by_index[index]['function']['name'] += func['name']
                                if 'arguments' in func:
                                    tool_calls_by_index[index]['function']['arguments'] += func['arguments']
                
                # Extract finish_reason
                if 'finish_reason' in choice and choice['finish_reason']:
                    result['finish_reason'] = choice['finish_reason']
        
        # Anthropic format: Extract text from content_block_delta events
        elif event.get('event') == 'content_block_delta':
            delta = data.get('delta', {})
            if 'text' in delta:
                content_parts.append(delta['text'])
            elif 'thinking' in delta:
                thinking_parts.append(delta['thinking'])
        
        # Anthropic format: message_start event (contains role)
        elif event.get('event') == 'message_start':
            message = data.get('message', {})
            if 'role' in message and not result['role']:
                result['role'] = message['role']
            if 'model' in message and not result['model']:
                result['model'] = message['model']
        
        # Anthropic format: message_delta event (contains finish reason)
        elif event.get('event') == 'message_delta':
            delta = data.get('delta', {})
            if 'stop_reason' in delta:
                result['finish_reason'] = delta['stop_reason']
        
        # Anthropic format: Extract text from text_delta events
        elif 'delta' in data:
            delta = data['delta']
            if isinstance(delta, dict):
                if 'text' in delta:
                    content_parts.append(delta['text'])
                elif delta.get('type') == 'text_delta' and 'text' in delta:
                    content_parts.append(delta['text'])
                elif delta.get('type') == 'thinking_delta' and 'thinking' in delta:
                    thinking_parts.append(delta['thinking'])
    
    # Assemble final result
    result['content'] = ''.join(content_parts)
    result['thinking'] = ''.join(thinking_parts)
    
    # Convert tool_calls dict to list (for OpenAI format)
    if tool_calls_by_index:
        result['tool_calls'] = [tool_calls_by_index[i] for i in sorted(tool_calls_by_index.keys())]
    
    return result


def parse_network_trace(jsonl_bytes):
    """Parses mitmproxy JSONL output into API events."""
    if not jsonl_bytes:
        return []

    events = []
    
    try:
        log_text = jsonl_bytes.decode('utf-8', errors='replace')
    except Exception as e:
        return []

    for line_num, line in enumerate(log_text.splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        
        try:
            entry = json.loads(line)
        except json.JSONDecodeError as e:
            continue
        
        # Skip test entries
        try:
            if entry.get("type") == "test" or entry.get("test"):
                continue
        except:
            print("\n-------------------Warning Begin----------------------")
            print(f"{line=}")
            print("\n-------------------Warning End----------------------")

            continue
        
        # Extract fields
        timestamp_epoch = entry.get("timestamp", "")
        method = entry.get("method", "")
        url = entry.get("url", "")
        status_code = entry.get("status_code", 0)
        host = entry.get("host", "")
        path = entry.get("path", "")
        
        request_headers = entry.get("request_headers", {})
        response_headers = entry.get("response_headers", {})
        
        request_body_raw = entry.get("request_body", "")
        response_body_raw = entry.get("response_body", "")
        
        # Decode base64 if present
        request_body = _decode_base64_content(request_body_raw)
        response_body = _decode_base64_content(response_body_raw)
        
        # Try to parse JSON bodies
        request_body = _parse_json_body(request_body)
        response_body = _parse_json_body(response_body)
        
        # Convert timestamp to HH:MM:SS.us format to match strace
        try:
            if timestamp_epoch:
                dt = datetime.fromtimestamp(float(timestamp_epoch))
                ts_str = dt.strftime('%H:%M:%S.%f')
            else:
                ts_str = "00:00:00.000000"
        except:
            ts_str = "00:00:00.000000"
        
        # Create request event
        events.append({
            "timestamp": ts_str,
            "type": "API_REQUEST",
            "summary": f"API_REQ: {method} {path}",
            "details": {
                "method": method,
                "url": url,
                "host": host,
                "path": path,
                "headers": request_headers,
                "body": request_body
            }
        })
        
        # Create response event (slightly offset timestamp for ordering)
        # Add 1 microsecond to ensure response comes after request
        try:
            dt_response = datetime.fromtimestamp(float(timestamp_epoch) + 0.000001)
            ts_str_response = dt_response.strftime('%H:%M:%S.%f')
        except:
            ts_str_response = ts_str

        # Check for chunked transfer encoding
        transfer_encoding = response_headers.get('Transfer-Encoding', response_headers.get('transfer-encoding', ''))
        if 'chunked' in transfer_encoding.lower():
            if 'https://api.gpt.ge' in url or 'https://api.v3.cm' in url:
                pass
            # Parse SSE events if body is string (SSE format)
            if isinstance(response_body, str) and response_body.strip():
                sse_events = parse_sse_events(response_body)
                response_body = extract_text_from_sse(sse_events)
        
        events.append({
            "timestamp": ts_str_response,
            "type": "API_RESPONSE",
            "summary": f"API_RESP: {status_code} {path}",
            "details": {
                "status_code": status_code,
                "url": url,
                "host": host,
                "path": path,
                "headers": response_headers,
                "body": response_body
            }
        })

    return events

def is_noise(node, filter_for_trace: Dict[str, Any] = {}):
    """Determine whether the node is a noise node"""
    for type, rules in filter_for_trace.items():
        if node.get("type", "") == type:
            if isinstance(rules, list):
                for pattern in rules:
                    for k, v in pattern.items():
                        # Look for the key in both top level and details
                        node_value = node.get(k, "") or node.get("details", {}).get(k, "")
                        if re.search(v, str(node_value)):
                            return True
    return False

def extract_anthropic_format(events: List[Dict[str, Any]]):
    agent_output = []
    agent_behavior_log = []
    for event in events:
        body = event.get("details", {}).get("body", {})
        messages = body.get("messages", [])
        
        # Handle API_REQUEST format: body.messages is an array
        if messages and isinstance(messages, list):
            for message in messages:
                role = message.get("role", "")
                if role == "user":
                    message_content = message.get("content", "")
                    
                    # Handle both string and list content
                    if isinstance(message_content, str) and message_content:
                        agent_output.append(ChatMessage(role="user", content=message_content))
                    elif isinstance(message_content, list):
                        # Process tool results in list format
                        text_parts = []
                        for item in message_content:
                            if item.get("type") == "tool_result":
                                tool_content = item.get("content", "")
                                is_error = item.get("is_error", False)
                                
                                if is_error:
                                    text_parts.append(f"[Tool Error]: {tool_content}")
                                elif tool_content:
                                    # Only add if content is meaningful (not too long)
                                    text_parts.append(f"[Tool Result]: {tool_content[:1000]}")
                            elif item.get("type") == "text":
                                text_content = item.get("text", "")
                                if text_content:
                                    text_parts.append(text_content)
                        
                        if text_parts:
                            agent_output.append(ChatMessage(role="user", content="\n".join(text_parts)))
                
                # Process assistant messages
                elif role == "assistant":
                    content_items = message.get("content", [])
                    
                    text_parts = []
                    
                    if isinstance(content_items, str):
                        text_parts.append(content_items)
                    elif isinstance(content_items, list):
                        for item in content_items:
                            item_type = item.get("type")
                            
                            # Extract thinking content
                            if item_type == "thinking":
                                thinking_text = item.get("thinking", "")
                                if thinking_text:
                                    text_parts.append(f"[Thinking]: {thinking_text}")
                            
                            # Extract regular text
                            elif item_type == "text":
                                text_content = item.get("text", "")
                                if text_content:
                                    text_parts.append(text_content)
                            
                            # Extract tool use
                            elif item_type == "tool_use":
                                tool_name = item.get("name", "")
                                tool_input = item.get("input", {})
                                
                                if tool_name:
                                    text_parts.append(f"[Tool Use: {tool_name}]")
                                    
                                    # Log specific tool behaviors
                                    if tool_name == "Bash":
                                        cmd = tool_input.get("command", "")
                                        if cmd:
                                            agent_behavior_log.append(f"Tool: {tool_name} | Command: {cmd}")
                                    elif tool_name == "Write":
                                        file_path = tool_input.get("file_path", "")
                                        if file_path:
                                            agent_behavior_log.append(f"Tool: {tool_name} | File: {file_path}")
                                    elif tool_name == "Read":
                                        file_path = tool_input.get("file_path", "")
                                        if file_path:
                                            agent_behavior_log.append(f"Tool: {tool_name} | File: {file_path}")
                                    else:
                                        agent_behavior_log.append(f"Tool: {tool_name} | Input: {str(tool_input)[:100]}")
                    
                    if text_parts:
                        full_text = "\n".join(text_parts)
                        agent_output.append(ChatMessage(role="assistant", content=full_text))
                    
                    # Extract tool_calls from message level (OpenAI format in messages)
                    if 'tool_calls' in message:
                        tool_calls = message.get("tool_calls", [])
                        for tool_call in tool_calls:
                            tool_name = tool_call.get("type", "") or tool_call.get("function", {}).get("name", "")
                            tool_input = tool_call.get("function", {}).get("arguments", "")
                            if tool_name:
                                agent_behavior_log.append(f"Tool: {tool_name} | Input: {str(tool_input)[:100]}")
        
        # Handle API_RESPONSE format: body directly contains role, content, tool_calls
        elif body.get("role"):
            role = body.get("role", "")
            content = body.get("content", "")
            thinking = body.get("thinking", "")
            
            text_parts = []
            if thinking:
                text_parts.append(f"[Thinking]: {thinking}")
            if content:
                text_parts.append(content)
            
            if text_parts:
                agent_output.append(ChatMessage(role=role, content="\n".join(text_parts)))
            
            # Extract tool_calls from body level (API_RESPONSE format)
            if 'tool_calls' in body:
                tool_calls = body.get("tool_calls", [])
                for tool_call in tool_calls:
                    # Handle both OpenAI and Anthropic formats
                    tool_name = tool_call.get("function", {}).get("name", "") or tool_call.get("name", "") or tool_call.get("type", "")
                    tool_input = tool_call.get("function", {}).get("arguments", "") or tool_call.get("input", {})
                    if tool_name:
                        agent_behavior_log.append(f"Tool: {tool_name} | Input: {str(tool_input)[:100]}")
    
    return agent_output, agent_behavior_log

def get_network_traces(container, filter_for_trace: Dict[str, Any] = {}):
    """Fetches and parses network traces from the container."""
    net_bytes = fetch_file_content(container, "/tmp/network_trace.jsonl")
    
    net_events = parse_network_trace(net_bytes)
    
    cleaned_net_events = []
    for event in net_events:
        if not is_noise(event, filter_for_trace=filter_for_trace):
            cleaned_net_events.append(event)
    
    # keep the last 2, one for the last request and one for the final response, which usually contains the most important info in a trace
    final_net_events = cleaned_net_events[-2:]

    # extract the tool calls from the final_net_events
    agent_output = []
    agent_behavior_log = []
    
    try:
        agent_output, agent_behavior_log = extract_anthropic_format(final_net_events)
        if not agent_output or not agent_behavior_log:
            raise ValueError("No meaningful content extracted from final_net_events")
    except Exception as e:
        agent_output, agent_behavior_log = [], []
        for event in final_net_events:
            # Safely get the details and body with proper type checking
            details = event.get("details", {})
            if not isinstance(details, dict):
                continue
                
            body = details.get("body")
            
            # Skip if body is None or not a dict/list
            if body is None:
                continue
            
            # Handle API_REQUEST format: body.messages exists
            if isinstance(body, dict):
                messages = body.get("messages")
                if messages and isinstance(messages, list):
                    for message in messages:
                        if not isinstance(message, dict):
                            continue
                            
                        role = message.get("role", "")
                        content = message.get("content", "")
                        
                        if role and content:
                            # Handle string content
                            if isinstance(content, str):
                                agent_output.append(ChatMessage(role=role, content=content))
                            # Handle list content (extract text)
                            elif isinstance(content, list):
                                text_parts = []
                                for item in content:
                                    if isinstance(item, dict) and item.get("type") == "text":
                                        text_parts.append(item.get("text", ""))
                                    elif isinstance(item, str):
                                        text_parts.append(item)
                                if text_parts:
                                    agent_output.append(ChatMessage(role=role, content="\n".join(text_parts)))
                        
                        # Extract tool_calls from message level
                        if 'tool_calls' in message and isinstance(message.get('tool_calls'), list):
                            tool_calls = message.get("tool_calls", [])
                            for tool_call in tool_calls:
                                if not isinstance(tool_call, dict):
                                    continue
                                    
                                tool_name = ""
                                if "function" in tool_call:
                                    tool_name = tool_call.get("function", {}).get("name", "")
                                if not tool_name:
                                    tool_name = tool_call.get("type", "")
                                    
                                tool_input = ""
                                if "function" in tool_call:
                                    tool_input = tool_call.get("function", {}).get("arguments", "")
                                
                                if tool_name:
                                    agent_behavior_log.append(f"Tool: {tool_name} | Input: {str(tool_input)[:100]}")
                
                # Handle API_RESPONSE format: body directly contains role, content, tool_calls
                elif body.get("role"):
                    role = body.get("role", "")
                    content = body.get("content", "")
                    
                    if role and content:
                        # Ensure content is string or convert appropriately
                        if isinstance(content, str):
                            agent_output.append(ChatMessage(role=role, content=content))
                        elif isinstance(content, (list, dict)):
                            # Try to serialize if needed
                            try:
                                content_str = str(content)
                                agent_output.append(ChatMessage(role=role, content=content_str))
                            except Exception:
                                pass
                    
                    # Extract tool_calls from body level
                    if 'tool_calls' in body and isinstance(body.get('tool_calls'), list):
                        tool_calls = body.get("tool_calls", [])
                        for tool_call in tool_calls:
                            if not isinstance(tool_call, dict):
                                continue
                                
                            tool_name = ""
                            if "function" in tool_call:
                                tool_name = tool_call.get("function", {}).get("name", "")
                            if not tool_name:
                                tool_name = tool_call.get("type", "")
                                
                            tool_input = ""
                            if "function" in tool_call:
                                tool_input = tool_call.get("function", {}).get("arguments", "")
                            
                            if tool_name:
                                agent_behavior_log.append(f"Tool: {tool_name} | Input: {str(tool_input)[:100]}")
            
            # If body is a list, handle list of messages
            elif isinstance(body, list):
                for item in body:
                    if not isinstance(item, dict):
                        continue
                    role = item.get("role", "")
                    content = item.get("content", "")
                    if role and content and isinstance(content, str):
                        agent_output.append(ChatMessage(role=role, content=content))
    
    return agent_output, agent_behavior_log