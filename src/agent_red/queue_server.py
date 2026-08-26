import pdb
import os
import argparse
import asyncio
import base64
import json
import logging
import uuid
import time
import traceback
import yaml
from pathlib import Path
from collections import defaultdict
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor

from fastapi import (FastAPI, BackgroundTasks, Form, UploadFile, File,
                     HTTPException, APIRouter, WebSocket, WebSocketDisconnect, Response, Request)
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, ConfigDict

# from .redteam_runner import RedTeamRunner
from .utils.container_prep import container_preparation
from .utils.log import TaskLoggingContext
from .engine.runner import RedTeamRunner
from .custom_types import ServerConfig, ExperimentConfig, RunnerResult
from .orchestrator_init import (
    initialize_orchestrator,
    start_scheduler,
    stop_scheduler,
    get_orchestrator,
    acquire_vm_for_session,
    release_vm_session,
)
from .vm_manager import VMInstance
from .scorer import default_scorer

DEFAULT_CORS_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:3001",
    "http://localhost:5173",
    "http://localhost:5174",
]
CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ALLOWED_ORIGINS", ",".join(DEFAULT_CORS_ORIGINS)).split(",")
    if origin.strip()
]

# --- Lifespan Context Manager ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and cleanup resources on app startup and shutdown"""
    # Startup
    logger.info("🚀 Starting VM Orchestrator...")
    try:
        await initialize_orchestrator(
            software_types=None,  # None = manage all software types (copilot_ide, cline_ide, cursor_ide)
            max_concurrency=10,   # Max 10 VMs running simultaneously across ALL software types
            max_uses_before_refresh=100,
            use_mock_hypervisor=True  # Set to False when using real hypervisor
        )
        await start_scheduler()
        logger.info("✅ VM Orchestrator started successfully")
        logger.info("🚦 Managing all software types with max 10 concurrent VMs")
    except Exception as e:
        logger.error(f"❌ Failed to start orchestrator: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("🛑 Shutting down VM Orchestrator...")
    try:
        await stop_scheduler()
        logger.info("✅ VM Orchestrator stopped")
    except Exception as e:
        logger.warning(f"Error during orchestrator shutdown: {e}")

# --- FastAPI App Setup ---
app = FastAPI(
    title="AgentSphere Backend", 
    lifespan=lifespan,
    # Increase WebSocket message size limit to 50MB
    ws_max_size=50 * 1024 * 1024
)
router = APIRouter()

# Network exposure guard.
#
# By default the API only accepts clients from the same machine.  If you need to
# access it through a reverse proxy or from a trusted LAN host, set
# ALLOWED_CLIENT_HOSTS, for example:
#   ALLOWED_CLIENT_HOSTS=127.0.0.1,::1,192.0.2.10
#
# This is intentionally independent of CORS: CORS protects browsers, but it
# does not stop scanners/curl/other non-browser clients from hitting the API.
ALLOWED_CLIENT_HOSTS = {
    host.strip()
    for host in os.getenv("ALLOWED_CLIENT_HOSTS", "127.0.0.1,::1,localhost").split(",")
    if host.strip()
}

def _client_allowed(host: str | None) -> bool:
    if not ALLOWED_CLIENT_HOSTS or "*" in ALLOWED_CLIENT_HOSTS:
        return True
    return bool(host and host in ALLOWED_CLIENT_HOSTS)

@app.middleware("http")
async def allow_only_trusted_clients(request: Request, call_next):
    client_host = request.client.host if request.client else None
    if not _client_allowed(client_host):
        logger.warning(f"Rejected HTTP request from untrusted client: {client_host}")
        return Response("Forbidden", status_code=403)
    return await call_next(request)

# Setup server logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler())
logger.addHandler(logging.FileHandler('logs/server.log', mode="a"))

root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)

