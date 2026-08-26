"""API routes for the automation server."""
from typing import Dict
import base64
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form, Header
from typing import Optional
import time
import uuid
import os
from fastapi.responses import JSONResponse, StreamingResponse
import logging
import json
import asyncio
from queue import Queue
import threading

import yaml

from .models import (
    InputRequest, ActionRequest, WorkflowRequest,
    HealthResponse, ExtensionListResponse, ExtensionInfo,
    ActionResponse, WorkflowResponse, StateResponse,
    HistoryResponse, HistoryItem, InputResponse, ActivateResponse,
    ErrorResponse, DynamicWorkflowRequest, DynamicStepsRequest,
    DynamicExecutionResponse, RegisterExtensionRequest,
    RegisterExtensionResponse, UnregisterExtensionResponse,
)
from ..config import config_loader, ExtensionConfig
from ..config.schema import ActionStep
from ..core import ActionExecutor
import ctypes
import os

def disable_quick_edit():
    """
    Disables Windows Console 'QuickEdit Mode' to prevent server freezing.
    When QuickEdit is enabled, clicking in the console pauses process execution
    until 'Enter' is pressed.
    """
    if os.name == 'nt': # Only run on Windows
        try:
            kernel32 = ctypes.windll.kernel32
            # STD_INPUT_HANDLE = -10
            hInput = kernel32.GetStdHandle(-10)
            
            mode = ctypes.c_ulong()
            if kernel32.GetConsoleMode(hInput, ctypes.byref(mode)):
                # ENABLE_QUICK_EDIT_MODE = 0x0040
                # ENABLE_INSERT_MODE = 0x0020
                # We perform a bitwise AND with the complement to turn these bits OFF
                mode.value &= ~(0x0040 | 0x0020)
                
                kernel32.SetConsoleMode(hInput, mode)
                logging.info("Windows QuickEdit Mode disabled successfully.")
        except Exception as e:
            logging.error(f"Failed to disable QuickEdit: {e}")

# Call this immediately when the module loads
disable_quick_edit()

logger = logging.getLogger(__name__)

router = APIRouter()

# Cache for executors
_executors: Dict[str, ActionExecutor] = {}

# ============ Session State Management ============
_session_lock = threading.Lock()
_active_session_token: str | None = None
_last_activity_time: float = 0.0
_cancellation_events: Dict[str, threading.Event] = {}

# If a client doesn't send a request for 10 minutes, force release the lock
SESSION_TIMEOUT_SECONDS = 1800 

def update_activity():
    """Updates the timestamp to prevent timeout."""
    global _last_activity_time
    _last_activity_time = time.time()

async def verify_session_token(x_session_token: str = Header(None)):
    """
    Dependency to enforce session locking.
    Add this to any endpoint that requires exclusive access.
    """
    global _active_session_token, _last_activity_time
    
    with _session_lock:
        current_time = time.time()
        
        # 1. Check if a session exists and has timed out
        if _active_session_token and (current_time - _last_activity_time > SESSION_TIMEOUT_SECONDS):
            logger.warning(f"Session {_active_session_token} timed out. Resetting.")
            _active_session_token = None
            
        # 2. If no session is active, we reject 'action' requests. 
        # The client MUST call /session/acquire first.
        if not _active_session_token:
            raise HTTPException(
                status_code=403, 
                detail="No active session. Please call /session/acquire first."
            )
            
        # 3. Check if the provided token matches the active token
        if x_session_token != _active_session_token:
            raise HTTPException(
                status_code=403, 
                detail="VM is locked by another session."
            )
            
        # 4. Success - Update activity time
        _last_activity_time = current_time
        return _active_session_token

class SSELogHandler(logging.Handler):
    """Custom log handler that captures logs into a queue for SSE streaming."""
    
    def __init__(self, log_queue: Queue):
        super().__init__()
        self.log_queue = log_queue
        
    def emit(self, record):
        try:
            log_entry = {
                "timestamp": record.created,
                "level": record.levelname,
                "logger": record.name,
                "message": self.format(record)
            }
            self.log_queue.put(log_entry)
        except Exception:
            self.handleError(record)


