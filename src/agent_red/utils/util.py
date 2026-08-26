import json
import re
import requests
import time
import pdb
import asyncio
import logging
import sseclient
import base64
import subprocess
from typing import Any, Callable, Dict, Tuple, Optional, List

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)
from .extract_traces import get_network_traces
from ..environment_manager import EnvironmentManager
from ..custom_types import ChatMessage

def _read_file_from_container(container, file_path: str) -> str:
    """Read file content from container."""
    try:
        exit_code, output = container.exec_run(f"cat {file_path}")
        if exit_code == 0:
            return output.decode().strip()
        else:
            return f"[Error reading file: {file_path}]"
    except Exception as e:
        return f"[Error reading file {file_path}: {str(e)}]"

def _looks_like_codex_history(chat_content_str: str) -> bool:
    if not chat_content_str:
        return False
    for line in chat_content_str.splitlines()[:20]:
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if entry.get("type") in {"session_meta", "response_item", "event_msg", "turn_context"}:
            return True
    return False

def extract_messages_and_logs(chat_content_str, target_name, manager: Optional[EnvironmentManager]=None, filter_for_trace: Optional[Dict[str, Any]] = None) -> Tuple[List[ChatMessage], List[str]]:
    """
    Unified parser to handle:
    1. Copilot JSON (dict)
    2. Cline/Claude-dev/Anthropic JSON (list) - IMPROVED
    3. Cursor Markdown (str)
    4. Claude Code JSONL format (newline-delimited JSON)
    """
    agent_output = []
    agent_behavior_log = []
    
    # --- FORMAT 5: Codex NDJSON (newline-delimited JSON with specific structure) ---
    # Check if content is Codex format (has session_meta, response_item, event_msg)
    if target_name == 'codex_cli' or _looks_like_codex_history(chat_content_str or ""):
        try:
            agent_output, agent_behavior_log = parse_codex_chat_history(chat_content_str)
            if agent_output or agent_behavior_log:
                return agent_output, agent_behavior_log
        except Exception as e:
            LOGGER.warning(f"Failed to parse Codex NDJSON format: {e}")
    # Claude Code stores a JSONL conversation that contains its tool calls.
    # It must be parsed before the generic CLI network-trace fallback; the
    # latter previously made the ``cc_cli`` branch below unreachable and left
    # Claude samples with empty commands/traces despite successful execution.
    if 'cli' in target_name and target_name != 'cc_cli':
        agent_output, agent_behavior_log = get_network_traces(container=manager.code_server.container, filter_for_trace=filter_for_trace or {})
        return agent_output, agent_behavior_log
    
    # --- FORMAT 4: Claude Code JSONL (newline-delimited JSON) ---
    # Check if content is JSONL format (each line is a JSON object)
    elif target_name == 'cc_cli':
        if not chat_content_str:
            agent_container = manager.code_server.container
            
            # Find the latest task directory
            tasks_path = "/home/devuser/.claude/projects/-home-devuser-project"
            # find the latest jsonl file in tasks_path
            exit_code, output = agent_container.exec_run(f"ls -t {tasks_path}/*.jsonl")
            if exit_code != 0:
                raise RuntimeError(f"Failed to list jsonl files in tasks directory: {output.decode()}")
            chat_history_path = output.decode().strip().split('\n')[0]
            
            # Read the chat history file
            exit_code, chat_content = agent_container.exec_run(f"cat {chat_history_path}")
            if exit_code != 0:
                raise RuntimeError(f"Failed to read chat history: {chat_content.decode()}")
            
            chat_content_str = chat_content.decode()
        try:
            lines = chat_content_str.strip().split('\n')
            for line in lines:
                if not line.strip():
                    continue
                try:
                    event = json.loads(line)
                    event_type = event.get("type")
                    
                    # Process user messages
                    if event_type == "user":
                        message_content = event.get("message", {}).get("content", "")
                        
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
                                        if len(tool_content) < 500:
                                            text_parts.append(f"[Tool Result]: {tool_content}")
                            
                            if text_parts:
                                agent_output.append(ChatMessage(role="user", content="\n".join(text_parts)))
                    
                    # Process assistant messages
                    elif event_type == "assistant":
                        message = event.get("message", {})
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
                
                except json.JSONDecodeError:
                    # Skip invalid JSON lines
                    continue
            
            # If we successfully parsed JSONL format, return results
            if agent_output:
                return agent_output, agent_behavior_log
        except Exception as e:
            LOGGER.warning(f"Failed to parse JSONL format: {e}")
    
    elif target_name == "cline_ide":
        if manager is None:
            raise ValueError("EnvironmentManager is required to extract cline logs.")
        agent_container = manager.code_server.container
        
        # Find the latest task directory
        tasks_path = "/home/devuser/.vscode-server/data/User/globalStorage/saoudrizwan.claude-dev/tasks/"
        exit_code, output = agent_container.exec_run(f"ls -t {tasks_path}")
        if exit_code != 0:
            raise RuntimeError(f"Failed to list tasks directory: {output.decode()}")
        
        # Get the latest subdirectory (first in time-sorted list)
        subdirs = output.decode().strip().split('\n')
        if not subdirs or subdirs[0] == '':
            raise RuntimeError("No task directories found")
        
        latest_subdir = subdirs[0]
        chat_history_path = f"{tasks_path}{latest_subdir}/api_conversation_history.json"
        
        # Read the chat history file
        exit_code, chat_content = agent_container.exec_run(f"cat {chat_history_path}")
        if exit_code != 0:
            raise RuntimeError(f"Failed to read chat history: {chat_content.decode()}")
        
        chat_content_str = chat_content.decode()

    # Attempt to detect if it's JSON
    try:
        data = json.loads(chat_content_str)
        
        if target_name == "trae_ide":
            # --- FORMAT: TRAE IDE (List of messages) ---
            if isinstance(data, list):
                for msg in data:
                    role = msg.get("role")
                    content = msg.get("content", "")
                    
                    # Add the message to output
                    agent_output.append(ChatMessage(role=role, content=content))
                    
                    # Extract behavior logs for assistant messages
                    if role == "assistant":
                        # Check for code blocks in the content
                        code_blocks = re.findall(r'```(?:python|bash|shell|js|javascript|sql|json)?\n(.*?)\n```', content, re.DOTALL)
                        for code_block in code_blocks:
                            agent_behavior_log.append(f"[CODE BLOCK]: {code_block.strip()[:100]}...")
                        
                        # Check for XML-style tags (like <search>, <replace>, etc.)
                        tags = re.findall(r'<(?P<tag>[a-z_]+)>(.*?)</(?P=tag)>', content, re.DOTALL)
                        for tag, tag_content in tags:
                            agent_behavior_log.append(f"[{tag.upper()}]: {tag_content.strip()[:100]}...")
        # --- FORMAT 2: Cline/Claude-dev/Anthropic (List) ---
        elif isinstance(data, list):
            for msg in data:
                role = msg.get("role")
                content_raw = msg.get("content", [])
                model_info = msg.get("modelInfo", {})
                
                text_parts = []
                
                # Handle case where content is just a string
                if isinstance(content_raw, str):
                    text_parts.append(content_raw)
                
                # Handle case where content is a list of blocks (Text + Tool Use)
                elif isinstance(content_raw, list):
                    for item in content_raw:
                        item_type = item.get("type")
                        
                        # 1. Extract Text
                        if item_type == "text":
                            text_parts.append(item.get("text", ""))
                        
                        # 2. Extract Tool Execution (THIS WAS MISSING)
                        elif item_type == "tool_use":
                            tool_name = item.get("name")
                            tool_input = item.get("input", {})
                            
                            # Log the behavior
                            if tool_name == "execute_command":
                                cmd = tool_input.get("command", "UNKNOWN")
                                agent_behavior_log.append(f"Tool: {tool_name} | Command: {cmd}")
                                text_parts.append(f"[Tool Use: {tool_name}] [Command: {cmd}]")
                            else:
                                agent_behavior_log.append(f"Tool: {tool_name} | Input: {tool_input}")
                                text_parts.append(f"[Tool Use: {tool_name}] [Input: {tool_input}]")
                                
                            # Optionally add a marker in the text output

                full_text = "\n".join(text_parts)
                agent_output.append(ChatMessage(role=role, content=full_text, model=model_info if model_info else None))

                # Keep your original Regex for XML tags (in case they mix formats)
                if role == "assistant":
                    tags = re.findall(r'<(?P<tag>[a-z_]+)>(.*?)</(?P=tag)>', full_text, re.DOTALL)
                    for tag, content in tags:
                        agent_behavior_log.append(f"[{tag.upper()}]: {content.strip()}")

        # --- FORMAT 2: Copilot (Dict with requests) ---
        elif isinstance(data, dict) and "requests" in data:
            for req in data.get("requests", []):
                # Extract user message
                user_message = req.get("message", {}).get("text", "")
                if user_message:
                    agent_output.append(ChatMessage(role="user", content=user_message))
                
                # Extract assistant responses - keep each item separate
                for resp_idx, resp in enumerate(req.get("response", [])):
                    resp_kind = resp.get("kind")
                    
                    # Extract thinking blocks as separate messages
                    if resp_kind == "thinking":
                        thinking_value = resp.get("value", "")
                        if thinking_value:
                            agent_output.append(ChatMessage(role="assistant", content=f"[Thinking]: {thinking_value}"))
                    
                    # Extract main text values as separate messages
                    elif "value" in resp and resp_kind != "inlineReference" and resp_kind != "prepareToolInvocation" and resp_kind != "thinking":
                        text_value = resp.get("value", "")
                        if text_value:
                            agent_output.append(ChatMessage(role="assistant", content=text_value))
                    
                    # Extract tool invocations as separate messages
                    elif resp_kind == "toolInvocationSerialized":
                        tool_specific = resp.get("toolSpecificData", {})
                        tool_name = tool_specific.get("toolName")
                        command_line = tool_specific.get("commandLine", {}).get("original", "")
                        terminal_output = tool_specific.get("terminalCommandOutput", {}).get("text", "")
                        
                        tool_content_parts = []
                        if tool_name:
                            tool_content_parts.append(f"[toolInvocationSerialized] Tool: {tool_name}")
                        if command_line:
                            tool_content_parts.append(f"Command: {command_line}")
                        if terminal_output:
                            tool_content_parts.append(f"Output: {terminal_output[:500]}")
                        
                        if tool_content_parts:
                            agent_output.append(ChatMessage(role="assistant", content="\n".join(tool_content_parts)))
                            # Log for behavior tracking
                            if tool_name and command_line:
                                agent_behavior_log.append(f"Tool: {tool_name} | Command: {command_line}")
                    
                    # Extract inline references combined with surrounding content
                    elif resp_kind == "inlineReference":
                        ref_path = resp.get("inlineReference", {}).get("path", "")
                        if ref_path:
                            # Collect content: before + inlineReference + after
                            content_parts = []
                            
                            # Get content before (from the previous message if it exists)
                            if agent_output:
                                before_content = agent_output[-1].content
                                content_parts.append(before_content)
                                # Remove the last message since we'll merge it
                                agent_output.pop()
                            
                            # Add the inline reference path
                            content_parts.append(f"[inlineReference]: {ref_path}")
                            
                            # Read the file content from container if available
                            if manager and hasattr(manager, 'code_server') and hasattr(manager.code_server, 'container'):
                                container = manager.code_server.container
                                file_content = _read_file_from_container(container, ref_path)
                                content_parts.append(f"\n```\n{file_content}\n```")
                            
                            # Check for content after (next response items)
                            for next_resp in req.get("response", [])[resp_idx + 1:]:
                                next_kind = next_resp.get("kind")
                                if next_kind == "inlineReference":
                                    # Stop at the next inlineReference
                                    break
                                elif "value" in next_resp and next_kind not in ["prepareToolInvocation", "thinking"]:
                                    content_parts.append(next_resp.get("value", ""))
                            
                            # Create combined message
                            agent_output.append(ChatMessage(role="assistant", content="\n".join(content_parts)))
                
                # Extract behavior from metadata
                for round in req.get("result", {}).get("metadata", {}).get("toolCallRounds", []):
                    for call in round.get("toolCalls", []):
                        agent_behavior_log.append(f"Tool: {call.get('function')} | Args: {call.get('arguments')}")
        
        return agent_output, agent_behavior_log

    except (json.JSONDecodeError, TypeError):
        # --- FORMAT 3: Cursor Markdown (String) ---
        if "**User**" in chat_content_str and "**Cursor**" in chat_content_str:
            parts = re.split(r'\n(?=\*\*(?:User|Cursor)\*\*)', chat_content_str)
            for part in parts:
                if part.startswith("**User**"):
                    content = part.replace("**User**", "").strip()
                    agent_output.append(ChatMessage(role="user", content=content))
                elif part.startswith("**Cursor**"):
                    content = part.replace("**Cursor**", "").strip()
                    agent_output.append(ChatMessage(role="assistant", content=content))
                    behavior_match = re.search(r'(What I did|Status):.*?(?=\n\n|\Z)', content, re.DOTALL)
                    if behavior_match:
                        agent_behavior_log.append(behavior_match.group(0).strip())
            return agent_output, agent_behavior_log

    return [ChatMessage(role="unknown", content=chat_content_str)], []

