"""
CLI Driver - Manages PTY sessions and Screen State for the ActionExecutor.
"""
import os
import pty
import time
import select
import struct
import fcntl
import termios
import threading
import subprocess
import logging
import re
from typing import Optional, List, Tuple
from dotenv import dotenv_values


# Import the existing TerminalRenderer
from .terminal_renderer import TerminalRenderer

logger = logging.getLogger(__name__)

class CLIController:
    def __init__(self):
        self.process: Optional[subprocess.Popen] = None
        self.master_fd: Optional[int] = None
        self.renderer: Optional[TerminalRenderer] = None

        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self.full_log = ""  # Keep a history of the session
        self.command = ""

    def start(self, command: List[str], rows: int = 30, cols: int = 120):
        """Start a new CLI session."""
        self.terminate()  # Cleanup existing if any

        self._stop_event.clear()
        self.full_log = ""
        self.renderer = TerminalRenderer(columns=cols, lines=rows)

        # Open PTY
        master_fd, slave_fd = pty.openpty()
        self.master_fd = master_fd

        # Set size
        winsize = struct.pack("HHHH", rows, cols, 0, 0)
        fcntl.ioctl(slave_fd, termios.TIOCSWINSZ, winsize)

        system_env = dotenv_values("/etc/environment")
        current_env = os.environ.copy()
        env = {**system_env, **current_env}
        env["PYTHONUNBUFFERED"] = "1"
        env["FORCE_COLOR"] = "1"
        env["TERM"] = "xterm-256color"
        env["LINES"] = str(rows)
        env["COLUMNS"] = str(cols)

        logger.info(f"Environment for CLI: {env}")
        logger.info(f"CLI Driver starting: {command}")
        self.command = " ".join(command)
        self.process = subprocess.Popen(
            command,
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            env=env,
            close_fds=True
        )
        os.close(slave_fd)

        # Resize master
        fcntl.ioctl(master_fd, termios.TIOCSWINSZ, winsize)

        # Start background reader
        self._thread = threading.Thread(target=self._reader_loop, daemon=True)
        self._thread.start()

    def _reader_loop(self):
        """Reads PTY output and updates the renderer in real-time."""
        while not self._stop_event.is_set():
            if self.process and self.process.poll() is not None:
                break

            try:
                r, _, _ = select.select([self.master_fd], [], [], 0.1)
                if self.master_fd in r:
                    data = os.read(self.master_fd, 4096)
                    if not data:
                        break
                    elif b'\x1b[6n' in data:
                        cy = self.renderer.screen.cursor.y + 1
                        cx = self.renderer.screen.cursor.x + 1
                        os.write(self.master_fd, f'\x1b[{cy};{cx}R'.encode())
                        data = data.replace(b'\x1b[6n', b'')

                    with self._lock:
                        if self.renderer:
                            self.renderer.feed(data)
                        try:
                            decoded = data.decode('utf-8', errors='ignore')
                            self.full_log += decoded
                        except Exception:
                            pass
            except (OSError, ValueError):
                break

    def write(self, text: str):
        """Write text/keys to the PTY."""
        if not self.master_fd:
            raise RuntimeError("CLI session not active")
        
        # Handle special tokens
        data = text
        if data == "<ENTER>":
            data = "\r"
        elif data == "<UP>":
            data = "\x1b[A"
        elif data == "<DOWN>":
            data = "\x1b[B"
        elif data == "<LEFT>":
            data = "\x1b[D"
        elif data == "<RIGHT>":
            data = "\x1b[C"
        elif data == "<CTRL+C>":
            data = "\x03"
        elif data == "<TAB>":
            data = "\t"
        elif data == "<ESC>":
            data = "\x1b"
        
        os.write(self.master_fd, data.encode('utf-8'))

    def get_screen_text(self) -> str:
        """Get the current visual text of the terminal."""
        if not self.renderer:
            return ""
        with self._lock:
            return self.renderer.get_screen_text()

    def get_full_log(self) -> str:
        """Return the accumulated output captured from the PTY."""
        with self._lock:
            return self.full_log

    def wait_for_text(self, pattern: str, timeout: float = 30.0, use_regex: bool = False) -> bool:
        """
        Block until the text/pattern appears on the screen.
        Returns True if found, False if timeout.
        """
        start = time.time()
        logger.debug(f"CLI Waiting for: '{pattern}' (Timeout: {timeout}s)")
        
        while (time.time() - start) < timeout:
            screen = self.get_screen_text()
            
            if use_regex:
                if re.search(pattern, screen, re.MULTILINE):
                    logger.debug(f"Pattern found: '{pattern}'")
                    return True
            else:
                if pattern in screen:
                    logger.debug(f"Text found: '{pattern}'")
                    return True
            
            time.sleep(0.2)
        
        logger.debug(f"Pattern not found after {timeout}s: '{pattern}'")
        return False
    
    def get_screenshot_base64(self) -> str:
        with self._lock:
            if not self.renderer:
                return ""
            return self.renderer.render_to_base64()

    def terminate(self):
        self._stop_event.set()
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=1)
            except:
                self.process.kill()
        if self.master_fd:
            try:
                os.close(self.master_fd)
            except:
                pass
        if self._thread:
            self._thread.join(timeout=1)
        self.process = None
        self.master_fd = None

# Singleton
_cli_controller = CLIController()


def get_cli_controller() -> CLIController:
    return _cli_controller