def get_vscode_controller(proxy_url: Optional[str] = None):
    """Dependency to get the VS Code controller (lazy-loaded for IDE mode only)."""
    try:
        from ..core.controller import get_controller
        return get_controller(proxy_url=proxy_url)
    except ImportError as e:
        raise HTTPException(
            status_code=503, 
            detail="IDE controller not available. This server is running in CLI-only mode."
        )


def get_cli_controller():
    """Lazy-load CLI controller (only when needed)."""
    try:
        from ..core.cli_controller import get_cli_controller as _get_cli_controller
        return _get_cli_controller()
    except ImportError as e:
        raise HTTPException(
            status_code=503, 
            detail="CLI controller not available. This server is running in IDE-only mode."
        )


def get_connected_controller():
    """Dependency to get a connected VS Code controller (for endpoints that require it)."""
    controller = get_vscode_controller()
    if not controller.ensure_connected():
        raise HTTPException(status_code=503, detail="Cannot connect to VS Code")
    return controller


def get_executor(extension_name: str, logger=None, proxy_url=None) -> ActionExecutor:
    """Get or create an executor for an extension."""
    if extension_name not in _executors:
        config = config_loader.get_extension(extension_name)
        if not config:
            raise HTTPException(status_code=404, detail=f"Extension '{extension_name}' not found")
        
        # Only pass the controller needed for this driver type
        driver_type = getattr(config, 'driver', 'ide')
        if driver_type == 'cli':
            _executors[extension_name] = ActionExecutor(config, cli_controller=get_cli_controller(), logger_instance=logger)
        else:
            controller = get_vscode_controller(proxy_url=proxy_url)  # Lazy-load only when needed
            _executors[extension_name] = ActionExecutor(config, controller=controller, logger_instance=logger)
    return _executors[extension_name]

# ============ Session Endpoints ============

@router.post("/session/acquire")
async def acquire_session():
    """
    Locks the VM for exclusive use. Returns a session token.
    If the VM is already locked by someone else, returns 409 Conflict.
    """
    global _active_session_token, _last_activity_time
    
    with _session_lock:
        current_time = time.time()
        
        # Check if currently locked and NOT timed out
        if _active_session_token and (current_time - _last_activity_time < SESSION_TIMEOUT_SECONDS):
            raise HTTPException(
                status_code=409, 
                detail="VM is currently busy with another session."
            )
            
        # Generate new token
        new_token = str(uuid.uuid4())
        _active_session_token = new_token
        _last_activity_time = current_time

        _cancellation_events[new_token] = threading.Event()
        
        logger.info(f"Session acquired. Token: {new_token}")
        return {"success": True, "token": new_token}

@router.post("/session/release")
async def release_session(x_session_token: str = Header(...)):
    """
    Releases the VM lock. 
    Only the owner of the token can release it.
    """
    global _active_session_token
    
    with _session_lock:
        if not _active_session_token:
            return {"success": True, "message": "Session was already empty"}
            
        if x_session_token != _active_session_token:
            raise HTTPException(status_code=403, detail="Invalid token for release")
        
        if _active_session_token in _cancellation_events:
            del _cancellation_events[_active_session_token]
            
        _active_session_token = None
        logger.info("Session released manually.")
        return {"success": True, "message": "Session released"}

@router.get("/session/status")
async def get_session_status():
    """Check if the VM is locked without trying to acquire it."""
    global _active_session_token, _last_activity_time
    is_busy = False
    
    with _session_lock:
        if _active_session_token:
            if time.time() - _last_activity_time < SESSION_TIMEOUT_SECONDS:
                is_busy = True
            else:
                # Lazy cleanup of timed-out session
                _active_session_token = None
                
    return {"busy": is_busy}

@router.post("/session/cancel_execution")
async def cancel_execution(x_session_token: str = Header(...)):
    """
    Signals workflow to stop AND kills the driver connection to unblock I/O.
    """
    # 1. Signal the logical event (for the loop check)
    if x_session_token in _cancellation_events:
        logger.warning(f"🛑 Setting cancellation event for session {x_session_token}")
        _cancellation_events[x_session_token].set()
    else:
        logger.warning(f"No active event found for token {x_session_token}")

    # 2. Force Kill the Driver (The "Immediate" Stop)
    # This ensures that if the thread is stuck in `driver.find_element(...)`, 
    # it immediately raises a MaxRetryError / WebDriverException.
    try:
        from ..core.controller import get_controller
        controller = get_controller()
        # Check if connected before trying to quit to avoid null errors
        if controller: 
            logger.warning("🔌 Forcing Appium Driver Quit to interrupt active step...")
            # Assuming controller.quit() calls self.driver.quit()
            controller.quit() 
        try:
            cli_controller = get_cli_controller()
            cli_controller.terminate()
            logger.warning("🛑 CLI controller terminated for cancellation")
        except Exception as cli_err:
            logger.error(f"Failed to terminate CLI controller: {cli_err}")
    except Exception as e:
        logger.error(f"Error while forcing driver quit: {e}")

    return {"success": True, "message": "Cancellation signal sent and driver terminated"}