def extract_attacker_server_log(attacker_server_port: int = 8085, timeout: float = 5.0) -> dict:
    try:
        res = requests.get(
            f"http://localhost:{attacker_server_port}/logs",
            timeout=timeout
        )
        if res.status_code == 200:
            try:
                return res.json()
            except json.JSONDecodeError:
                return {}
        LOGGER.warning(
            "Failed to fetch attacker logs from port %s (status=%s)",
            attacker_server_port,
            res.status_code,
        )
        return {}
    except requests.RequestException as e:
        LOGGER.warning(
            "Attacker log fetch failed (port=%s): %s",
            attacker_server_port,
            e,
        )
        return {}

def run_cli_command(command: list[str], timeout: int = 30) -> Optional[str]:
    """
    Run a CLI command with a timeout and return its output.
    
    Args:
        command: The command to run
        timeout: Timeout in seconds
    
    Returns:
        Command output as string, or None if timed out
    """
    result = subprocess.run(command, shell=False, capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        raise RuntimeError(f"Command '{' '.join(command)}' failed with error: {result.stderr.strip()}")
    return result.stdout.strip()

def execute_workflow_stream(
    url: str,
    json_payload: Dict[str, Any],
    headers: Optional[Dict[str, str]] = None,
    on_log: Optional[Callable[[str, str], None]] = None,
    on_complete: Optional[Callable[[Dict[str, Any]], None]] = None,
    on_error: Optional[Callable[[str], None]] = None,
    frame_queue: asyncio.Queue | None = None,
    main_loop: asyncio.AbstractEventLoop | None = None,
    stream_screenshots: bool = True,
    stream_logs: bool = True,
    timeout: Tuple[int, int] = (30, 150),
    logger: Optional[logging.Logger] = None
) -> Dict[str, Any]:
    """
    Execute a streaming SSE workflow and handle events.
    
    This is a fully decoupled function that can work with any SSE endpoint.
    
    Args:
        url: Full URL of the streaming endpoint (e.g., "http://localhost:5000/stream")
        json_payload: Request body to send (e.g., {"prompt": "...", "model": "..."})
        headers: Optional HTTP headers (will add 'Accept: text/event-stream' automatically)
        on_log: Optional callback for log events (level, message)
        on_complete: Optional callback for completion event (outputs)
        on_error: Optional callback for error event (error_message)
        frame_queue: Optional asyncio queue for screenshot frames
        main_loop: Optional asyncio event loop for thread-safe queue operations
        timeout: Tuple of (connect_timeout, read_timeout)
        logger: Optional logger instance
    
    Returns:
        Dict with 'success' and 'outputs' keys
    
    Raises:
        Exception if workflow fails
    """
    if logger is None:
        logger = LOGGER
    
    if headers is None:
        headers = {}
    
    logger.info(f"Starting streaming request to {url}")
    
    try:
        json_payload = dict(json_payload)
        json_payload.setdefault("stream_screenshots", stream_screenshots)
        json_payload.setdefault("stream_logs", stream_logs)

        resp = requests.post(
            url,
            json=json_payload,
            stream=True,
            headers={'Accept': 'text/event-stream', **headers},
            timeout=timeout
        )
        resp.raise_for_status()
        
        client = sseclient.SSEClient(resp)
        outputs = None
        error = None
        
        for event in client.events():
            try:
                data = json.loads(event.data)
                
                if data['type'] == 'log':
                    log_entry = data['data']
                    level = log_entry.get('level', 'INFO')
                    message = log_entry.get('message', '')
                    if on_log:
                        on_log(level, message)
                
                elif data['type'] == 'complete':
                    outputs = data.get('outputs', {}) or data  # Support both formats
                    logger.info(f"Workflow completed successfully")
                    if on_complete:
                        on_complete(outputs)
                    break
                
                elif data['type'] == 'error':
                    error = data.get('error', 'Unknown error')
                    logger.error(f"Workflow error: {error}")
                    if on_error:
                        on_error(error)
                    break

                elif data['type'] == 'screenshot':
                    if not (frame_queue and main_loop):
                        continue
                    try:
                        img_bytes = base64.b64decode(data['data'])
                        # Use call_soon_threadsafe because we are inside a blocking 
                        # requests loop, not an async coroutine
                        main_loop.call_soon_threadsafe(
                            frame_queue.put_nowait, 
                            img_bytes
                        )
                    except Exception as e:
                        logger.error(f"Failed to process screenshot: {e}")
            
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse event data: {e}")
                continue
        
        if error:
            raise Exception(f"Workflow failed: {error}")
        
        if isinstance(outputs, dict) and 'status' in outputs and outputs['status'] != 'success':
            return {"success": False, "outputs": outputs or {}}
        return {"success": True, "outputs": outputs or {}}
    
    except Exception as e:
        status = requests.get(url.replace("/stream", "/status"), timeout=10)
        logger.error(f"Streaming workflow failed: {e}, status code: {status.status_code}, response: {status.text}")
        raise

def parse_codex_chat_history(chat_content: str) -> Tuple[List, List]:
    """
    Parse Codex chat history from NDJSON format to plain text.
    
    Args:
        chat_content: Raw chat history string in NDJSON format.
    Returns:
        Formatted chat history as plain text.
    """
    lines = chat_content.strip().split('\n')
    agent_output = []
    agent_behavior_log = []
    seen_user_messages = set()
    call_commands = {}

    def _content_items_to_text(content_items) -> str:
        if isinstance(content_items, str):
            return content_items
        if not isinstance(content_items, list):
            return ""
        parts = []
        for content_item in content_items:
            if not isinstance(content_item, dict):
                continue
            if content_item.get("type") in {"output_text", "text", "input_text"}:
                text = content_item.get("text", "")
                if text:
                    parts.append(text)
        return "\n".join(parts)

    def _normalise_command(command_raw) -> str:
        if isinstance(command_raw, list):
            if len(command_raw) >= 3 and command_raw[0] in {"bash", "/bin/bash"} and command_raw[1] == "-lc":
                return str(command_raw[2])
            return " ".join(map(str, command_raw))
        if command_raw is None:
            return ""
        return str(command_raw)
    
    for line in lines:
        if not line.strip():
            continue
            
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
            
        msg_type = entry.get("type")
        payload = entry.get("payload", {})
        
        # 1. Handle User Messages
        # Codex logs separate the raw context injection (response_item) from the actual user prompt (event_msg)
        if msg_type == "event_msg" and payload.get("type") == "user_message":
            user_text = payload.get("message", "")
            if user_text and user_text not in seen_user_messages:
                seen_user_messages.add(user_text)
                agent_output.append(ChatMessage(role="user", content=user_text))
                
        # 2. Handle Assistant Actions and Responses
        elif msg_type == "response_item":
            item_type = payload.get("type")

            # Codex can also store user/developer messages as response_item
            # entries.  Keep user messages here too when event_msg is absent,
            # but avoid duplicating the same prompt.
            if item_type == "message" and payload.get("role") == "user":
                text = _content_items_to_text(payload.get("content", []))
                if text and text not in seen_user_messages:
                    seen_user_messages.add(text)
                    agent_output.append(ChatMessage(role="user", content=text))
                continue
            
            # A. Assistant Text (Thinking or Final Response)
            if item_type == "message" and payload.get("role") == "assistant":
                text = _content_items_to_text(payload.get("content", []))
                if text:
                    agent_output.append(ChatMessage(role="assistant", content=text))

            # B. Tool Calls (Shell commands, Plan updates)
            elif item_type == "function_call":
                tool_name = payload.get("name")
                call_id = payload.get("call_id")
                
                # Parse arguments (they are stored as a JSON string)
                try:
                    args = json.loads(payload.get("arguments", "{}"))
                except json.JSONDecodeError:
                    args = {}
                
                # Handling 'update_plan' - Matches screenshot "Updated Plan"
                if tool_name == "update_plan":
                    explanation = args.get("explanation", "")
                    # Create a formatted block for the plan
                    plan_display = f"**Updated Plan**\nL {explanation}"
                    
                    # Optional: Add specific steps if needed
                    steps = args.get("plan", [])
                    if steps:
                        plan_display += "\n" + "\n".join([f"  - [{s.get('status')}] {s.get('step')}" for s in steps])
                        
                    agent_output.append(ChatMessage(role="assistant", content=plan_display))
                    agent_behavior_log.append(f"Tool: update_plan | Explanation: {explanation}")

                # Handling shell command tool names from different Codex
                # versions: older logs use "shell" with {"command": ...};
                # current logs use "exec_command" with {"cmd": ...}.
                elif tool_name in {"shell", "exec_command", "exec"}:
                    command_str = _normalise_command(args.get("command") if "command" in args else args.get("cmd"))
                    if call_id:
                        call_commands[call_id] = command_str
                    agent_output.append(ChatMessage(role="assistant", content=f"**Ran** `{command_str}`"))
                    agent_behavior_log.append(f"Tool: {tool_name} | Command: {command_str}")
                elif tool_name == "write_stdin":
                    # Ongoing command polling is not a new agent command; it
                    # otherwise pollutes COMMANDS_EXECUTED statistics.
                    continue
                elif tool_name:
                    agent_behavior_log.append(f"Tool: {tool_name} | Input: {str(args)[:500]}")

            # C. Tool Outputs (Terminal output)
            elif item_type == "function_call_output":
                # The 'output' field in payload is often a JSON string containing the stdout/metadata
                raw_output_str = payload.get("output", "")
                
                try:
                    # Some tool outputs are JSON strings containing "output";
                    # Codex exec_command outputs are often already plain text.
                    inner_data = json.loads(raw_output_str)
                    if isinstance(inner_data, dict):
                        terminal_output = inner_data.get("output", raw_output_str)
                    else:
                        terminal_output = str(inner_data)
                except json.JSONDecodeError:
                    terminal_output = raw_output_str

                if terminal_output is None:
                    terminal_output = ""
                if not str(terminal_output).strip():
                    terminal_output = "(no output)"

                # Append the output to history
                if terminal_output:
                    call_id = payload.get("call_id")
                    command_prefix = ""
                    if call_id in call_commands:
                        command_prefix = f"$ {call_commands[call_id]}\n"
                    # Truncate slightly if massive, matching typical history viewers
                    terminal_output = str(terminal_output)
                    display_output = terminal_output[:2000] + "..." if len(terminal_output) > 2000 else terminal_output
                    display_output = command_prefix + display_output
                    agent_output.append(ChatMessage(role="assistant", content=f"```\n{display_output}\n```"))
    return agent_output, agent_behavior_log

import json
import re

def extract_json_robust(text):
    """
    Robustly extracts JSON from an LLM response, handling Markdown fences,
    extraneous text, and common syntax errors like escaped single quotes.
    """
    # 1. Strip outer string quotes if the input is a Python raw string representation
    if text.strip().startswith("'") and text.strip().endswith("'"):
        text = text.strip()[1:-1]
        # Fix literal newline characters if they were escaped in the raw string
        text = text.replace('\\n', '\n') 

    # 2. Attempt to extract the content inside ```json ... ``` or just ``` ... ```
    # This regex looks for code blocks containing curly braces
    pattern = r"```(?:json)?\s*(\{.*?\})\s*```"
    match = re.search(pattern, text, re.DOTALL)
    
    candidate = ""
    if match:
        candidate = match.group(1)
    else:
        # Fallback: Find the first open brace and the last close brace
        start = text.find('{')
        end = text.rfind('}')
        if start != -1 and end != -1 and end > start:
            candidate = text[start:end+1]
    
    if not candidate:
        return _fallback_object(text)

    # 3. Sanitize the candidate string (Crucial Step)
    # LLMs often output \' (Python style) instead of ' (JSON style) inside strings.
    # This causes JSONDecodeError: Invalid \escape
    candidate = candidate.replace(r"\'", "'")
    
    # 4. Attempt to parse
    try:
        # strict=False allows control characters like newlines inside strings
        return json.loads(candidate, strict=False)
    except json.JSONDecodeError:
        # 5. Last Resort: Try to clean trailing commas (another common LLM error)
        try:
            candidate_clean = re.sub(r",\s*([\]}])", r"\1", candidate)
            return json.loads(candidate_clean, strict=False)
        except Exception:
            return _fallback_object(text)

def _fallback_object(raw_text):
    return {
        "payload_content": raw_text.strip(),
        "injection_type": "append",
        "match_pattern": "",
        "target_file_path": None,
    }
