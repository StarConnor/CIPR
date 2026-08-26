import os
import logging
import asyncio
import contextvars
from pathlib import Path
from datetime import datetime

_task_id_var = contextvars.ContextVar("task_id", default=None)
_sample_id_var = contextvars.ContextVar("sample_id", default=None)

def set_task_id(task_id: str):
    """Set the task_id context for the current async task/thread."""
    return _task_id_var.set(task_id)

def set_sample_id(sample_id: str):
    """Set the sample_id context for the current async task/thread."""
    return _sample_id_var.set(sample_id)

def get_task_id():
    return _task_id_var.get()

def get_sample_id():
    return _sample_id_var.get()

class QueueHandler(logging.Handler):
    """Sends log records to an asyncio Queue in a thread-safe way."""
    def __init__(self, queue: asyncio.Queue | None, loop: asyncio.AbstractEventLoop | None):
        super().__init__()
        self.queue = queue
        self.loop = loop

    def emit(self, record):
        try:
            msg = self.format(record)
            
            # Retrieve context
            s_id = _sample_id_var.get()
            
            # Construct a structured payload
            payload = {
                "type": "log",
                "message": msg,
                "sample_id": s_id,
                "timestamp": datetime.now().isoformat()
            }

            if self.queue is None:
                return
            # Push structured payload instead of raw string
            try:
                if self.loop is not None:
                    self.loop.call_soon_threadsafe(self.queue.put_nowait, payload)
                else:
                    self.queue.put_nowait(payload)
            except Exception:
                try:
                    self.queue.put_nowait(payload)
                except Exception:
                    pass
        except Exception:
            self.handleError(record)

class TaskIdFilter(logging.Filter):
    """Filters logs so only those from the specific task ID context are accepted."""
    def __init__(self, task_id):
        super().__init__()
        self.task_id = task_id

    def filter(self, record):
        # Check if the current thread has the matching task_id
        current_id = _task_id_var.get()
        return current_id == self.task_id

class TaskLoggingContext:
    """
    Context Manager to automatically setup and teardown logging for a specific task.
    Usage:
        with TaskLoggingContext(task_id, log_queue, loop):
            runner.run()
    """
    def __init__(self, task_id: str, queue: asyncio.Queue | None, loop: asyncio.AbstractEventLoop | None):
        self.task_id = task_id
        self.queue = queue
        self.loop = loop
        self.handlers = []
        self.token = None

    def __enter__(self):
        # 1. Set the task ID for this specific thread
        self.token = set_task_id(self.task_id)

        # 2. Setup formatter
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

        # Filter to only capture logs emitted from the current task context
        task_filter = TaskIdFilter(self.task_id)

        # 3. Setup Queue Handler (Stream to WebSocket) scoped to this task.
        # If queue is None, live log streaming is disabled but file logging below
        # remains enabled.
        if self.queue is not None:
            queue_h = QueueHandler(self.queue, self.loop)
            queue_h.setFormatter(formatter)
            queue_h.setLevel(logging.INFO)
            queue_h.addFilter(task_filter)
            self.handlers.append(queue_h)

        # 4. Setup File Handler (Isolated file for this task)
        log_dir = Path("exp") / self.task_id
        log_dir.mkdir(exist_ok=True, parents=True) # Added parents=True for safety
        file_h = logging.FileHandler(log_dir / "main.log", mode='w', encoding='utf-8')
        file_h.setFormatter(formatter)
        file_h.setLevel(logging.DEBUG)  
        file_h.addFilter(task_filter)
        self.handlers.append(file_h)

        # Silence noisy third-party libraries (Global setting, affects all, but harmless)
        logging.getLogger('urllib3').setLevel(logging.WARNING)
        logging.getLogger('docker').setLevel(logging.WARNING)
        logging.getLogger('sseclient').setLevel(logging.WARNING)
        logging.getLogger('asyncio').setLevel(logging.WARNING)
        logging.getLogger('requests').setLevel(logging.WARNING)
        logging.getLogger('httpx').setLevel(logging.WARNING)
        logging.getLogger('httpcore').setLevel(logging.WARNING)

        # Attach handlers to the root logger to capture all loggers in the application
        # The 'task_filter' ensures that Handler A only accepts logs from Thread A.
        root_logger = logging.getLogger()
        for h in self.handlers:
            root_logger.addHandler(h)
        
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # 1. Clean up handlers from the root logger
        root_logger = logging.getLogger()
        for h in self.handlers:
            root_logger.removeHandler(h)
            h.close()
        
        # 2. Reset the thread context
        if self.token:
            _task_id_var.reset(self.token)

def setup_logging(name: str | Path, stream=True):
    # Create logs directory if it doesn't exist
    if isinstance(name, Path):
        path = str(name.absolute())
        os.makedirs(str(name.parent.absolute()), exist_ok=True)
    else:
        os.makedirs("logs", exist_ok=True)
        path = f"logs/{name}"
    
    # Get or create logger
    logger_name = path.split("/")[-1]
    logger = logging.getLogger(logger_name)
    
    # Only configure if not already configured
    if not logger.handlers:
        logger.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        
        # Add file handler
        file_handler = logging.FileHandler(path, mode="a")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        
        # Add stream handler if requested
        if stream:
            stream_handler = logging.StreamHandler()
            stream_handler.setFormatter(formatter)
            logger.addHandler(stream_handler)
    
    # Ensure propagation to root logger (important for TaskLoggingContext)
    logger.propagate = True
    
    return logger

logger = setup_logging(__name__)