@router.post("/upload_file")
async def upload_file(
    file: UploadFile = File(...),
    dir_path: str = Form("uploads")
):
    """Accept a file upload and save it to a directory, creating the directory if it doesn't exist."""
    try:
        os.makedirs(dir_path, exist_ok=True)
        file_location = os.path.join(dir_path, file.filename)
        with open(file_location, "wb") as f:
            content = await file.read()
            f.write(content)
        return JSONResponse(content={"success": True, "filename": file.filename, "directory": dir_path})
    except Exception as e:
        return JSONResponse(content={"success": False, "error": str(e)}, status_code=500)


@router.post("/upload_file_json")
async def upload_file_json(request: dict):
    """Accept a file upload via JSON with base64-encoded content."""
    try:
        import base64
        
        filename = request.get("filename")
        file_content_b64 = request.get("content")  # base64 encoded
        dir_path = request.get("dir_path", "uploads")
        
        if not filename or not file_content_b64:
            return JSONResponse(
                content={"success": False, "error": "Missing 'filename' or 'content'"},
                status_code=400
            )
        
        os.makedirs(dir_path, exist_ok=True)
        file_location = os.path.join(dir_path, filename)
        
        # Decode base64 content
        file_content = base64.b64decode(file_content_b64)
        
        with open(file_location, "wb") as f:
            f.write(file_content)
        
        return JSONResponse(
            content={"success": True, "filename": filename, "directory": dir_path}
        )
    except Exception as e:
        return JSONResponse(content={"success": False, "error": str(e)}, status_code=500)

