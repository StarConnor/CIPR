import os
import json
import logging
import asyncio
import yaml
from typing import Dict, Any, List, Optional
from .vm_manager import (
    VMOrchestrator,
    VMwareController,
    VMwareRuntimeConfig,
    VMInstance,
    VMSessionInfo,
    VMState,
)

LOGGER = logging.getLogger(__name__)

# --- CONFIGURATION ---
VMWARE_CONFIG_PATH = os.getenv("VMWARE_CONFIG_PATH", "configs/vmware.local.yaml")

TEMP_VM_DIR = os.path.join(os.getcwd(), "temp_vms")
VM_POOL_CONFIG = os.path.join(TEMP_VM_DIR, "vm_pool.json")

_global_orchestrator: Optional[VMOrchestrator] = None
_scheduler_task: Optional[asyncio.Task] = None


def load_vmware_config() -> tuple[VMwareRuntimeConfig, Dict[str, str]]:
    path = os.getenv("VMWARE_CONFIG_PATH", VMWARE_CONFIG_PATH)
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"VMware configuration not found at {path}. "
            "Copy configs/vmware.example.yaml to configs/vmware.local.yaml "
            "and fill in the local VM paths."
        )
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"VMware configuration must be a YAML mapping: {path}")
    base_vms = data.get("base_vms") or {}
    if not isinstance(base_vms, dict):
        raise ValueError(f"base_vms must be a mapping: {path}")
    return VMwareRuntimeConfig.from_mapping(data), {
        str(name): str(value) for name, value in base_vms.items() if value
    }


