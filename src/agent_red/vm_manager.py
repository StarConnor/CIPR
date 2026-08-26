import os
import pdb
import asyncio
import requests
import logging
import json
import time
import shutil
import base64
from typing import Dict, Any, Optional, Callable, Tuple, List
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
from .utils.util import run_cli_command, execute_workflow_stream

# Configure module-level logger
LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)

if not LOGGER.handlers:
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    LOGGER.addHandler(console_handler)


class VMState(str, Enum):
    """VM lifecycle states"""
    STOPPED = "STOPPED"
    STARTING = "STARTING"
    READY = "READY"
    BUSY = "BUSY"
    DIRTY = "DIRTY"
    MAINTENANCE = "MAINTENANCE"
    ERROR = "ERROR"
    RELEASED = "RELEASED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class VMwareRuntimeConfig:
    """Local VMware/SSH settings loaded from configs/vmware.local.yaml.

    Machine-specific paths intentionally do not have public defaults. The
    ignored local configuration holds the VM credentials as well.
    """

    guest_user: str = "devuser"
    guest_password: Optional[str] = None
    ssh_host: str = ""
    ssh_user: str = "devuser"
    ssh_config_dir: str = ""
    ssh_identity_file: str = ""
    github_identity_file: str = ""

    @classmethod
    def from_mapping(cls, data: Optional[Dict[str, Any]]) -> "VMwareRuntimeConfig":
        data = data or {}
        guest = data.get("guest") or {}
        ssh = data.get("ssh") or {}
        password = guest.get("password")
        if password is not None:
            password = str(password)
        elif guest.get("password_env"):
            # Backward compatibility for existing local configuration files.
            password = os.getenv(str(guest["password_env"]))
        return cls(
            guest_user=str(guest.get("username") or "devuser"),
            guest_password=password,
            ssh_host=str(ssh.get("host") or ""),
            ssh_user=str(ssh.get("user") or guest.get("username") or "devuser"),
            ssh_config_dir=str(ssh.get("config_dir") or ""),
            ssh_identity_file=str(ssh.get("identity_file") or ""),
            github_identity_file=str(ssh.get("github_identity_file") or ""),
        )


@dataclass
class VMSessionInfo:
    """Holds VM session information"""
    token: str
    ssh_port: int
    vnc_port: int
    ip: str = ""
    management_port: int = 8000
    api_version: str = "v1"

    @property
    def base_url(self) -> str:
        if not self.ip:
            return "http://localhost:0/ide"
        return f"http://{self.ip}:{self.management_port}/api/{self.api_version}"
    
    @property
    def headers(self) -> Dict[str, str]:
        return {
            "X-Session-Token": self.token,
            "Content-Type": "application/json"
        }


