import pdb
import os
from pydantic_core import core_schema
from typing import  Any, Dict, Optional, List, Union
import socket
import requests
import time
import logging
import re
from datetime import datetime
from urllib.parse import urlparse


import docker
from docker.models.containers import Container
DOCKER_AVAILABLE = True
from .base import BaseExecutionEnvironment
from .build_image import build_instance_image
from ..utils.others import retry_sync, find_available_port
LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)


def _redact_runtime_secrets(text: str) -> str:
    """Keep container diagnostics useful without persisting runtime credentials."""
    key_names = r"api[_-]?key|anthropic_auth_token|anthropic_api_key|authorization"
    # Covers both Python-debug dictionaries (``'api_key': '...'``) and
    # environment/YAML-style output (``ANTHROPIC_API_KEY=...``).
    pattern = re.compile(
        rf"(?i)([\"']?(?:{key_names})[\"']?\s*[:=]\s*[\"']?)([^\"'\s,}}]+)"
    )
    return pattern.sub(r"\1<redacted>", text)

class DockerExecutionEnvironment(BaseExecutionEnvironment):
    """Docker-based execution environment for red teaming tests."""
    
    def __init__(
        self,
        image_name: str,
        container_name: Optional[str] = None,
        network: str = "my-network",
        volumes: Optional[Dict[str, Dict[str, str]]] = None,
        tmpfs: Optional[Dict[str, str]] = None,
        environment_vars: Optional[Dict[str, str]] = None,
        ports: Optional[Dict[str, int]] = None,
        auto_remove: bool = True,
        detach: bool = True,
        mounts = None,
        commands: Union[str, List[str]] = [],
        is_ssh: bool = False,
        privileged: bool = False,
        extra_hosts: Optional[Dict[str, str]] = None,
        **kwargs
    ):
        """
        Initialize Docker environment.

        Args:
            image_name: Docker image name to use
            container_name: Optional name for the container
            network_mode: Docker network mode (bridge, host, none)
            volumes: Dictionary mapping host paths to container paths
            environment_vars: Environment variables to set in container
            ports: Port mappings {container_port: host_port}
            auto_remove: Whether to remove container after stopping
            detach: Run container in detached mode
            auto_assign_ports: Automatically assign available ports if not specified
        """
        super().__init__()
        self.image_name = image_name
        self.container_name = container_name
        self.network = network
        self.volumes = volumes or {}
        self.tmpfs = tmpfs or {}
        self.environment_vars = environment_vars or {}
        self.auto_remove = auto_remove
        self.detach = detach
        self.mounts = mounts or []
        self.commands = commands
        self.is_ssh = is_ssh
        self.privileged = privileged
        self.extra_hosts = extra_hosts or {}

        # Handle port assignment
        self.ports = ports or {}

        # Docker client
        if docker is None:
            raise ImportError("Docker package is not installed. Install it with: pip install docker")
        if requests is None:
            raise ImportError("Requests package is not installed. Install it with: pip install requests")
            
        self.client = docker.from_env()
        self.container: Optional[Container] = None  # docker.models.containers.Container
        self._is_running = False
        self.api_url = None
        self.kwargs = kwargs

    def setup(self) -> None:
        """Start the Docker container."""
        if self._is_running:
            return

        try:
            self.client.images.get(self.image_name)
        except Exception:  # ImageNotFound
            raise
            # self.client.images.pull(self.image_name)
        attempts = 0
        while attempts < 3:
            try:
                # Check if network exists, create if not
                try:
                    self.client.networks.get(self.network)
                except Exception:  # Network not found
                    LOGGER.info(f"Creating network {self.network}...")
                    self.client.networks.create(self.network)
                
                except_ports = []
                for internal_port, external_port in self.ports.items():
                    self.ports[internal_port] = find_available_port(external_port, except_ports=except_ports)
                    except_ports.append(self.ports[internal_port])

                # Run container
                self.container = self.client.containers.run(
                    self.image_name,
                    name=self.container_name,
                    network=self.network,
                    volumes=self.volumes,
                    mounts=self.mounts,
                    environment=self.environment_vars,
                    ports=self.ports,
                    # auto_remove=self.auto_remove,
                    auto_remove=False,
                    detach=self.detach,
                    tmpfs=self.tmpfs,
                    privileged=self.privileged,
                    extra_hosts=self.extra_hosts,
                    # tty=True,
                    # stdin_open=True,
                    command=self.commands
                )
                self._is_running = True
                LOGGER.info(f"Container {self.container.short_id} started successfully")
                
                # Determine API URL based on network mode and port mappings
                if self.ports:
                    first_port = list(self.ports.keys())[0]
                    host_port = self.ports[first_port]
                    self.api_url = f"http://localhost:{host_port}"
                elif self.kwargs.get("health_port", None):
                    health_port = self.kwargs["health_port"]
                    self.api_url = f"http://localhost:{health_port}"
                else:
                    self.api_url = "http://localhost:8000"
                
                if self.is_ssh:
                    # Wait for SSH service to be ready
                    self._wait_for_ssh_ready(timeout=60)
                else:
                    # Wait for API to be ready
                    self._wait_for_api()
                return

            except Exception as e:
                attempts += 1
                LOGGER.error(f"Error starting container (attempt {attempts}/3): {e}")
                
                # Cleanup failed container before retry to avoid name conflicts
                if self.container:
                    try:
                        LOGGER.info(f"Cleaning up failed container {self.container.short_id}...")
                        self.container.stop(timeout=5)
                        self.container.remove(force=True)
                        self.container = None
                    except Exception as cleanup_error:
                        LOGGER.warning(f"Failed to cleanup container: {cleanup_error}")
                        # Try to remove by name as fallback
                        try:
                            if self.container_name:
                                existing = self.client.containers.get(self.container_name)
                                existing.remove(force=True)
                                LOGGER.info(f"Removed container by name: {self.container_name}")
                        except Exception:
                            pass  # Container might not exist
                
                continue
        if attempts >= 3:
            raise Exception("Failed to start Docker container after 3 attempts")

    def _wait_for_ssh_ready(self, timeout: int = 30) -> None:
        if not self.api_url:
            return
        parsed_url = urlparse(self.api_url)
        host = parsed_url.hostname
        port = parsed_url.port
        start_time = time.time()
        
        # First, wait for SSH banner
        banner_received = False
        while time.time() - start_time < timeout and not banner_received:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2.0)
            try:
                sock.connect((host, port))
                banner = sock.recv(1024)
                
                if banner.startswith(b"SSH-"):
                    LOGGER.info(f"SSH banner received on {host}:{port} - Banner: {banner.strip()}")
                    banner_received = True
            except (socket.timeout, ConnectionRefusedError, OSError) as e:
                LOGGER.debug(f"SSH banner check failed: {e}")
            finally:
                sock.close()
            
            if not banner_received:
                time.sleep(1)
        
        if not banner_received:
            raise RuntimeError(f"SSH service on {host}:{port} did not send banner within {timeout} seconds")
        
        # Now verify actual SSH connectivity with container exec
        # This ensures VS Code server and SSH are both functional
        LOGGER.info("SSH banner detected, verifying container SSH is fully operational...")
        
        consecutive_successes = 0
        required_successes = 2
        remaining_time = timeout - (time.time() - start_time)
        
        while time.time() - start_time < timeout:
            try:
                # Use docker exec to verify sshd is actually working inside container
                # Use a shell to allow the fallback pipeline; without this pgrep sees the pipe tokens as extra patterns
                exit_code, output = self.container.exec_run(
                    ["bash", "-c", "pgrep -f sshd || ps aux | grep sshd"],
                    demux=False
                )
                
                if exit_code == 0 and output:
                    consecutive_successes += 1
                    LOGGER.info(f"SSH daemon verified running in container ({consecutive_successes}/{required_successes})")
                    
                    if consecutive_successes >= required_successes:
                        # Grace period for VS Code server to be ready
                        LOGGER.info(f"SSH verified stable, waiting 3s grace period for VS Code server...")
                        time.sleep(3)
                        LOGGER.info(f"SSH is ready on {host}:{port}")
                        return
                else:
                    consecutive_successes = 0
                    
            except Exception as e:
                consecutive_successes = 0
                LOGGER.debug(f"SSH daemon verification failed: {e}")
            
            time.sleep(1.5)
    
        raise RuntimeError(f"SSH service on {host}:{port} did not become stable within {timeout} seconds")

    def _wait_for_api(self, timeout: int = 30) -> None:
        """Wait for API server to be ready."""
        if not self.api_url:
            return
            
        # Extract host and port from API URL
        parsed_url = urlparse(self.api_url)
        host = parsed_url.hostname
        port = parsed_url.port
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self._is_port_listening(host, port):
                LOGGER.info(f"Port {port} is listening at {host}")
                return
            time.sleep(1)
        
        raise RuntimeError(f"Port {port} did not start listening within {timeout} seconds")
    
    def _is_port_listening(self, host: Optional[str] = "localhost", port: Optional[int] = 8000, timeout: float = 2.0) -> bool:
        """Check if a port is listening."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(timeout)
                s.connect((host, port))
                return True
        except Exception:
            return False
    
    def teardown(self, log_path: str | None = None) -> None:
        """Stop and remove the Docker container, clean up resources."""
        if log_path is None:
            log_path = "./logs"
        try:
            if self.container:
                # Save logs before stopping the container
                try:
                    container_name = self.container_name or self.container.short_id
                    log_filename = os.path.join(log_path, f"{container_name}.log")
                    self.save_logs(log_filename, timestamps=True)
                    LOGGER.info(f"Container logs saved to {log_filename}")
                except Exception as log_error:
                    LOGGER.warning(f"Could not save container logs: {log_error}")

                self.container.stop()
                self.container.remove()
                self.container = None
        except Exception as e:
            LOGGER.warning(f"Error stopping container: {e}")
        
        # try:
        #     if self.temp_dir and os.path.exists(self.temp_dir):
        #         import shutil
        #         shutil.rmtree(self.temp_dir)
        #         self.temp_dir = None
        # except Exception as e:
        #     LOGGER.warning(f"Error cleaning up temp directory: {e}")
            
        if self.client:
            self.client.close()
            self.client = None
    
    def execute_tool(self, tool_name: str, **kwargs) -> str:
        """Execute a tool within the Docker container."""
        if not self.container:
            raise RuntimeError("Container not running. Call setup() first.")
        
        try:
            # Execute tool through http request
            json_data = kwargs
            response = requests.post(f"{self.api_url}/{tool_name}", json=json_data)
            return response.text
            
        except Exception as e:
            return f"Error executing tool '{tool_name}': {str(e)}"

    def get_state(self) -> Dict[str, Any]:
        """Get a snapshot of the container's current state."""
        if not self.container:
            return {"error": "Container not running"}
        
        try:
            # Get state through http request '/state'
            state = requests.get(f"{self.api_url}/state").json()
            return state
            
        except Exception as e:
            return {"error": f"Failed to get container state: {str(e)}"}
    
    def init_task(self):
        pass

    def get_logs(self, since: Optional[Union[str, datetime]] = None, 
                 until: Optional[Union[str, datetime]] = None,
                 timestamps: bool = False) -> str:
        """
        Retrieve logs from the container.
        
        Args:
            since: Show logs since timestamp (e.g., "2013-01-02T13:23:37") or datetime object
            until: Show logs before timestamp (e.g., "2013-01-02T13:23:37") or datetime object
            timestamps: Show timestamps in logs
            
        Returns:
            Container logs as a string
        """
        if not self.container:
            raise RuntimeError("Container not running. Call setup() first.")
            
        try:
            logs = self.container.logs(
                since=since,
                until=until,
                timestamps=timestamps
            )
            # Convert bytes to string if needed
            if isinstance(logs, bytes):
                logs = logs.decode('utf-8')
            return logs
        except Exception as e:
            raise RuntimeError(f"Failed to retrieve container logs: {e}")

    def save_logs(self, filepath: str, 
                  since: Optional[Union[str, datetime]] = None,
                  until: Optional[Union[str, datetime]] = None,
                  timestamps: bool = True) -> None:
        """
        Save container logs to a file.
        
        Args:
            filepath: Path to the file where logs should be saved
            since: Show logs since timestamp (e.g., "2013-01-02T13:23:37") or datetime object
            until: Show logs before timestamp (e.g., "2013-01-02T13:23:37") or datetime object
            timestamps: Show timestamps in logs
        """
        logs = _redact_runtime_secrets(
            self.get_logs(since=since, until=until, timestamps=timestamps)
        )
        
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(logs)

        LOGGER.info(f"Logs saved to {filepath}")

    def stream_logs(self, since: Optional[Union[str, datetime]] = None) -> None:
        """
        Stream logs from the container to stdout.
        
        Args:
            since: Show logs since timestamp (e.g., "2013-01-02T13:23:37") or datetime object
        """
        if not self.container:
            raise RuntimeError("Container not running. Call setup() first.")
            
        try:
            for line in self.container.logs(
                since=since,
                timestamps=True,
                follow=True,
                stream=True
            ):
                # Decode bytes to string if needed
                if isinstance(line, bytes):
                    line = line.decode('utf-8')
                LOGGER.info(line.rstrip())
        except Exception as e:
            raise RuntimeError(f"Failed to stream container logs: {e}")

    def get_file(self, file_path: str) -> str:
        """
        Retrieve the content of a file from the running container.
        
        Args:
            file_path: Path to the file inside the container
            
        Returns:
            Content of the file as a string
            
        Raises:
            RuntimeError: If the container is not running or file cannot be accessed
        """
        if not self.container:
            raise RuntimeError("Container not running. Call setup() first.")
            
        try:
            LOGGER.info(f"Attempting to retrieve file '{file_path}' from container")
            # Use the Docker SDK to get file content from container
            def get_file_info():
                return self.container.get_archive(file_path)
            
            bits, stat = retry_sync(get_file_info, max_attempts=5, delay=1, backoff=2, exceptions=(Exception,))
            LOGGER.info(f"Successfully retrieved file info. Stat: {stat}")
            
            # Log information about bits
            bits_list = list(bits)
            LOGGER.info(f"Bits list has {len(bits_list)} items")
            if len(bits_list) > 0:
                LOGGER.info(f"First bits item type: {type(bits_list[0])}, size: {len(bits_list[0]) if hasattr(bits_list[0], '__len__') else 'unknown'}")
            
            # The returned data is a tar archive, we need to extract it
            import tarfile
            import io
            
            # Create a tar file from the returned bytes
            tar_stream = io.BytesIO(b''.join(bits_list))
            LOGGER.info(f"Created tar stream of size: {tar_stream.getbuffer().nbytes} bytes")
            
            # Open and extract the tar file
            with tarfile.open(fileobj=tar_stream) as tar:
                members = tar.getmembers()
                LOGGER.info(f"Tar file contains {len(members)} members")
                if not members:
                    raise RuntimeError(f"No files found in archive for '{file_path}'")
                    
                member = members[0]  # Get the first (and likely only) file
                LOGGER.info(f"Extracting member: {member.name}, size: {member.size} bytes")
                file_content = tar.extractfile(member).read()
                LOGGER.info(f"Extracted content of size: {len(file_content)} bytes")
                
                # Try to decode as UTF-8 text, fallback to bytes if that fails
                try:
                    decoded_content = file_content.decode('utf-8')
                    LOGGER.info("Successfully decoded content as UTF-8")
                    return decoded_content
                except UnicodeDecodeError:
                    decoded_content = file_content.decode('utf-8', errors='replace')
                    LOGGER.warning("Decoded content with error replacement")
                    return decoded_content
                    
        except Exception as e:
            LOGGER.error(f"Failed to retrieve file '{file_path}' from container: {e}")
            raise RuntimeError(f"Failed to retrieve file '{file_path}' from container: {e}")
