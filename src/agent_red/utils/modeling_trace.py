import json
import base64
import gzip
import zlib
import re
import os
from datetime import datetime
import brotli

class AgentLogProcessor:
    def __init__(self, log_file_path=None, content=None, filter_for_trace={}):
        self.log_file_path = log_file_path
        self.content = content
        # Regex used to strip terminal color codes
        self.noise_filters = filter_for_trace

    def _split_http_payload(self, raw_bytes):
        """
        Splits Raw HTTP wire data into (Headers String, Body Bytes)
        """
        delimiter = b'\r\n\r\n'
        if delimiter in raw_bytes:
            parts = raw_bytes.split(delimiter, 1)
            header_bytes = parts[0]
            body_bytes = parts[1]
            return header_bytes.decode('utf-8', errors='ignore'), body_bytes
        return "", raw_bytes

    def _get_encoding_from_headers(self, headers):
        """Simple header parser to find Content-Encoding"""
        # Handle both dictionary (new format) and string (old format)
        if isinstance(headers, dict):
            # New format: headers is a dictionary
            for key, value in headers.items():
                if key.lower() == 'content-encoding':
                    return value.strip()
            return None
        elif isinstance(headers, str):
            # Old format: headers is a raw HTTP header string
            for line in headers.split('\r\n'):
                if 'content-encoding:' in line.lower():
                    return line.lower().split(':')[1].strip()
            return None
        else:
            return None

    def is_noise(self, node):
        """Determine whether the node is a noise node"""
        for type, rules in self.noise_filters.items():
            if node.get("type", "") == type:
                for pattern in rules:
                    for k, v in pattern.items():
                        # Look for the key in both top level and details
                        node_value = node.get(k, "") or node.get("details", {}).get(k, "")
                        if re.search(v, str(node_value)):
                            return True
        return False

    def _reconstruct_sse(self, sse_text):
        """
        Parse the SSE stream and reconstruct Chain of Thought (Thinking) and Tool Use
        """
        # Initialize the result containers
        result = {
            "type": "stream_reconstructed",
            "thinking": "",     # Holds the concatenated thinking process
            "tool_use": [],     # Holds tool invocations
            "response_text": "" # Holds plain text replies
        }

        # Temporary buffers
        current_tool = None
        tool_json_buffer = ""

        # Process line by line
        lines = sse_text.split('\n')
        
        for line in lines:
            line = line.strip()
            # Only process data lines; ignore event lines (unless you need the event type for special handling)
            if not line.startswith("data: "):
                continue
            
            raw_data = line[6:] # Strip the "data: " prefix
            if raw_data == "[DONE]": continue # OpenAI end-of-stream marker
            
            try:
                chunk = json.loads(raw_data)
                
                # --- Anthropic/Claude stream format handling ---
                evt_type = chunk.get("type")
                
                # 1. Concatenate thinking process (Thinking Delta)
                if evt_type == "content_block_delta":
                    delta = chunk.get("delta", {})
                    delta_type = delta.get("type")
                    
                    if delta_type == "thinking_delta":
                        result["thinking"] += delta.get("thinking", "")
                    
                    # 2. Concatenate tool arguments (Input JSON Delta)
                    elif delta_type == "input_json_delta":
                        tool_json_buffer += delta.get("partial_json", "")
                    
                    # 3. Concatenate plain text replies (Text Delta)
                    elif delta_type == "text_delta":
                        result["response_text"] += delta.get("text", "")

                # 4. Tool start (Tool Use Start)
                elif evt_type == "content_block_start":
                    block = chunk.get("content_block", {})
                    if block.get("type") == "tool_use":
                        # If a previous tool is still unprocessed, save it first (should not normally happen)
                        current_tool = {
                            "name": block.get("name"),
                            "id": block.get("id"),
                            "input": {} 
                        }
                        tool_json_buffer = "" # Reset the JSON buffer

                # 5. Block stop (Block Stop) - JSON concatenation complete, try parsing
                elif evt_type == "content_block_stop":
                    if current_tool and tool_json_buffer:
                        try:
                            # The concatenated string is usually a complete JSON object
                            current_tool["input"] = json.loads(tool_json_buffer)
                            result["tool_use"].append(current_tool)
                        except:
                            # Keep the raw string for debugging if the JSON is incomplete
                            current_tool["input_raw"] = tool_json_buffer
                            result["tool_use"].append(current_tool)
                        
                        current_tool = None
                        tool_json_buffer = ""

                # --- OpenAI format compatibility (optional) ---
                choices = chunk.get("choices", [])
                if choices:
                    delta = choices[0].get("delta", {})
                    if "content" in delta and delta["content"]:
                        result["response_text"] += delta["content"]
                    if "tool_calls" in delta:
                        # OpenAI's streaming tool-call handling is more complex and omitted here,
                        # since the logs are clearly Anthropic format
                        pass

            except json.JSONDecodeError:
                continue

        # Remove empty fields
        if not result["thinking"]: del result["thinking"]
        if not result["tool_use"]: del result["tool_use"]
        if not result["response_text"]: del result["response_text"]
        
        return result
    def _decode_body(self, body_b64, encoding):
        """Decompress body based on encoding"""
        if not body_b64:
            return None
        
        # First decode from base64 to bytes
        try:
            if isinstance(body_b64, str):
                body_bytes = base64.b64decode(body_b64)
            else:
                body_bytes = body_b64  # Already bytes
        except Exception as e:
            return body_b64  # Return as-is if decode fails
            
        # Then decompress if needed
        try:
            if encoding and 'gzip' in encoding:
                body_bytes = gzip.decompress(body_bytes)
            elif encoding and 'br' in encoding and brotli:
                body_bytes = brotli.decompress(body_bytes)
            elif encoding and 'deflate' in encoding:
                body_bytes = zlib.decompress(body_bytes)
        except Exception as e:
            # Sometimes data isn't compressed even if header says so, or partial
            pass
        
        # Finally decode to string
        try:
            return body_bytes.decode('utf-8', errors='replace')
        except Exception:
            return body_bytes.decode('latin-1', errors='replace')

    def process(self):
        timeline = []
        
        # Handle content string directly or read from file
        if self.content is not None:
            lines = self.content.splitlines()
        elif self.log_file_path:
            if not os.path.exists(self.log_file_path):
                print(f"Error: Log file not found at {self.log_file_path}")
                return []
            with open(self.log_file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        else:
            print("Error: Neither content nor log_file_path provided")
            return []
        
        for line_num, line in enumerate(lines):
            line = line.strip()
            if not line: continue
            
            try:
                entry = json.loads(line)
                
                # Base metadata
                ts_ms = entry.get('ts', 0)
                dt_object = datetime.fromtimestamp(ts_ms / 1000.0)
                timestamp_str = dt_object.isoformat()
                
                evt_type = entry.get('t')
                data = entry.get('d', {})
                
                # Build the standard node structure
                node = {
                    "id": line_num,
                    "timestamp": timestamp_str,
                    "timestamp_ms": ts_ms,
                    "type": evt_type,
                    "details": {}
                }
                # =========================================
                # 1. Network layer (Network)
                # =========================================
                if evt_type in ['FETCH', 'HTTPS']:
                    decoded_req_body = self._decode_body(data.get('reqb64'), None)
                    resp_encoding = self._get_encoding_from_headers(data.get('respHeaders', ''))
                    decoded_resp_body = self._decode_body(data.get('respb64'), resp_encoding or "")
                    node["details"] = {
                        "method": data.get('method', 'GET'),
                        "url": data.get('url'),
                        "status": data.get('status'),
                        "headers": {'req': data.get('reqHeaders'), 'resp': data.get('respHeaders')},
                        "reqbody": decoded_req_body,
                        "respbody": decoded_resp_body,
                    }
                    node["summary"] = f"Request: {data.get('method')} {data.get('url')} -> {data.get('status')}"
                # =========================================
                # 2. File system (FileSystem)
                # =========================================
                elif evt_type == 'FS_WRITE':
                    node["details"] = {"path": data.get('p'), "method": data.get('m'), 'content': data.get('content')}
                    node["summary"] = f"Write File: {data.get('p')}"

                elif evt_type == 'FS_READ':
                    node["details"] = {"path": data.get('p'), 'result': data.get('result') or data.get('error')}
                    node["summary"] = f"Read File: {data.get('p')}"

                elif evt_type == 'FS_LIST':
                    node["details"] = {"path": data.get('p')}
                    node["summary"] = f"List Directory: {data.get('p')}"

                # =========================================
                # 3. Command line / Shell (Execution)
                # =========================================
                elif evt_type == 'CMD':
                    cmd_str = f"{data.get('c')} {' '.join(data.get('a', []))}"
                    node["details"] = {
                        "command": data.get('c'),
                        "args": data.get('a'),
                        "cwd": data.get('w'),
                        "code": data.get('code'),
                    }
                    if data.get('stdout'):
                        node["details"]["stdout"] = data.get('stdout')
                    if data.get('stderror'):
                        node["details"]["stderror"] = data.get('stderror')
                    node["summary"] = f"Run Command: {cmd_str}"

                else:
                    # Handle unknown events
                    node["details"] = data
                    node["summary"] = f"Unknown Event: {evt_type}"

                if self.is_noise(node):
                    continue

                timeline.append(node)

            except json.JSONDecodeError:
                print(f"Skipping malformed JSON line: {line[:50]}...")
            except Exception as e:
                print(f"Error processing line {line_num}: {e}")

        return timeline


def extract_trace(container=None, content=None, log_file_path=None, filter_for_trace={}):
    """
    Extract trace from container, content string, or file path.
    
    Args:
        container: Docker container object (will read /tmp/raw_trace.jsonl)
        content: Direct content string of the trace file
        log_file_path: Path to local trace file
    
    Returns:
        List of processed trace events
    """
    if content is not None:
        processor = AgentLogProcessor(content=content, filter_for_trace=filter_for_trace)
        return processor.process()
    elif container is not None:
        try:
            # Get file content from container
            exit_code, output = container.exec_run(
                "cat /tmp/raw_trace.jsonl",
                demux=False
            )
            if exit_code == 0:
                content = output.decode('utf-8', errors='replace')
                processor = AgentLogProcessor(content=content, filter_for_trace=filter_for_trace)
                return processor.process()
            else:
                print(f"Error reading trace from container: exit code {exit_code}")
                return []
        except Exception as e:
            print(f"Error extracting trace from container: {e}")
            return []
    elif log_file_path is not None:
        processor = AgentLogProcessor(log_file_path=log_file_path, filter_for_trace=filter_for_trace)
        return processor.process()
    else:
        print("Error: Must provide either container, content, or log_file_path")
        return []