class VMAPIClient:
    """Handles all HTTP requests to a VM"""
    
    def __init__(
        self,
        session_info: VMSessionInfo,
        timeout: Tuple[int, int] = (30, 150),
        runtime_config: Optional[VMwareRuntimeConfig] = None,
    ):
        self.session_info = session_info
        self.runtime_config = runtime_config or VMwareRuntimeConfig()
        self.connect_timeout, self.read_timeout = timeout
        self.logger = logging.getLogger(f"{__name__}.VMAPIClient.{session_info.ip}")
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Generic request handler with error handling"""
        url = f"{self.session_info.base_url}{endpoint}"
        headers = {**self.session_info.headers, **kwargs.pop("headers", {})}
        timeout = kwargs.pop("timeout", (self.connect_timeout, self.read_timeout))
        
        try:
            if method == "GET":
                resp = requests.get(url, headers=headers, timeout=timeout, **kwargs)
            elif method == "POST":
                resp = requests.post(url, headers=headers, timeout=timeout, **kwargs)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            resp.raise_for_status()
            return resp.json() if resp.text else {"success": True}
        except requests.exceptions.Timeout as e:
            self.logger.error(f"Timeout on {method} {endpoint}: {e}")
            raise
        except requests.exceptions.ConnectionError as e:
            self.logger.error(f"Connection error on {method} {endpoint}: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Error on {method} {endpoint}: {e}")
            raise
    
    def check_busy(self):
        res = self._make_request("GET", "/session/status")
        return res.get("busy", False)

    # --- Restored Methods ---

    def register_extension(self, yaml_config: str, overwrite: bool = True) -> Dict[str, Any]:
        """Register an extension with the VM"""
        self.logger.info(f"Registering extension on {self.session_info.ip}")
        return self._make_request(
            "POST",
            "/extensions/register",
            json={"yaml_config": yaml_config, "overwrite": overwrite}
        )
    
    def prepare_vscode(self, target_name: str, executable_path: str, workspace_path: str, wait_time: float = 5.0) -> Dict[str, Any]:
        """Prepare VS Code environment"""
        self.logger.info(f"Preparing VS Code for {target_name}")
        return self._make_request(
            "POST",
            f"/extensions/{target_name}/workflow",
            json={
                "workflow": "prepare_vscode",
                "params": {
                    "executable_path": executable_path,
                    "workspace_path": workspace_path,
                    "wait_time": wait_time
                }
            },
            timeout=(30, 300)
        )
    
    def execute_workflow_stream(
        self,
        target_name: str,
        workflow: str,
        params: Dict[str, Any],
        log_level: str = "INFO",
        max_jumps: int = 1000,
        proxy_url: Optional[str] = None,
        on_log: Optional[Callable[[str, str], None]] = None,
        on_complete: Optional[Callable[[Dict[str, Any]], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
        frame_queue: asyncio.Queue | None = None,
        main_loop: asyncio.AbstractEventLoop | None = None,
        stream_screenshots: bool = True,
        stream_logs: bool = True,
    ) -> Dict[str, Any]:
        """Execute a streaming workflow and handle events (method wrapper)"""
        return execute_workflow_stream(
            url=f"{self.session_info.base_url}/extensions/{target_name}/workflow/stream",
            json_payload={"workflow": workflow, "proxy_url": proxy_url, "params": params, "screenshot_time": params.get("screenshot_time"), "log_level": log_level, "max_jumps": max_jumps, "stream_screenshots": stream_screenshots, "stream_logs": stream_logs},
            headers=self.session_info.headers,
            on_log=on_log,
            on_complete=on_complete,
            on_error=on_error,
            frame_queue=frame_queue,
            main_loop=main_loop,
            stream_screenshots=stream_screenshots,
            stream_logs=stream_logs,
            timeout=(self.connect_timeout, self.read_timeout),
            logger=self.logger
        )
    
    def upload_file(self, filename: str, content: str, dir_path: str) -> Dict[str, Any]:
        """Upload a file to the VM"""
        self.logger.info(f"Uploading file '{filename}' to {self.session_info.ip}:{dir_path}")
        return self._make_request(
            "POST",
            "/upload_file_json",
            json={
                "filename": filename,
                "content": base64.b64encode(content.encode('utf-8')).decode('utf-8'),
                "dir_path": dir_path
            },
            timeout=(30, 300)
        )

    def upload_ssh_config(self, port: int) -> Dict[str, Any]:
        """Upload SSH config with dynamic port for docker-container host"""
        config = self.runtime_config
        missing = [
            name for name, value in {
                "ssh.host": config.ssh_host,
                "ssh.config_dir": config.ssh_config_dir,
                "ssh.identity_file": config.ssh_identity_file,
                "ssh.github_identity_file": config.github_identity_file,
            }.items() if not value
        ]
        if missing:
            raise RuntimeError(
                "Missing VMware SSH configuration: "
                + ", ".join(missing)
                + ". Create configs/vmware.local.yaml from vmware.example.yaml."
            )
        ssh_config = f"""Host docker-container
    HostName {config.ssh_host}
    Port {port}
    User {config.ssh_user}
    IdentityFile {config.ssh_identity_file}
    StrictHostKeyChecking no
    UserKnownHostsFile /dev/null