# --- State Management ---
class Task(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    status: str = "pending"
    results: Optional[List[Any]] = Field(default_factory=list)
    runner_result: Any = None
    task_ix: int = 0
    queues: Dict[str, Optional[asyncio.Queue]]
    latest_frame: Optional[str] = None
    stop_requested: bool = False
    worker_loop: Any = None  # Stores asyncio.AbstractEventLoop
    worker_task: Any = None  # Stores asyncio.Task
    message_buffer: List[dict] = Field(default_factory=list)  # Buffer messages before client connects
    completed_results: List[Any] = Field(default_factory=list)  # Historical skipped results available on demand
    completed_result_file: Optional[str] = None

TASKS: Dict[str, Task] = {}
CONNECTIONS: Dict[str, List[WebSocket]] = defaultdict(list)
EXTENSIONS_DIR = Path("temp_extensions")
EXTENSIONS_DIR.mkdir(exist_ok=True)

# A thread pool executor to run our blocking I/O tasks
executor = ThreadPoolExecutor()

# Retry configuration
MAX_ATTEMPTS = 3

# --- WebSocket and Queue Logic ---

from fastapi.encoders import jsonable_encoder # <--- Import this

async def broadcast_to_task_clients(task_id: str, message: dict):
    """Helper function to send a JSON message to all clients for a specific task."""
    # logger.debug(...) 
    
    # 1. Convert complex types (Pydantic models, datetime, UUID) to standard JSON types
    # Run JSON encoding in thread pool to avoid blocking event loop for large payloads
    loop = asyncio.get_running_loop()
    safe_message = await loop.run_in_executor(None, jsonable_encoder, message)

    # If no clients connected yet, buffer the message
    if task_id not in CONNECTIONS or len(CONNECTIONS[task_id]) == 0:
        task = TASKS.get(task_id)
        if task:
            task.message_buffer.append(safe_message)
        return

    # Send to all clients without blocking - create tasks for each send
    async def send_to_client(client, msg):
        try:
            await client.send_json(msg)
        except Exception as e:
            logger.error(f"Failed to send message to client {task_id}: {e}")
            if client in CONNECTIONS[task_id]:
                CONNECTIONS[task_id].remove(client)
    
    # Create non-blocking tasks for each client
    for client in CONNECTIONS[task_id][:]:
        asyncio.create_task(send_to_client(client, safe_message))

async def queue_pusher(task_id: str, queue_name: str):
    print(f"[{task_id}] {queue_name} queue pusher started.")
    task_info = TASKS.get(task_id)
    if not task_info:
        return

    queue = task_info.queues.get(queue_name)
    if queue is None:
        return
    batch_size = 10 if queue_name == "frame" else 50  # Batch frames less aggressively
    batch = []
    
    while True:
        try:
            # Try to get items with a small timeout to allow batching
            new_data = await asyncio.wait_for(queue.get(), timeout=0.1)
        except asyncio.TimeoutError:
            # Process batch if we have items
            if batch:
                for item in batch:
                    await _process_queue_item(task_id, queue_name, item)
                batch.clear()
                # Yield to event loop after processing batch
                await asyncio.sleep(0)
            continue

        if new_data is None:
            # Process remaining batch before exiting
            if batch:
                for item in batch:
                    await _process_queue_item(task_id, queue_name, item)
            break # Exit the loop on shutdown signal
        
        batch.append(new_data)
        
        # Process batch when it reaches size limit
        if len(batch) >= batch_size:
            for item in batch:
                await _process_queue_item(task_id, queue_name, item)
            batch.clear()
            # Yield to event loop after processing batch
            await asyncio.sleep(0)
    
    # After exiting the loop, finalize the queue
    await _finalize_queue_pusher(task_id, queue_name)

async def _process_queue_item(task_id: str, queue_name: str, new_data: Any):
    """Process a single queue item and broadcast to clients"""
    try:
        payload = None
        if queue_name == "frame":
            # new_data is now: {"type": "frame", "data": bytes, "sample_id": str}
            if isinstance(new_data, dict) and "data" in new_data:
                image_bytes = new_data["data"]
                sample_id = new_data.get("sample_id")
                
                base64_image = base64.b64encode(image_bytes).decode("utf-8")
                data_url = f"data:image/png;base64,{base64_image}"
                
                # Store latest frame (optional: you might want a dict of latest frames per sample)
                TASKS[task_id].latest_frame = data_url 
                
                payload = {
                    "code": 0, "message": "success",
                    "data": {
                        "frame": data_url, 
                        "sample_id": sample_id,  # Pass to client
                        "timestamp": int(time.time() * 1000)
                    }
                }
                # Optional: Save to file with sample ID
                with open(f"exp/{task_id}/frame_{sample_id}.png", "wb") as f:
                    f.write(image_bytes)

        # --- HANDLING LOGS ---
        elif queue_name == "log":
            # new_data is now: {"type": "log", "message": str, "sample_id": str, ...}
            if isinstance(new_data, dict):
                log_msg = new_data.get("message")
                sample_id = new_data.get("sample_id")
            else:
                # Fallback for system logs that might not use the new handler
                log_msg = str(new_data)
                sample_id = "system"

            payload = {
                "code": 0, "message": "success",
                "data": {
                    "log": log_msg, 
                    "sample_id": sample_id, # Pass to client
                    "timestamp": int(time.time() * 1000)
                }
            }
        
        # --- HANDLING RESULTS ---
        elif queue_name == "result":
            # Results usually contain sample_id inside them already
            sample_id = new_data.get("sample_id")
            
            print('='*50)
            print("New result data prepared:", new_data.get('scores'))
            print('='*50)
            payload = {
                "code": 0, "message": "success",
                "data": {
                    "result": new_data, 
                    "sample_id": sample_id, # Ensure client sees it easily
                    "timestamp": int(time.time() * 1000)
                }
            }
            TASKS[task_id].results.append(new_data)
            
        if payload:
            await broadcast_to_task_clients(task_id, payload)
            
    except Exception as e:
        # If serialization fails here (before broadcast), catch it
        logger.error(f"[{task_id}] Queue processing error: {e}")
        traceback.print_exc()

def _build_stream_queues(req: ExperimentConfig) -> Dict[str, Optional[asyncio.Queue]]:
    """Create queues according to request streaming preferences.

    result queue is always enabled because it drives final result delivery and
    TASKS[task_id].results. frame/log queues are optional and only affect live
    WebSocket transport, not local result files.
    """
    return {
        'frame': asyncio.Queue() if req.stream_frames else None,
        'result': asyncio.Queue(),
        'log': asyncio.Queue() if req.stream_logs else None,
    }


def _start_queue_pushers(task_id: str, queues: Dict[str, Optional[asyncio.Queue]]) -> None:
    for queue_name, queue in queues.items():
        if queue is not None:
            asyncio.create_task(queue_pusher(task_id, queue_name))


def _shutdown_queues_threadsafe(task_id: str, main_loop: asyncio.AbstractEventLoop) -> None:
    if task_id not in TASKS or not TASKS[task_id].queues:
        return
    for q_name, queue in TASKS[task_id].queues.items():
        if queue is None:
            continue
        try:
            main_loop.call_soon_threadsafe(queue.put_nowait, None)
        except Exception as e:
            print(f"[{task_id}] Error closing queue {q_name}: {e}")


async def _finalize_queue_pusher(task_id: str, queue_name: str):
    """Send final messages when queue finishes"""
    # Only send "Task Finished" if this is the RESULT queue.
    # If the frame queue finishes, we just stop sending frames, but we wait for the result.
    if queue_name == "result":
        print(f"[{task_id}] Result queue finished. Sending Task Complete signal.")
        final_payload = {"code": 1002, "message": "Task completed", "data": None}
        await broadcast_to_task_clients(task_id, final_payload)
    else:
        print(f"[{task_id}] {queue_name} queue finished.")

def safe_release_vm_from_thread(main_loop, vm, task_id):
    if not vm: return
    async def _release():
        try:
            logger.info(f"[{task_id}] Releasing VM {vm.vm_id}...")
            await release_vm_session(vm)
        except Exception as e:
            logger.error(f"[{task_id}] Release failed: {e}")
            
    # Schedule on main loop
    main_loop.call_soon_threadsafe(lambda: main_loop.create_task(_release()))

# REVISED WORKER FUNCTION
# Update signature to accept 'main_loop'
def run_redteam_task_in_thread(task_id: str, runner: RedTeamRunner, main_loop: asyncio.AbstractEventLoop):
    import asyncio as thread_asyncio
    
    # Create the worker loop for this thread
    worker_loop = thread_asyncio.new_event_loop()
    thread_asyncio.set_event_loop(worker_loop)

    log_queue = TASKS[task_id].queues['log']
    
    with TaskLoggingContext(task_id, log_queue, main_loop):
        try:
            # Call the async internal method directly to avoid nested loop issues
            # runner.run() uses asyncio.run() which fails if called inside a loop
            worker_task = worker_loop.create_task(runner._run_inner())
            TASKS[task_id].worker_loop = worker_loop
            TASKS[task_id].worker_task = worker_task
            
            TASKS[task_id].status = "running"
            result_data = worker_loop.run_until_complete(worker_task)
            
            TASKS[task_id].status = "finished"
            TASKS[task_id].runner_result = result_data
        except thread_asyncio.CancelledError:
            logger.warning(f"🛑 [{task_id}] Dataset task cancelled.")
            TASKS[task_id].status = "cancelled"
        except Exception as e:
            print(f"[{task_id}] Task encountered an error: {e}")
            traceback.print_exc()
            TASKS[task_id].status = "error"
        finally:
            worker_loop.close()
            
            # Send shutdown signals to enabled queues
            print(f"[{task_id}] Thread cleanup. Sending shutdown signals to queues.")
            _shutdown_queues_threadsafe(task_id, main_loop)

def run_single_sample_in_thread(task_id: str, request_data: ExperimentConfig, main_loop: asyncio.AbstractEventLoop, vm: VMInstance | None = None):
    """Worker function to run a single sample in a separate thread using RedTeamRunner"""
    import asyncio as thread_asyncio
    
    # Create the worker loop for this thread
    worker_loop = thread_asyncio.new_event_loop()
    thread_asyncio.set_event_loop(worker_loop)

    headers = vm.session_info.headers if vm else {}

    # --- FIX: Start Logging Context IMMEDIATELY ---
    # This ensures logs from VM acquisition are captured and streamed
    log_queue = TASKS[task_id].queues['log']
    fail_immediately_on_error = request_data.fail_immediately_on_error
    
    with TaskLoggingContext(task_id, log_queue, main_loop):
        try:
            # 1. Acquire VM (Now inside the logging context)
            if request_data.agent.software.endswith("ide"):
                if vm:
                    logger.info(f"[{task_id}] Using provided VM {vm.vm_id} for IDE task at {vm.session_info.ip}, VNC Port {vm.session_info.vnc_port}.")
                
                logger.info(f"[{task_id}] ✅ Acquired VM {vm.vm_id} (IP: {vm.session_info.ip})")
                    
            # 2. Run Retry Loop
            for attempt in range(1, MAX_ATTEMPTS + 1):
                if TASKS[task_id].stop_requested:
                    break
                try:
                    TASKS[task_id].status = "running"
                    assert request_data.sample, "Single-sample experiment need sample." 
                    logger.info(f"[{task_id}] Attempt {attempt}/{MAX_ATTEMPTS} for sample {request_data.sample.id}")
                    
                    runner = RedTeamRunner(
                        exp_config=request_data,
                        task_id=task_id,
                        queues=TASKS[task_id].queues,
                        loop=main_loop,
                        server_config=server_config,
                    )
                    
                    coro = runner.run_single_sample(
                        sample=request_data.sample,
                        scorers={"default_scorer": default_scorer},
                        container_preparation_fn=container_preparation,
                        sample_id=request_data.sample.id,
                        headers=headers,
                        vm=vm,
                        save_result=True,
                    )
                    
                    worker_task = worker_loop.create_task(coro)
                    TASKS[task_id].worker_loop = worker_loop
                    TASKS[task_id].worker_task = worker_task
                    
                    result_data = worker_loop.run_until_complete(worker_task)
                    
                    TASKS[task_id].status = "finished"
                    TASKS[task_id].runner_result = [result_data]
                    break # Success

                except thread_asyncio.CancelledError:
                    logger.warning(f"🛑 [{task_id}] Execution cancelled.")
                    TASKS[task_id].status = "cancelled"
                    break
                except Exception as e:
                    traceback.print_exception(e)
                    logger.warning(f"⚠️ [{task_id}] Attempt {attempt} failed: {e}")
                    if attempt == MAX_ATTEMPTS or fail_immediately_on_error:
                        TASKS[task_id].status = "error"
                        TASKS[task_id].runner_result = [{"error": str(e), "status": "error"}]
                        break

        finally:
            if vm:
                print(f"{''.center(40, '=')}\nVM detected!!!!!!!, releasing...")
                logger.info(f"[{task_id}] Releasing VM {vm.vm_id}...")
                safe_release_vm_from_thread(main_loop, vm, task_id)

            worker_loop.close()
            
            # Send shutdown signals to enabled queues
            _shutdown_queues_threadsafe(task_id, main_loop)


# --- API Endpoints ---
@router.post("/coding-agent/tasks", status_code=200)
async def start_evaluation_task(req: ExperimentConfig):
    logger.info("Starting new evaluation task...")
    logger.info(f"Software: {req.agent.software}, LLM: {req.agent.model.model_name}, Dataset: {req.dataset_name}, Attack Method: {req.attack_method_name}")
    try:
        main_loop = asyncio.get_running_loop()
        queues = _build_stream_queues(req)
        task_id = f"task-{int(time.time())}-{uuid.uuid4().hex[:8]}"
        
        runner = RedTeamRunner(
            exp_config=req,
            queues=queues,
            loop=main_loop,
            task_id=task_id,
            server_config=server_config,
        )

        completed_results = list(runner.completed_experiments.values()) if req.skip_completed else []
        TASKS[task_id] = Task(
            queues=queues,
            completed_results=completed_results,
            completed_result_file=str(runner.result_file_path),
        )
        
        # Schedule queue pushers only for enabled live streams.
        _start_queue_pushers(task_id, queues)
        
        # Run the blocking task in a separate thread without awaiting it here
        main_loop.run_in_executor(
            executor, 
            run_redteam_task_in_thread, 
            task_id, 
            runner, 
            main_loop, # <--- PASSED HERE
        )
        
        return {
            "code": 0,
            "message": "Task started successfully",
            "data": {
                "task_id": task_id,
                "frame_endpoint": f"/api/v1/coding-agent/tasks/{task_id}/frame",
                "completed_results_count": len(completed_results),
                "completed_results_endpoint": f"/api/v1/coding-agent/tasks/{task_id}/completed-results",
            },
        }
    
    except json.JSONDecodeError:
        return {"code": 1001, "message": "Failed to start: invalid MCP configuration format", "data": None}
    except Exception as e:
        traceback.print_exception(e)
        logger.error(f"Failed to start task: {e}")
        # You can customize the error message based on the specific exception
        if "VSCode" in str(e) or "connection" in str(e).lower():
            return {"code": 1001, "message": "Failed to start: cannot connect to VSCode", "data": None}
        else:
            return {"code": 1001, "message": f"Failed to start: {str(e)}", "data": None}

@router.post("/coding-agent/tasks/single-sample", status_code=200)
async def run_single_sample(request: ExperimentConfig):
    assert request.sample is not None, "Single-sample task requires a sample."
    logger.info(f"Starting single sample task for sample: {request.sample.id}")
    
    # 1. Prepare variables
    vm = None
    vm_info = None

    try:
        # 2. Acquire VM immediately (Blocking the HTTP response, not the thread)
        if request.agent.software.endswith("ide"):
            try:
                # We use the main loop's orchestrator to get the VM
                vm = await acquire_vm_for_session(software_type=request.agent.software, timeout=300)
                
                # Extract info to send to client
                vm_info = {
                    "vm_id": vm.vm_id,
                    "ip": vm.session_info.ip,
                    "ssh_port": vm.session_info.ssh_port,
                    "vnc_port": vm.session_info.vnc_port,
                    "headers": vm.session_info.headers,
                }
                logger.info(f"✅ VM {vm.vm_id} acquired immediately. IP: {vm.session_info.ip}, VNC Port: {vm.session_info.vnc_port}")
            except Exception as e:
                logger.error(f"Failed to acquire VM: {e}")
                return {"code": 1001, "message": f"VM Error: {str(e)}", "data": None}
        logger.info(f"Software: {request.agent.software}, LLM: {request.agent.model.model_name}")
    
        main_loop = asyncio.get_running_loop()
        queues = _build_stream_queues(request)
        task_id = f"task-{int(time.time())}-{uuid.uuid4().hex[:8]}"
        
        TASKS[task_id] = Task(queues=queues)
        
        # Schedule queue pushers only for enabled live streams.
        _start_queue_pushers(task_id, queues)
        
        # Run the blocking task in a separate thread
        main_loop.run_in_executor(
            executor,
            run_single_sample_in_thread,
            task_id,
            request,
            main_loop,
            vm
        )
        
        return {
            "code": 0,
            "message": "Single-sample task started successfully",
            "data": {
                "task_id": task_id,
                "vm_info": vm_info,
                "websocket_endpoint": f"/ws/{task_id}",
                "frame_endpoint": f"/api/v1/coding-agent/tasks/{task_id}/frame"
            }
        }
    
    except Exception as e:
        logger.error(f"Error starting task: {e}")
        # Cleanup if we crashed after acquiring but before starting thread
        if vm:
            await release_vm_session(vm)
        return {"code": 1001, "message": str(e), "data": None}

# The WebSocket endpoint remains the same
@app.websocket("/ws/{task_id}")
async def websocket_endpoint(websocket: WebSocket, task_id: str):
    client_host = websocket.client.host if websocket.client else None
    if not _client_allowed(client_host):
        logger.warning(f"Rejected WebSocket request from untrusted client: {client_host}")
        await websocket.close(code=1008, reason="Forbidden")
        return

    if task_id not in TASKS:
        await websocket.close(code=1008, reason="Task not found")
        return

    # Accept with larger message size limit (50MB to handle large results with base64 images)
    await websocket.accept()
    CONNECTIONS[task_id].append(websocket)
    
    # Send all buffered messages to the newly connected client
    task = TASKS[task_id]
    if task.message_buffer:
        logger.info(f"[{task_id}] Sending {len(task.message_buffer)} buffered messages to new client")
        for buffered_message in task.message_buffer:
            try:
                await websocket.send_json(buffered_message)
            except Exception as e:
                logger.error(f"[{task_id}] Failed to send buffered message: {e}")
        # Clear the buffer after sending
        logger.info(f"[{task_id}] Cleared message buffer after sending to client")
        task.message_buffer.clear()
    
    try:
        while True:
            # Sleep to keep the event loop responsive for ping/pong handling
            # FastAPI automatically responds to protocol-level pings in the background
            await asyncio.sleep(30)  # Increased to 30s to reduce overhead
            
            # Send periodic keepalive message to detect dead connections
            # Only send if we haven't sent data recently
            try:
                await websocket.send_json({
                    "code": 1000, 
                    "message": "keepalive", 
                    "data": {"timestamp": int(time.time() * 1000)}
                })
            except Exception as e:
                logger.warning(f"[{task_id}] Keepalive send failed, connection dead: {e}")
                break
                
    except WebSocketDisconnect:
        logger.info(f"Client disconnected from task {task_id}")
    except Exception as e:
        logger.error(f"WebSocket error for task {task_id}: {e}")
    finally:
        if websocket in CONNECTIONS.get(task_id, []):
            CONNECTIONS[task_id].remove(websocket)

def _get_task_result_data(task_id: str) -> Tuple[Optional[List[RunnerResult]], Optional[List[Any]], Optional[Dict[str, Any]]]:
    """Helper: fetch and validate task result data"""
    task = TASKS.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task.status != "finished":
        return None, None, {"code": 1003, "message": f"Task is not completed, status: {task.status}", "data": None}
    
    if not task.runner_result:
        return None, None, {"code": 1004, "message": "Task is completed, but no reults", "data": None}

    # Handle the case where result is a list (based on the result.json structure, it is a list of dicts)
    runner_result = task.runner_result
    results = task.results if task.results else []
    return runner_result, results, None

@router.get("/coding-agent/tasks/{task_id}/completed-results")
async def get_task_completed_results(task_id: str, limit: int = 0, offset: int = 0, include_result: bool = True):
    """
    Fetch historical results that were skipped due to skip_completed=True.

    These results are intentionally not replayed over the experiment WebSocket by
    default, because replaying hundreds of old results on every resume can make
    fragile clients repeatedly restart and overload the server.
    """
    task = TASKS.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    completed = task.completed_results or []
    total = len(completed)
    offset = max(0, offset)
    end = None if not limit or limit <= 0 else offset + limit
    page = completed[offset:end]

    if not include_result:
        page = [
            {
                "sample_id": item.get("sample_id") if isinstance(item, dict) else None,
                "status": item.get("status") if isinstance(item, dict) else None,
                "timestamp": item.get("timestamp") if isinstance(item, dict) else None,
                "attempts": item.get("attempts") if isinstance(item, dict) else None,
                "error": item.get("error") if isinstance(item, dict) else None,
            }
            for item in page
        ]

    return {
        "code": 0,
        "message": "success",
        "data": {
            "task_id": task_id,
            "result_file": task.completed_result_file,
            "total": total,
            "offset": offset,
            "limit": limit,
            "results": page,
        },
    }

@router.post("/coding-agent/completed-results")
async def get_completed_results_for_config(req: ExperimentConfig, limit: int = 0, offset: int = 0, include_result: bool = True):
    """
    Query completed results for a config without starting a new experiment.
    """
    dummy_queues = {"frame": None, "result": asyncio.Queue(), "log": None}
    runner = RedTeamRunner(
        exp_config=req,
        queues=dummy_queues,
        loop=asyncio.get_running_loop(),
        task_id="completed-results-query",
        server_config=server_config,
    )
    completed = list(runner.completed_experiments.values()) if req.skip_completed else []
    total = len(completed)
    offset = max(0, offset)
    end = None if not limit or limit <= 0 else offset + limit
    page = completed[offset:end]
    if not include_result:
        page = [
            {
                "sample_id": item.get("sample_id") if isinstance(item, dict) else None,
                "status": item.get("status") if isinstance(item, dict) else None,
                "timestamp": item.get("timestamp") if isinstance(item, dict) else None,
                "attempts": item.get("attempts") if isinstance(item, dict) else None,
                "error": item.get("error") if isinstance(item, dict) else None,
            }
            for item in page
        ]

    return {
        "code": 0,
        "message": "success",
        "data": {
            "result_file": str(runner.result_file_path),
            "total": total,
            "offset": offset,
            "limit": limit,
            "results": page,
        },
    }

@router.get("/coding-agent/tasks/{task_id}/report")
async def get_task_report(task_id: str):
    """
    Fetch a task's evaluation report (scores, statistics, configuration).
    """
    runner_results, results, error_response = _get_task_result_data(task_id)
    if runner_results is None or results is None:
        return error_response

    n_run_success = 0
    n_attack_success = 0
    samples = []
    for sample, result in zip(runner_results, results):
        if sample.status == "success":
            n_run_success += 1
        if result.get("attack_success"):
            n_attack_success += 1
        samples.append(result.get('sample'))

    report_data = {
        "n_samples": len(runner_results),
        "n_run_success": n_run_success,
        "n_attack_success": n_attack_success,
        "samples": samples, 
        "stats": [runner_result.stats for runner_result in runner_results],
        "config": results[0].get("exp_config") if results else None,
    }
        
    return {
        "code": 0, 
        "message": "success", 
        "data": report_data
    }

@router.post("/coding-agent/tasks/{task_id}/cancel")
async def cancel_task(task_id: str):
    if task_id not in TASKS:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task_info = TASKS[task_id]
    
    # 1. Set flag (prevents new retries)
    task_info.stop_requested = True
    task_info.status = "cancelling"
    logger.info(f"🛑 Cancel requested for {task_id}")

    # 2. Inject Exception into the running Async Task
    if task_info.worker_loop and task_info.worker_task and not task_info.worker_task.done():
        logger.info(f"🛑 Sending CancelledError to worker task...")
        # Schedule the cancellation in the WORKER thread's loop
        task_info.worker_loop.call_soon_threadsafe(task_info.worker_task.cancel)
    else:
        logger.info("Task is not running or already finished.")
        final_payload = {"code": 1002, "message": "Task completed", "data": None}
        await broadcast_to_task_clients(task_id, final_payload)

    return {"code": 0, "message": "Cancellation signal sent"}

@router.get("/api/vm-pool/status")
async def get_vm_pool_status():
    """
    Get the current status of the VM pool.
    
    Returns:
    - total_vms: Total number of VMs managed
    - active_vms: Number of currently active VMs
    - max_concurrency: Maximum concurrent VMs allowed
    - software_breakdown: Breakdown by software type (total, ready, busy, stopped)
    """
    try:
        orchestrator = get_orchestrator()
        if not orchestrator:
            return {
                "code": 1005,
                "message": "VM Orchestrator not initialized",
                "data": None
            }
        
        status = orchestrator.get_pool_status()
        
        return {
            "code": 0,
            "message": "success",
            "data": status
        }
    except Exception as e:
        logger.error(f"Failed to get VM pool status: {e}")
        return {
            "code": 1005,
            "message": f"Failed to get pool status: {str(e)}",
            "data": None
        }

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")

if __name__ == "__main__":
    import uvicorn
    parser = argparse.ArgumentParser(description="AgentSphere Queue Server")
    # Safer default: listen on localhost only.  Use --host 0.0.0.0 together
    # with ALLOWED_CLIENT_HOSTS if you intentionally expose the service.
    parser.add_argument("--host", type=str, default=os.getenv("QUEUE_SERVER_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=8083)
    parser.add_argument("--yaml", type=str, default="server.yaml", help="Path to server config YAML file")
    args = parser.parse_args()
    global server_config
    if os.path.exists(args.yaml):
        with open(args.yaml, 'r') as f:
            config = yaml.safe_load(f)
            server_config = ServerConfig(**config)
            logger.info(f"Loaded server config from {args.yaml}: {server_config}")
    else:
        logger.warning(f"Config file {args.yaml} not found. Using default settings.")
        server_config = ServerConfig()

    uvicorn.run(app, host=args.host, port=args.port)