async def initialize_orchestrator(
    software_types: Optional[List[str]] = None,
    max_concurrency: int = 10,
    max_uses_before_refresh: int = 100,
    use_mock_hypervisor: bool = False
) -> VMOrchestrator:
    global _global_orchestrator
    
    if _global_orchestrator is not None:
        return _global_orchestrator
    
    if not os.path.exists(TEMP_VM_DIR):
        os.makedirs(TEMP_VM_DIR)
        
    runtime_config, base_vm_paths = load_vmware_config()
    hypervisor = VMwareController(runtime_config)
    vm_configs: Dict[str, Dict[str, Any]] = {}
    
    if software_types is None:
        software_types = list(base_vm_paths.keys())
    
    # --- Load existing pool config if present ---
    existing_configs: Dict[str, Dict[str, Any]] = {}
    if os.path.exists(VM_POOL_CONFIG):
        try:
            with open(VM_POOL_CONFIG, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                existing_configs = data
                LOGGER.info(f"Found existing VM pool config with {len(existing_configs)} entries")
        except Exception as e:
            LOGGER.warning(f"Failed to read existing VM pool config: {e}")
    
    # Helper: ensure unique port assignment continues from max used
    def next_ports(start_slot: int) -> tuple[int, int, int]:
        ssh = 2222 + start_slot
        vnc = 5910 + start_slot
        return start_slot, ssh, vnc
    
    # Determine initial slot counter based on existing configs
    max_slot = 0
    for cfg in existing_configs.values():
        vnc = int(cfg.get("vnc_port", 0) or 0)
        if vnc >= 5910:
            slot = vnc - 5910
            if slot > max_slot: max_slot = slot
    slot_id = max_slot + 1
    
    # Build/merge vm_configs
    for sw_type in software_types:
        if sw_type not in base_vm_paths:
            continue
        base_path = base_vm_paths[sw_type]
        
        # Reuse any existing configs of this software type
        for vm_id, cfg in existing_configs.items():
            if cfg.get("software_type") != sw_type:
                continue
            # Validate instance path exists
            instance_path = cfg.get("instance_vmx_path")
            if not instance_path or not os.path.exists(instance_path):
                continue
            vm_configs[vm_id] = {
                "vm_id": vm_id,
                "software_type": sw_type,
                "base_vmx_path": base_path,
                "instance_vmx_path": instance_path,
                "ssh_port": int(cfg.get("ssh_port", 0)) or (2222 + max(1, (int(cfg.get("vnc_port", 5910)) - 5910))),
                "vnc_port": int(cfg.get("vnc_port", 0)) or (5910 + max(1, (int(cfg.get("ssh_port", 2223)) - 2222))),
            }
        
        # Create additional slots to reach a pool size of 5 per type
        existing_count = sum(1 for v in vm_configs.values() if v.get("software_type") == sw_type)
        to_create = max(0, 5 - existing_count)
        for i in range(to_create):
            vm_id = f"{sw_type}-worker-{existing_count + i + 1}"
            instance_path = os.path.join(TEMP_VM_DIR, vm_id, f"{vm_id}.vmx")
            slot_id, ssh_port, vnc_port = next_ports(slot_id)
            vm_configs[vm_id] = {
                "vm_id": vm_id,
                "software_type": sw_type,
                "base_vmx_path": base_path,
                "instance_vmx_path": instance_path,
                "ssh_port": ssh_port,
                "vnc_port": vnc_port,
            }
            slot_id += 1

    # Instantiate VM objects
    vm_pool: Dict[str, VMInstance] = {}
    for vm_id, config in vm_configs.items():
        session_info = VMSessionInfo(token="", ssh_port=config["ssh_port"], vnc_port=config["vnc_port"], ip="")
        
        vm = VMInstance(
            vm_id=vm_id,
            hypervisor=hypervisor,
            session_info=session_info,
            base_vmx_path=config["base_vmx_path"],
            instance_vmx_path=config["instance_vmx_path"],
            max_uses_before_refresh=max_uses_before_refresh,
            software_type=config["software_type"],
            runtime_config=runtime_config,
        )
        # If the instance clone already exists, try to detect its state
        try:
            if os.path.exists(config["instance_vmx_path"]):
                # If VM is running and healthy, mark READY and set IP
                if await hypervisor.is_vm_running(config["instance_vmx_path"]):
                    ip = await hypervisor.get_vm_ip(config["instance_vmx_path"], timeout=60)
                    if ip:
                        healthy = await hypervisor.health_check(ip)
                        if healthy:
                            vm.session_info.ip = ip
                            vm.state = VMState.READY
                            LOGGER.info(f"Detected existing READY VM {vm_id} at {ip} (VNC {config['vnc_port']})")
                        else:
                            vm.state = VMState.STOPPED
                    else:
                        vm.state = VMState.STOPPED
                else:
                    vm.state = VMState.STOPPED
        except Exception as e:
            LOGGER.warning(f"Failed to detect state for {vm_id}: {e}")
        vm_pool[vm_id] = vm

    _global_orchestrator = VMOrchestrator(hypervisor, vm_configs, max_concurrency, max_uses_before_refresh)
    _global_orchestrator.vm_pool = vm_pool
    
    await _global_orchestrator.initialize()
    # Persist the pool config for next startup
    try:
        with open(VM_POOL_CONFIG, "w", encoding="utf-8") as f:
            json.dump(vm_configs, f, indent=2)
    except Exception as e:
        LOGGER.warning(f"Failed to persist VM pool config: {e}")
    return _global_orchestrator


async def start_scheduler():
    global _scheduler_task, _global_orchestrator
    if _global_orchestrator is None: raise RuntimeError("Orchestrator not initialized.")
    
    if _scheduler_task is not None and not _scheduler_task.done():
        LOGGER.warning("Scheduler already running")
        return
    
    _scheduler_task = asyncio.create_task(_global_orchestrator.scheduler_loop())
    LOGGER.info("🚀 Scheduler loop started")


async def stop_scheduler():
    global _scheduler_task
    if _scheduler_task is not None and not _scheduler_task.done():
        _scheduler_task.cancel()
        try: await _scheduler_task
        except asyncio.CancelledError: pass
    LOGGER.info("🛑 Scheduler loop stopped")


def get_orchestrator() -> VMOrchestrator:
    if _global_orchestrator is None: raise RuntimeError("Orchestrator not initialized.")
    return _global_orchestrator


async def acquire_vm_for_session(software_type: str, timeout: int = 300) -> VMInstance:
    """
    Main entry point for Server.
    """
    orchestrator = get_orchestrator()
    # Use the new wait method in orchestrator
    vm = await orchestrator.acquire_vm_wait(software_type, timeout=timeout)
    return vm


async def release_vm_session(vm: VMInstance):
    try:
        await vm.release()
        LOGGER.info(f"Released VM {vm.vm_id}")
        
        # Fulfill the demand now that VM is released
        orchestrator = get_orchestrator()
        orchestrator.fulfill_demand(vm.software_type)
    except Exception as e:
        LOGGER.warning(f"Failed to release VM {vm.vm_id}: {e}")