Host github.com
    HostName github.com
    User git
    IdentityFile {config.github_identity_file}
    IdentitiesOnly yes
"""
        content_b64 = base64.b64encode(ssh_config.encode('utf-8')).decode('utf-8')
        
        self.logger.info(f"Uploading SSH config to {self.session_info.ip} with port {port}")
        return self._make_request(
            "POST",
            "/upload_file_json",
            json={
                "filename": "config",
                "content": content_b64,
                "dir_path": config.ssh_config_dir
            },
            timeout=(30, 300)
        )
    
    def execute_workflow(self, target_name: str, workflow: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a non-streaming workflow"""
        self.logger.info(f"Executing workflow '{workflow}' on {self.session_info.ip}")
        return self._make_request(
            "POST",
            f"/extensions/{target_name}/workflow",
            json={"workflow": workflow, "params": params},
            timeout=(30, 300)
        )
    
    def close_vscode(self, target_name: str, force: bool = True) -> Dict[str, Any]:
        """Close VS Code gracefully"""
        self.logger.info(f"Closing VS Code on {self.session_info.ip}")
        return self._make_request(
            "POST",
            f"/extensions/{target_name}/workflow",
            json={"workflow": "close_vscode", "params": {"force": force}},
            timeout=(30, 60)
        )
    
    def cancel_execution(self) -> Dict[str, Any]:
        """Cancel ongoing execution"""
        self.logger.info(f"Cancelling execution on {self.session_info.ip}")
        return self._make_request("POST", "/session/cancel_execution", timeout=(10, 10))


# ============================================================================
# HYPERVISOR CONTROLLER
# ============================================================================

