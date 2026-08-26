# agent/playwright_agent.py
import os
import json
import time
from typing import Any, Dict
import yaml
import pdb
import datetime
import requests
import sseclient
from pathlib import Path
import traceback
import base64
import logging

from ..environment_manager import EnvironmentManager
from ..utils.util import extract_messages_and_logs, extract_attacker_server_log
from ..custom_types import TaskState, AgentConfig
from ..vm_manager import execute_workflow_stream

from ..utils.others import retry_sync, get_container_file_content
from ..utils.get_model_api import get_model_api

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)

async def vm_solve(
    *,
    state: TaskState, 
    agent: AgentConfig,
    vm_config_path: str,
    manager: EnvironmentManager,
    screenshot_time: float | None = None,
    vm=None,  # NEW: Accept VMInstance directly
    frame_queue=None,
    main_loop=None,
    log_level: str = "INFO",
    debug_port: int = -1,
    stream_screenshots: bool = True,
    stream_logs: bool = True,
    **kwargs
) -> TaskState:
    target_name = agent.software
    safe_sample_id = "".join(c if c.isalnum() or c in "._-" else "_" for c in state.sample.id)[:180]
    sample_artifact_dir = Path(manager.log_path) / "samples" / safe_sample_id
    sample_artifact_dir.mkdir(parents=True, exist_ok=True)
    workflow_log_path = sample_artifact_dir / "workflow.log"

    def workflow_log(level: str, message: str) -> None:
        timestamp = datetime.datetime.now().isoformat(timespec="milliseconds")
        with workflow_log_path.open("a", encoding="utf-8") as handle:
            handle.write(f"[{timestamp}] {level} {message}\n")
        LOGGER.info("[%s] %s", level, message)
    
    # Support both new (vm) and old (vm_ip/headers) interfaces for compatibility
    if vm is not None:
        # New interface: use VMInstance
        vm_ip = vm.session_info.ip
        headers = vm.session_info.headers
        BASE_URL = vm.session_info.base_url
        ssh_port = vm.session_info.ssh_port
        api_client = vm.api_client
    else:
        # Old interface: fallback to kwargs
        vm_ip = kwargs.get("vm_ip", 'localhost')
        headers = kwargs.get("headers", {})
        BASE_URL = f"http://{vm_ip}:{manager.code_server.ports['8000/tcp']}/api/v1"
        if not headers:
            def acquire_session():
                response = requests.post(f"{BASE_URL}/session/acquire")
                acquired_data = response.json()
                headers = {
                    "X-Session-Token": acquired_data['token'],
                    "Content-Type": "application/json"
                }
                return headers
            headers = retry_sync(acquire_session, max_attempts=5, delay=2.0)
        api_client = None  # Will use raw requests
    
    attempts = 0
    sample_id = state.sample.id
    try:
        pause_before_prompt_seconds = max(0, int(os.getenv("CC_PAUSE_BEFORE_PROMPT_SECONDS", "0")))
    except ValueError:
        LOGGER.warning("Invalid CC_PAUSE_BEFORE_PROMPT_SECONDS; continuing without a pause")
        pause_before_prompt_seconds = 0


    # The automation server constructs an OpenAI client from the registered
    # extension YAML before executing any workflow. Keep published YAML files
    # credential-free, but provide that server with an ephemeral, per-run
    # OpenAI-compatible credential at registration time. This is intentionally
    # separate from the evaluated agent's workflow credential: Claude Code can
    # use CHEAP_* while automation_server uses AUTOMATION_SERVER_OPENAI_* (or
    # CODEX_* as its fallback).
    registration_yaml = agent.yaml
    try:
        registration_config = yaml.safe_load(agent.yaml or "")
        if not isinstance(registration_config, dict):
            raise ValueError("agent YAML is not a mapping")
        automation_api_key = (
            os.getenv("AUTOMATION_SERVER_OPENAI_API_KEY")
            or os.getenv("CODEX_API_KEY")
            or agent.model.api_key
        )
        automation_base_url = (
            os.getenv("AUTOMATION_SERVER_OPENAI_BASE_URL")
            or os.getenv("CODEX_BASE_URL")
            or agent.model.base_url
        )
        registration_config["llm_api_key"] = automation_api_key or ""
        registration_config["llm_base_url"] = automation_base_url or ""
        registration_yaml = yaml.safe_dump(registration_config, allow_unicode=True, sort_keys=False)
        LOGGER.info(
            "Registering %s with automation-server LLM credentials: key_present=%s base_url_present=%s",
            target_name,
            bool(automation_api_key),
            bool(automation_base_url),
        )
    except Exception as exc:
        LOGGER.warning("Could not prepare runtime automation-server config: %s", exc)

    LOGGER.info(f"Posting extension registration for {target_name} with {f"{BASE_URL}/extensions/register"}...")
    
    if api_client:
        response_data = api_client.upload_file(
            filename="settings.json",
            content=json.dumps(agent.ide_settings or state.sample.ide_settings or {}, indent=2),
            dir_path="C:\\automation_server_appium\\data\\User"
        )
        response_data = api_client.upload_ssh_config(port=ssh_port)
        # Use VMAPIClient built-in method
        response_data = api_client.register_extension(
            yaml_config=registration_yaml,
            overwrite=True
        )
        LOGGER.info(f"Register response: success={response_data.get('success')}")
    else:
        # Fallback to raw requests
        response = requests.post(
            f"{BASE_URL}/extensions/register",
            json={"yaml_config": registration_yaml, "overwrite": True},
            headers=headers,
            timeout=60
        )
        LOGGER.info(f"Register response: {response.status_code}, response.json: {response.json()['success']}")
    time.sleep(3)
    if api_client:
        # Use VMAPIClient built-in method
        response_data = api_client.execute_workflow_stream(
            target_name=target_name,
            workflow="prepare_vscode",
            params={
                "executable_path": agent.executable_path,
                "workspace_path": agent.remote_target_arg,
                "screenshot_time": screenshot_time or 1.0
            },
            log_level=log_level,
            on_log=workflow_log,
            on_complete=None,
            on_error=None,
            frame_queue=frame_queue,
            main_loop=main_loop,
            stream_screenshots=stream_screenshots and frame_queue is not None,
            stream_logs=stream_logs,
        )
        LOGGER.info(f"Prepare VS Code: success={response_data.get('outputs', {}).get('started', False)}")
        started = response_data.get("outputs", {}).get("started", False)
    else:
        started = True
    attempts += 1
    retry_needed = False

    result_entry = {
        "id": sample_id,
        "input": state.sample.user_instruction,
        "metadata": state.sample.metadata,
        "response": None,
        "chat_history": None,
        "error": None
    }
    # pdb.set_trace()
            
    if started:
        LOGGER.info(f"Processing {sample_id}...")
        
        try:
            if api_client:
                # Use VMAPIClient built-in streaming method
                outputs = None
                workflow_error = None
                proxy_url = manager.https_proxy
                LOGGER.info("IDE workflow proxy configured: %s", bool(proxy_url))
                
                try:
                    result = api_client.execute_workflow_stream(
                        target_name=target_name,
                        workflow="send_and_export",
                        log_level=log_level,
                        max_jumps=1000,
                        params={
                            "message": state.sample.user_instruction,
                            "model": agent.model.model_name,
                            "api_key": agent.model.api_key,
                            "api_base_url": agent.model.base_url,
                            "timeout_seconds": 1200,
                            "pause_before_prompt_seconds": pause_before_prompt_seconds,
                            "chat_file_name": f"chat_{sample_id}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}",
                            "export_directory": agent.export_dir
                        },
                        proxy_url=proxy_url,
                        on_log=workflow_log,
                        on_complete=None,
                        on_error=None,
                        frame_queue=frame_queue,
                        main_loop=main_loop,
                        stream_screenshots=stream_screenshots and frame_queue is not None,
                        stream_logs=stream_logs,
                    )
                    
                    if result.get('success'):
                        outputs = result.get('outputs', {})
                        LOGGER.info("Workflow completed successfully!")
                    else:
                        workflow_error = result.get('error', 'Unknown error')
                        LOGGER.info(f"Workflow failed: {workflow_error}")
                        
                except Exception as e:
                    workflow_error = str(e)
                    LOGGER.error(f"Workflow execution failed: {e}")
                
                if outputs is not None:
                    result_entry["response"] = {"success": True, "outputs": outputs}
                    result_entry["success"] = True
                    result_entry["status_code"] = 200
                    
                    # Extract chat history if available
                    if "chat_history" in outputs:
                        chat_history = outputs["chat_history"]
                        if "error" not in chat_history:
                            content = chat_history.get("content", "")
                            result_entry["chat_history"] = content.decode("utf-8", errors="ignore") if isinstance(content, bytes) else content
                        else:
                            LOGGER.info(f"    Chat History Error: {chat_history.get('error')}")
                            result_entry["error"] = chat_history.get("error")
                            result_entry["success"] = False
                    if "time_record" in outputs:
                        result_entry["time_record"] = outputs["time_record"]
                    
                    LOGGER.info(f"    Success: {result_entry['success']}")
                elif workflow_error:
                    result_entry["error"] = workflow_error
                    result_entry["success"] = False
            else:
                # Use standalone function
                outputs = None
                workflow_error = None
                
                try:
                    result = execute_workflow_stream(
                        url=f"{BASE_URL}/extensions/{target_name}/workflow/stream",
                        json_payload={
                            "workflow": "send_and_export",
                            "log_level": log_level,
                            "max_jumps": -1,
                            "debug_port": 4444 if debug_port != -1 else -1,
                            "stream_screenshots": stream_screenshots and frame_queue is not None,
                            "stream_logs": stream_logs,
                            "params": {
                                "model": agent.model.model_name,
                                "api_key": agent.model.api_key,
                                "api_base_url": agent.model.base_url,
                                "message": state.sample.user_instruction,
                                "timeout_seconds": 1200,
                                "pause_before_prompt_seconds": pause_before_prompt_seconds,
                                "chat_file_name": f"chat_{sample_id}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}",
                                "export_directory": agent.export_dir
                            }
                        },
                        headers=headers,
                        on_log=lambda level, msg: LOGGER.info(f"[{level}] {msg}"),
                        on_complete=None,
                        on_error=None,
                        frame_queue=frame_queue,
                        main_loop=main_loop,
                        stream_screenshots=stream_screenshots and frame_queue is not None,
                        stream_logs=stream_logs,
                        timeout=(60, 150)
                    )
                    
                    if result.get('success'):
                        outputs = result.get('outputs', {})
                        LOGGER.info("Workflow completed successfully!")
                    else:
                        workflow_error = result.get('error', 'Unknown error')
                        LOGGER.info(f"Workflow failed: {workflow_error}")
                        
                except Exception as e:
                    workflow_error = str(e)
                    LOGGER.error(f"Workflow execution failed: {e}")
                
                result_entry.update({"status_code": 200 if outputs else 500})
                
                if outputs is not None:
                    result_entry["response"] = {"success": True, "outputs": outputs}
                    result_entry["success"] = True
                    
                    # Extract chat history if available
                    if "chat_history" in outputs:
                        chat_history = outputs["chat_history"]
                        if isinstance(chat_history, str):
                            raise ValueError(f"chat_history should be a dict, got str. {chat_history=}" )
                        elif "error" not in chat_history:
                            content = chat_history.get("content", "")
                            result_entry["chat_history"] = content.decode("utf-8", errors="ignore") if isinstance(content, bytes) else content
                        else:
                            LOGGER.info(f"    Chat History Error: {chat_history.get('error')}")
                            result_entry["error"] = chat_history.get("error")
                            result_entry["success"] = False
                    if "time_record" in outputs:
                        result_entry["time_record"] = outputs["time_record"]
                    
                    LOGGER.info(f"    Success: {result_entry['success']}")
                elif workflow_error:
                    result_entry["error"] = workflow_error
                    result_entry["success"] = False
                    LOGGER.info(f"    Workflow Error: {workflow_error}")
            
            # Small delay between requests
            time.sleep(2)
            
        except Exception as e:
            traceback.print_exception(e)
            LOGGER.info(f"    Exception: {e}")
    else:
        retry_needed = True

    # Close VS Code with retry logic for transient errors
    # Note: If connection is refused, it likely means the container was already cleaned up (e.g., task cancelled)
    try:
        if api_client:
            # Use VMAPIClient built-in method
            def close_vscode_request():
                resp_data = api_client.close_vscode(
                    target_name=target_name,
                    force=True
                )
                if not resp_data.get('success'):
                    raise Exception(f"Close VS Code failed: {resp_data.get('error', 'Unknown error')}")
                return resp_data
            
            response_data = retry_sync(
                close_vscode_request,
                max_attempts=5,
                delay=2.0,
                exceptions=(requests.exceptions.RequestException, Exception)
            )
            LOGGER.info(f"\nClose VS Code: success={response_data.get('success')}")
        else:
            # Fallback to raw requests
            def close_vscode_request():
                resp = requests.post(
                    f"{BASE_URL}/extensions/{target_name}/workflow",
                    json={
                        "workflow": "close_session",
                    },
                    headers=headers,
                    timeout=60
                )
                # Raise exception if not successful to trigger retry
                if resp.status_code not in [200, 201]:
                    raise Exception(f"Close VS Code failed with status {resp.status_code}: {resp.text}")
                return resp
            
            if manager.environments.get("code_server").container is not None:
                response = retry_sync(
                    close_vscode_request,
                    max_attempts=5,
                    delay=2.0,
                    exceptions=(requests.exceptions.RequestException, Exception)
                )
                LOGGER.info(f"\nClose {target_name}: {response.status_code}")
    except (requests.exceptions.ConnectionError, ConnectionRefusedError) as e:
        # Connection refused usually means the container is already stopped (e.g., task was cancelled)
        LOGGER.info(f"ℹ️  VSCode cleanup skipped - container already removed (Connection refused)")
    except Exception as e:
        # Log other errors but don't fail the entire task
        LOGGER.warning(f"⚠️  Failed to close VSCode cleanly: {e}")
    if not result_entry.get("success", False):
        raise Exception("IDE interaction failed.")
    
    # Get trace file content from container and process it
    # try:
    #     trace_content = get_container_file_content(
    #         container=manager.code_server.container,
    #         file_path="/tmp/raw_trace.jsonl"
    #     )
    #     with open(f"traces_{agent.software}_raw.jsonl", "w") as f:
    #         f.write(trace_content)
    #     state.traces = extract_trace(content=trace_content, filter_for_trace=agent.filter_for_trace or {})
    # except Exception as e:
    #     LOGGER.warning(f"Failed to extract trace: {e}")
    #     state.traces = []
    # pdb.set_trace()
    state.chat_history = result_entry.get("chat_history", "")
    state.chat_history = state.chat_history.replace("\x00", "") if state.chat_history else state.chat_history
    state.messages, state.commands_executed = extract_messages_and_logs(state.chat_history, target_name=target_name, manager=manager, filter_for_trace=agent.filter_for_trace or {})
    state.web_server_log = extract_attacker_server_log(state.env_state.running_environments['web_server'].ports['8081/tcp'])


    return state