@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Check server health and VS Code connection."""
    try:
        from ..core.controller import get_controller
        controller = get_controller()
        connected = controller.is_connectable()
    except ImportError:
        # CLI-only mode, no IDE controller available
        connected = False
    
    extensions = config_loader.list_extensions()
    
    return HealthResponse(
        status="healthy" if connected else "degraded",
        vscode_connected=connected,
        extensions_loaded=len(extensions),
    )


@router.get("/extensions/{name}", response_model=ExtensionInfo)
async def get_extension(name: str):
    """Get information about a specific extension."""
    config = config_loader.get_extension(name)
    if not config:
        raise HTTPException(status_code=404, detail=f"Extension '{name}' not found")
    
    return ExtensionInfo(
        name=config.name,
        display_name=config.display_name,
        version=config.version,
        selectors=list(config.selectors.keys()),
        actions=list(config.actions.keys()),
        workflows=list(config.workflows.keys()),
        state_queries=list(config.state.keys()),
    )


# ============ Extension Registration ============

@router.post("/extensions/register", response_model=RegisterExtensionResponse)
async def register_extension(request: RegisterExtensionRequest, token: str = Depends(verify_session_token)):
    """
    Register a new extension from YAML configuration.
    
    After registration, the extension can be used with all standard endpoints:
    - POST /extensions/{name}/activate
    - POST /extensions/{name}/input
    - POST /extensions/{name}/action
    - POST /extensions/{name}/workflow
    - GET /extensions/{name}/state
    - GET /extensions/{name}/history
    
    Example YAML:
    ```yaml
    name: my_extension
    display_name: My Extension
    version: "1.0"
    
    selectors:
      activation:
        method: child_window
        criteria:
          title: "My Extension"
          control_type: "TabItem"
      input:
        method: child_window
        criteria:
          control_type: "Edit"
      send_button:
        method: child_window
        criteria:
          title: "Send"
          control_type: "Button"
    
    actions:
      click_send:
        steps:
          - type: click
            target: send_button
    
    workflows:
      send_message:
        parameters:
          - name: message
            required: true
        steps:
          - type: input
            target: input
            value: "{{message}}"
          - type: click
            target: send_button
    ```
    """
    try:
        # Parse YAML
        data = yaml.safe_load(request.yaml_config)
        
        if 'name' not in data:
            return RegisterExtensionResponse(
                success=False,
                name="",
                message="",
                error="Extension YAML must include 'name' field"
            )
        
        ext_name = data['name']
        
        # Check if already exists
        if config_loader.extension_exists(ext_name) and not request.overwrite:
            return RegisterExtensionResponse(
                success=False,
                name=ext_name,
                message="",
                error=f"Extension '{ext_name}' already exists. Set overwrite=true to replace."
            )
        
        # Register the extension
        config = config_loader.register_extension_from_yaml(request.yaml_config)
        
        # Clear cached executor if overwriting
        if ext_name in _executors:
            del _executors[ext_name]
        
        return RegisterExtensionResponse(
            success=True,
            name=config.name,
            message=f"Extension '{config.name}' registered successfully",
            selectors=list(config.selectors.keys()),
            actions=list(config.actions.keys()),
            workflows=list(config.workflows.keys()),
        )
        
    except yaml.YAMLError as e:
        return RegisterExtensionResponse(
            success=False,
            name="",
            message="",
            error=f"YAML parse error: {e}"
        )
    except Exception as e:
        logger.exception("Failed to register extension")
        return RegisterExtensionResponse(
            success=False,
            name="",
            message="",
            error=str(e)
        )


@router.delete("/extensions/{name}", response_model=UnregisterExtensionResponse)
async def unregister_extension(name: str, token: str = Depends(verify_session_token)):
    """
    Unregister/remove an extension.
    
    This removes the extension from the server's registry.
    Note: This does not delete any YAML files on disk.
    """
    try:
        if not config_loader.extension_exists(name):
            return UnregisterExtensionResponse(
                success=False,
                name=name,
                message="",
                error=f"Extension '{name}' not found"
            )
        
        # Remove from config loader
        config_loader.unregister_extension(name)
        
        # Clear cached executor
        if name in _executors:
            del _executors[name]
        
        return UnregisterExtensionResponse(
            success=True,
            name=name,
            message=f"Extension '{name}' unregistered successfully"
        )
        
    except Exception as e:
        logger.exception(f"Failed to unregister extension {name}")
        return UnregisterExtensionResponse(
            success=False,
            name=name,
            message="",
            error=str(e)
        )


@router.post("/extensions/{name}/action", response_model=ActionResponse)
async def execute_action(
    name: str,
    request: ActionRequest,
    token: str = Depends(verify_session_token)
):
    """Execute a named action for an extension."""
    try:
        executor = get_executor(name)
        outputs = executor.execute_action(request.action, request.params)
        
        return ActionResponse(
            success=True,
            action=request.action,
            outputs=outputs,
        )
    except ValueError as e:
        return ActionResponse(success=False, action=request.action, error=str(e))
    except Exception as e:
        logger.exception(f"Failed to execute action {request.action}")
        return ActionResponse(success=False, action=request.action, error=str(e))


@router.post("/extensions/{name}/workflow", response_model=WorkflowResponse)
async def execute_workflow(
    name: str,
    request: WorkflowRequest,
    token: str = Depends(verify_session_token)
):
    """Execute a workflow for an extension."""
    try:
        executor = get_executor(name, proxy_url=request.proxy_url)
        outputs = executor.execute_workflow(request.workflow, request.params)
        
        return WorkflowResponse(
            success=True,
            workflow=request.workflow,
            outputs=outputs,
        )
    except ValueError as e:
        return WorkflowResponse(success=False, workflow=request.workflow, error=str(e))
    except Exception as e:
        logger.exception(f"Failed to execute workflow {request.workflow}")
        return WorkflowResponse(success=False, workflow=request.workflow, error=str(e))


@router.post("/extensions/{name}/workflow/stream")
async def execute_workflow_stream(
    name: str,
    request: WorkflowRequest,
    token: str = Depends(verify_session_token)
):
    """Execute a workflow and stream logs in real-time via Server-Sent Events (SSE)."""
    
    async def event_generator():
        event_queue = Queue()
        executor_logger = logging.getLogger("automation_server.core.executor")
        
        # Add SSE handler to capture logs only when live log streaming is enabled.
        sse_handler = None
        if request.stream_logs:
            sse_handler = SSELogHandler(event_queue)
            # Set log level from request parameter (both logger and handler must allow the level)
            log_level = getattr(logging, request.log_level.upper(), logging.INFO)
            sse_handler.setLevel(log_level)  # Set the handler's level
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            sse_handler.setFormatter(formatter)
            executor_logger.addHandler(sse_handler)
        
        # Container for outputs
        outputs_container = {}
        error_container = {}
        workflow_done_event = threading.Event()
        screenshot_time_interval = request.screenshot_time or 0.2  # Default to 1 second intervals
        
        # Detect driver type from extension config
        config = config_loader.get_extension(name)
        driver_type = getattr(config, 'driver', 'ide') if config else 'ide'
        use_cli_screenshots = (driver_type == 'cli')

        def run_background_screenshots():
            # Wait briefly for initialization
            time.sleep(1)
            
            # Lazy import GUI dependencies only if needed
            if not use_cli_screenshots:
                import pyautogui
                import io
            
            while not workflow_done_event.is_set():
                try:
                    if use_cli_screenshots:
                        # CLI mode: use terminal renderer
                        cli_ctrl = get_cli_controller()
                        b64_str = cli_ctrl.get_screenshot_base64()
                    else:
                        # IDE mode: use pyautogui for GUI capture
                        buf = io.BytesIO()
                        pyautogui.screenshot().save(buf, format='PNG')
                        image_bytes = buf.getvalue()
                        b64_str = base64.b64encode(image_bytes).decode('utf-8')

                    if b64_str:
                        # Push to shared queue with a custom type marker
                        event_queue.put({
                            "internal_type": "screenshot",
                            "data": b64_str
                        })
                        
                except Exception as e:
                    # Don't crash the thread, just log internal warning
                    print(f"Screenshot capture failed: {e}")
                
                # Interval between screenshots
                time.sleep(screenshot_time_interval)
        
        # Execute workflow in a separate thread
        def run_workflow():
            try:
                executor = get_executor(name)

                stop_event = _cancellation_events.get(token)
                
                outputs = executor.execute_workflow(
                    request.workflow, 
                    params=request.params,
                    max_jumps=request.max_jumps,
                    stop_event=stop_event,
                    debug_port=request.debug_port
                )
                outputs_container['result'] = outputs
            except Exception as e:
                logger.exception(f"Failed to execute workflow {request.workflow}")
                error_container['error'] = str(e)
            finally:
                # <--- CRITICAL FIX: Signal screenshot thread to stop AS SOON as work is done
                workflow_done_event.set() 
        
        workflow_thread = threading.Thread(target=run_workflow)
        screenshot_thread = threading.Thread(target=run_background_screenshots) if request.stream_screenshots else None
        workflow_thread.start()
        if screenshot_thread is not None:
            screenshot_thread.start()
        
        try:
            # Stream logs while workflow is running
            while workflow_thread.is_alive() or (screenshot_thread is not None and screenshot_thread.is_alive()) or not event_queue.empty():
                if not event_queue.empty():
                    item = event_queue.get()
                    # Format as SSE
                    if isinstance(item, dict) and item.get("internal_type") == "screenshot":
                        yield f"data: {json.dumps({'type': 'screenshot', 'data': item['data']})}\n\n"
                    else:
                        # Standard Log
                        yield f"data: {json.dumps({'type': 'log', 'data': item})}\n\n"
                else:
                    await asyncio.sleep(0.1)
            
            # Wait for thread to complete
            workflow_thread.join()
            if screenshot_thread is not None:
                screenshot_thread.join()
            
            # Send final result
            if error_container:
                yield f"data: {json.dumps({'type': 'error', 'error': error_container['error']})}\n\n"
            else:
                yield f"data: {json.dumps({'type': 'complete', 'outputs': outputs_container.get('result', {})})}\n\n"
                
        finally:
            # Remove the SSE handler
            workflow_done_event.set()
            if sse_handler is not None:
                executor_logger.removeHandler(sse_handler)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )


@router.get("/extensions/{name}/state", response_model=StateResponse)
async def get_state(
    name: str,
    token: str = Depends(verify_session_token)
):
    """Get current UI state of an extension."""
    try:
        executor = get_executor(name)
        state = executor.query_state()
        
        return StateResponse(success=True, state=state)
    except Exception as e:
        logger.exception(f"Failed to get state for {name}")
        return StateResponse(success=False, error=str(e))

# ============ Dynamic Execution Endpoints ============
@router.post("/execute/yaml", response_model=DynamicExecutionResponse)
async def execute_yaml(
    request: DynamicWorkflowRequest,
    token: str = Depends(verify_session_token)
):
    """
    Execute a workflow or action defined in inline YAML.
    
    This allows clients to send dynamic configurations without
    pre-registering extension configs on the server.
    
    Example YAML:
    ```yaml
    selectors:
      my_button:
        method: child_window
        criteria:
          title: "Click Me"
          control_type: "Button"
    
    workflows:
      click_and_wait:
        steps:
          - type: click
            target: my_button
          - type: wait
            duration: 1
    ```
    """
    try:
        # Parse YAML config
        config_data = yaml.safe_load(request.yaml_config)
        
        # Create a temporary extension config
        config_data.setdefault('name', '_dynamic')
        config_data.setdefault('version', '1.0')
        
        temp_config = ExtensionConfig(**config_data)
        
        # Only pass the controller needed for this driver type
        driver_type = getattr(temp_config, 'driver', 'ide')
        if driver_type == 'cli':
            executor = ActionExecutor(temp_config, cli_controller=get_cli_controller())
        else:
            controller = get_vscode_controller()  # Lazy-load only for IDE
            executor = ActionExecutor(temp_config, controller=controller)
        
        outputs = {}
        
        # Execute workflow if specified
        if request.workflow:
            if request.workflow not in temp_config.workflows:
                return DynamicExecutionResponse(
                    success=False,
                    error=f"Workflow '{request.workflow}' not found in YAML config"
                )
            outputs = executor.execute_workflow(request.workflow, request.params)
        
        # Execute action if specified
        elif request.action:
            if request.action not in temp_config.actions:
                return DynamicExecutionResponse(
                    success=False,
                    error=f"Action '{request.action}' not found in YAML config"
                )
            outputs = executor.execute_action(request.action, request.params)
        
        else:
            return DynamicExecutionResponse(
                success=False,
                error="Either 'workflow' or 'action' must be specified"
            )
        
        return DynamicExecutionResponse(success=True, outputs=outputs)
        
    except yaml.YAMLError as e:
        return DynamicExecutionResponse(success=False, error=f"YAML parse error: {e}")
    except Exception as e:
        logger.exception("Failed to execute dynamic YAML")
        return DynamicExecutionResponse(success=False, error=str(e))


@router.post("/execute/steps", response_model=DynamicExecutionResponse)
async def execute_steps(
    request: DynamicStepsRequest,
    token: str = Depends(verify_session_token)
):
    """
    Execute a list of steps directly without defining a full workflow.
    
    This is useful for simple, one-off automation tasks.
    
    Example:
    ```json
    {
        "selectors": {
            "input_box": {
                "method": "child_window",
                "criteria": {"control_type": "Edit"}
            }
        },
        "steps": [
            {"type": "click", "target": "input_box"},
            {"type": "input", "target": "input_box", "value": "{{message}}"},
            {"type": "wait", "duration": 1}
        ],
        "params": {"message": "Hello World!"}
    }
    ```
    """
    try:
        from ..core.executor import ExecutionContext
        
        # Build temporary config with selectors
        config_data = {
            'name': '_dynamic_steps',
            'version': '1.0',
            'selectors': request.selectors,
        }
        
        temp_config = ExtensionConfig(**config_data)
        
        # Only pass the controller needed for this driver type
        driver_type = getattr(temp_config, 'driver', 'ide')
        if driver_type == 'cli':
            executor = ActionExecutor(temp_config, cli_controller=get_cli_controller())
        else:
            controller = get_vscode_controller()  # Lazy-load only for IDE
            executor = ActionExecutor(temp_config, controller=controller)
        
        context = ExecutionContext(request.params)
        
        # Execute each step
        for step_data in request.steps:
            step = ActionStep(**step_data)
            executor.execute_step(step, context)
        
        return DynamicExecutionResponse(success=True, outputs=context.outputs)
        
    except Exception as e:
        logger.exception("Failed to execute dynamic steps")
        return DynamicExecutionResponse(success=False, error=str(e))