class VMwareController:
    """Controller for Clone -> Run -> Destroy workflow."""
    
    def __init__(self, runtime_config: Optional[VMwareRuntimeConfig] = None):
        self.logger = logging.getLogger(f"{__name__}.VMwareController")
        self.provisioning_semaphore = asyncio.Semaphore(2)
        self.runtime_config = runtime_config or VMwareRuntimeConfig()
    
    def _read_vmx(self, path: str) -> str:
        with open(path, 'r') as f: return f.read()

    def _write_vmx(self, path: str, content: str):
        with open(path, 'w') as f: f.write(content)

    async def clone_vm(self, base_vmx: str, target_vmx: str) -> bool:
        async with self.provisioning_semaphore:
            try:
                base_vmx = base_vmx.strip("\"'")
                target_vmx = target_vmx.strip("\"'")
                target_dir = os.path.dirname(target_vmx)
                os.makedirs(target_dir, exist_ok=True)
                
                self.logger.info(f"Cloning {base_vmx} to {target_vmx}...")
                # Use linked clone for speed
                await asyncio.to_thread(run_cli_command, ["vmrun", "clone", base_vmx, target_vmx, "linked"])
                return True
            except Exception as e:
                self.logger.error(f"Failed to clone VM: {e}")
                return False

    async def set_vnc_port(self, vmx_path: str, port: int) -> bool:
        try:
            content = await asyncio.to_thread(self._read_vmx, vmx_path)
            lines = content.splitlines()
            new_lines = []
            vnc_port_set = False
            vnc_enabled_set = False

            for line in lines:
                if "RemoteDisplay.vnc.port" in line:
                    new_lines.append(f'RemoteDisplay.vnc.port = "{port}"')
                    vnc_port_set = True
                elif "RemoteDisplay.vnc.enabled" in line:
                    new_lines.append('RemoteDisplay.vnc.enabled = "TRUE"')
                    vnc_enabled_set = True
                else:
                    new_lines.append(line)
            
            if not vnc_port_set: new_lines.append(f'RemoteDisplay.vnc.port = "{port}"')
            if not vnc_enabled_set: new_lines.append('RemoteDisplay.vnc.enabled = "TRUE"')

            await asyncio.to_thread(self._write_vmx, vmx_path, "\n".join(new_lines))
            return True
        except Exception as e:
            self.logger.error(f"Failed to update VNC port: {e}")
            return False

    async def start_vm(self, vmx_path: str) -> bool:
        async with self.provisioning_semaphore:
            try:
                run_cli_command(["vmrun", "start", vmx_path, "nogui"])
                return True
            except Exception as e:
                self.logger.error(f"Failed to start VM {vmx_path}: {e}")
                return False
    
    async def stop_vm(self, vmx_path: str, force: bool = False) -> bool:
        try:
            mode = "hard" if force else "soft"
            run_cli_command(["vmrun", "stop", vmx_path, mode])
            return True
        except Exception as e:
            self.logger.error(f"Failed to stop VM {vmx_path}: {e}")
            return False

    async def delete_vm(self, vmx_path: str) -> bool:
        try:
            run_cli_command(["vmrun", "deleteVM", vmx_path])
            directory = os.path.dirname(vmx_path)
            if os.path.exists(directory):
                shutil.rmtree(directory)
            return True
        except Exception as e:
            self.logger.error(f"Failed to delete VM {vmx_path}: {e}")
            return False
    
    async def get_vm_ip(self, vmx_path: str, timeout: int = 300) -> Optional[str]:
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                try:
                    if self.runtime_config.guest_password:
                        run_cli_command([
                            "vmrun",
                            "-gu", self.runtime_config.guest_user,
                            "-gp", self.runtime_config.guest_password,
                            "runProgramInGuest", vmx_path, "cmd",
                        ])
                except Exception: pass
                
                ip = run_cli_command(["vmrun", "getGuestIPAddress", vmx_path])
                if ip and "Error" not in ip:
                    return ip.strip()
            except Exception: pass
            await asyncio.sleep(2)
        return None

    async def health_check(self, vm_ip: str, port: int = 8000) -> bool:
        try:
            response = requests.get(f"http://{vm_ip}:{port}/api/v1/health", timeout=2)
            return response.status_code == 200
        except Exception:
            return False
    
    async def is_vm_running(self, vmx_path: str) -> bool:
        try:
            output = run_cli_command(["vmrun", "list"])
            return vmx_path in output
        except Exception:
            return False


# ============================================================================
# VM INSTANCE
# ============================================================================

class VMInstance:
    """
    Manages the lifecycle: STOPPED -> STARTING -> READY -> BUSY -> DIRTY -> STOPPED
    """
    
    def __init__(
        self,
        vm_id: str,
        hypervisor: VMwareController,
        session_info: VMSessionInfo,
        base_vmx_path: str,
        instance_vmx_path: str,
        max_uses_before_refresh: int = 1,
        software_type: str = "unknown",
        runtime_config: Optional[VMwareRuntimeConfig] = None,
    ):
        self.vm_id = vm_id
        self.hypervisor = hypervisor
        self.session_info = session_info
        self.base_vmx_path = base_vmx_path
        self.instance_vmx_path = instance_vmx_path
        self.runtime_config = runtime_config or hypervisor.runtime_config
        self.api_client = VMAPIClient(session_info, runtime_config=self.runtime_config)
        
        self.state = VMState.STOPPED
        self.usage_count = 0
        self.max_uses_before_refresh = max_uses_before_refresh
        self.software_type = software_type
        self.logger = logging.getLogger(f"{__name__}.VMInstance.{vm_id}")
        self._lock = asyncio.Lock()
    
    async def start(self) -> bool:
        """Clone and Start the VM."""
        if self.state not in [VMState.STOPPED, VMState.RELEASED, VMState.ERROR]:
            return False
        
        self.state = VMState.STARTING
        self.logger.info(f"Initializing ephemeral VM from {self.base_vmx_path}")
        
        try:
            # If an instance clone already exists, reuse without cloning
            if os.path.exists(self.instance_vmx_path):
                self.logger.info("Existing VM clone detected; reusing without cloning.")
                # Ensure VNC port is configured (idempotent)
                await self.hypervisor.set_vnc_port(self.instance_vmx_path, self.session_info.vnc_port)
                # If already running, attach and validate
                if await self.hypervisor.is_vm_running(self.instance_vmx_path):
                    vm_ip = await self.hypervisor.get_vm_ip(self.instance_vmx_path, timeout=60)
                    if vm_ip:
                        self.session_info.ip = vm_ip
                        if await self.hypervisor.health_check(vm_ip):
                            self.state = VMState.READY
                            self.logger.info(f"VM is READY at {vm_ip}, vnc port {self.session_info.vnc_port}")
                            return True
                    # Not healthy/running properly; attempt restart
                    await self.hypervisor.stop_vm(self.instance_vmx_path, force=True)
                # Start the existing instance
                if not await self.hypervisor.start_vm(self.instance_vmx_path):
                    raise Exception("Startup failed")
            else:
                # Fresh clone path
                if not await self.hypervisor.stop_vm(self.base_vmx_path, force=True):
                    self.logger.warning("Base VM was running; forced stop failed.")
                if not await self.hypervisor.clone_vm(self.base_vmx_path, self.instance_vmx_path):
                    raise Exception("Clone failed")
                if not await self.hypervisor.set_vnc_port(self.instance_vmx_path, self.session_info.vnc_port):
                    raise Exception("VNC setup failed")
                if not await self.hypervisor.start_vm(self.instance_vmx_path):
                    raise Exception("Startup failed")
            
            # 4. Get IP
            vm_ip = await self.hypervisor.get_vm_ip(self.instance_vmx_path, timeout=600)
            if not vm_ip:
                raise Exception("Could not acquire IP address")
            self.session_info.ip = vm_ip

            # 5. Health Check
            for i in range(60):
                if await self.hypervisor.health_check(vm_ip):
                    self.state = VMState.READY
                    self.logger.info(f"VM is READY at {vm_ip}, vnc port {self.session_info.vnc_port}")
                    return True
                await asyncio.sleep(2)
            
            raise Exception("Service health check failed")
        
        except Exception as e:
            self.logger.error(f"Start sequence failed: {e}")
            self.state = VMState.ERROR
            await self.cleanup_and_revert()
            return False

    async def acquire(self) -> bool:
        """
        Atomic-like acquisition. 
        Only transitions if READY. Calls Guest API to get token.
        """
        if self._lock.locked():
            return False
        async with self._lock:
            if self.state != VMState.READY:
                return False
            
            try:
                previous_state = self.state
                self.state = VMState.BUSY
                # Call the Guest VM to get a session token
                resp = await asyncio.to_thread(
                    self.api_client._make_request, "POST", "/session/acquire"
                )
                
                if resp.get("success"):
                    self.session_info.token = resp.get("token", "")
                    self.state = VMState.BUSY
                    self.usage_count += 1
                    self.logger.info(f"VM acquired. Token: {self.session_info.token[:10]}...")
                    return True
                else:
                    self.state = previous_state
                    self.logger.warning(f"VM rejected acquisition: {resp}")
                    return False
            except Exception as e:
                self.state = previous_state
                self.logger.error(f"Acquisition failed: {e}")
                return False

    async def release(self):
        """Release the VM session and determine lifecycle state"""
        try:
            # 1. Call API to release session on the Guest
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self.api_client._make_request("POST", "/session/release", timeout=(30, 30))
            )
            self.logger.info(f"VM {self.vm_id} session released via API")

            # 2. Increment Usage Count
            self.usage_count += 1
            self.current_job_id = None

            # 3. Determine Next State
            if self.usage_count >= self.max_uses_before_refresh:
                self.logger.info(f"Max uses reached ({self.usage_count}/{self.max_uses_before_refresh}). Marking DIRTY for cleanup.")
                self.state = VMState.DIRTY
            else:
                self.logger.info(f"VM reusable ({self.usage_count}/{self.max_uses_before_refresh}). returning to READY.")
                self.state = VMState.READY

        except Exception as e:
            self.logger.error(f"Failed to release VM session: {e}")
            # If we can't cleanly release, we should probably recycle the VM to be safe
            self.state = VMState.DIRTY

    async def cleanup_and_revert(self) -> bool:
        """Destroy the instance."""
        self.state = VMState.MAINTENANCE
        self.logger.info("Destroying VM instance...")
        
        try:
            await self.hypervisor.stop_vm(self.instance_vmx_path, force=True)
            
            if await self.hypervisor.delete_vm(self.instance_vmx_path):
                self.usage_count = 0
                self.state = VMState.STOPPED
                self.session_info.ip = ""
                self.session_info.token = ""
                return True
            else:
                self.state = VMState.ERROR
                return False
        except Exception as e:
            self.logger.error(f"Cleanup failed: {e}")
            self.state = VMState.ERROR
            return False
    
    def get_status(self) -> Dict[str, Any]:
        return {
            "vm_id": self.vm_id,
            "state": self.state.value,
            "ip": self.session_info.ip,
            "usage_count": self.usage_count
        }


# ============================================================================
# VM ORCHESTRATOR
# ============================================================================

class VMOrchestrator:
    """
    Manages the pool.
    Concept: 
    1. Server calls acquire_vm_wait(software="cline").
    2. Orchestrator increments 'pending_requests'.
    3. Scheduler Loop sees pending requests and starts STOPPED VMs.
    4. acquire_vm_wait loops until it finds a READY VM.
    """
    
    def __init__(
        self,
        hypervisor: VMwareController,
        vm_configs: Dict[str, Dict[str, Any]],
        max_concurrency: int = 10,
        max_uses_before_refresh: int = 5
    ):
        self.hypervisor = hypervisor
        self.vm_configs = vm_configs
        self.max_concurrency = max_concurrency
        self.max_uses_before_refresh = max_uses_before_refresh
        
        self.vm_pool: Dict[str, VMInstance] = {}
        # Tracks how many VMs of a specific type are currently requested by clients
        self.pending_requests: Dict[str, int] = {} 
        
        self.logger = logging.getLogger(f"{__name__}.VMOrchestrator")
    
    async def initialize(self):
        # Pool is populated by orchestrator_init.py typically
        self.logger.info(f"Orchestrator initialized. Max concurrency: {self.max_concurrency}")

    def register_demand(self, software_type: str):
        """Signal that we need a VM of this type."""
        self.pending_requests[software_type] = self.pending_requests.get(software_type, 0) + 1
        self.logger.info(f"Demand registered for {software_type}. Total pending: {self.pending_requests[software_type]}")

    def fulfill_demand(self, software_type: str):
        """Signal that we got a VM."""
        if self.pending_requests.get(software_type, 0) > 0:
            self.pending_requests[software_type] -= 1

    async def scheduler_loop(self):
        """
        Background loop.
        1. Cleans DIRTY VMs.
        2. Starts STOPPED VMs if there is pending demand.
        """
        self.logger.info("Scheduler loop started")
        
        while True:
            try:
                active_count = sum(1 for v in self.vm_pool.values() 
                                 if v.state not in [VMState.STOPPED, VMState.RELEASED, VMState.ERROR, VMState.MAINTENANCE])
                
                # --- 1. CLEANUP DIRTY VMS ---
                # Prioritize cleanup to free up slots if we are near capacity
                dirty_vms = [v for v in self.vm_pool.values() if v.state == VMState.DIRTY]
                for vm in dirty_vms:
                    # Fire and forget cleanup
                    asyncio.create_task(vm.cleanup_and_revert())

                # --- 2. START NEW VMS BASED ON DEMAND ---
                for software_type, needed_count in self.pending_requests.items():
                    if needed_count <= 0: continue
                    
                    if active_count >= self.max_concurrency:
                        break # Cannot start more

                    # Count available and provisioning VMs
                    ready_count = sum(1 for v in self.vm_pool.values() 
                                    if v.software_type == software_type and v.state == VMState.READY)
                    busy_count = sum(1 for v in self.vm_pool.values() 
                                   if v.software_type == software_type and v.state == VMState.BUSY)
                    starting_count = sum(1 for v in self.vm_pool.values() 
                                       if v.software_type == software_type and v.state == VMState.STARTING)
                    
                    # Calculate how many VMs we currently have available or being provisioned
                    # READY VMs can serve new requests, BUSY are in use, STARTING will be ready soon
                    available_or_provisioning = ready_count + busy_count + starting_count
                    
                    # Only start new VMs if current capacity < pending demand
                    # This allows parallel execution while preventing over-provisioning
                    if available_or_provisioning >= needed_count:
                        continue

                    # Find a stopped candidate
                    candidate = next((v for v in self.vm_pool.values() 
                                      if v.state == VMState.STOPPED and v.software_type == software_type), None)
                    
                    if candidate:
                        self.logger.info(f"Spinning up {candidate.vm_id} to meet demand for {software_type} ({available_or_provisioning}/{needed_count} capacity)")
                        # Start asynchronously
                        asyncio.create_task(candidate.start())
                        active_count += 1
                
                await asyncio.sleep(2)
            
            except Exception as e:
                self.logger.error(f"Scheduler error: {e}")
                await asyncio.sleep(5)
    
    async def acquire_vm_wait(self, software_type: str, timeout: int = 300) -> VMInstance:
        """
        Called by Server. 
        1. Registers demand.
        2. Waits for a VM to become READY.
        3. Calls vm.acquire().
        """
        self.register_demand(software_type)
        start_time = time.time()
        
        try:
            while time.time() - start_time < timeout:
                # Find a READY VM of correct type
                candidate = next((v for v in self.vm_pool.values() 
                                  if v.software_type == software_type 
                                  and v.state == VMState.READY
                                  and not v._lock.locked()), None)
                
                if candidate:
                    # Attempt to lock it
                    if await candidate.acquire():
                        self.logger.info(f"Successfully acquired {candidate.vm_id}")
                        return candidate
                
                await asyncio.sleep(1)
            
            raise TimeoutError(f"No {software_type} VM available within {timeout}s")
            
        except Exception:
            # Reduce demand on failure/timeout
            self.fulfill_demand(software_type)
            raise

    # ========== MONITORING & STATUS ==========
    
    def get_active_count(self) -> int:
        """Count VMs not in STOPPED/RELEASED/ERROR state"""
        return sum(
            1 for vm in self.vm_pool.values()
            if vm.state not in [VMState.STOPPED, VMState.RELEASED, VMState.ERROR]
        )
    
    def get_ready_count(self) -> int:
        """Count VMs in READY state"""
        return sum(1 for vm in self.vm_pool.values() if vm.state == VMState.READY)
    
    def get_busy_count(self) -> int:
        """Count VMs executing jobs"""
        return sum(1 for vm in self.vm_pool.values() if vm.state == VMState.BUSY)
    
    def get_dirty_count(self) -> int:
        """Count VMs needing maintenance"""
        return sum(1 for vm in self.vm_pool.values() if vm.state == VMState.DIRTY)
    
    def get_vm_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all VMs"""
        return {vm_id: vm.get_status() for vm_id, vm in self.vm_pool.items()}
    
    def get_pool_status(self) -> Dict[str, Any]:
        """Get overall pool status"""
        return {
            "total_vms": len(self.vm_pool),
            "active_vms": self.get_active_count(),
            "ready_vms": self.get_ready_count(),
            "busy_vms": self.get_busy_count(),
            "dirty_vms": self.get_dirty_count(),
            "max_concurrency": self.max_concurrency,
        }
