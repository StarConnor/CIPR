import asyncio
import os
import shutil
import threading
import pdb
import traceback
import yaml
import time
import json
import logging
import argparse
from functools import partial
from typing import Dict, Any, List, Set, Callable, Optional
from pathlib import Path
import asyncio
import logging
import pdb
from typing import Any, Dict 
from datetime import datetime

# from ..agent.screenshot_solver import auto_screenshot_solver
from ..agent.scorer_wrapper import wrap_scorer_with_reporting
from ..agent.ide_solver import vm_solve
from ..utils.log import set_task_id, set_sample_id
from ..utils.load_dataset import load_dataset, load_scorer
from ..attacks.session import AttackFeedback
from ..attacks.strategies.registry import build_attack_session
from ..environment_manager import EnvironmentManager
from ..orchestrator_init import acquire_vm_for_session, release_vm_session
from ..vm_manager import VMInstance
from ..config import MODEL_NAME_MAPPING
from ..utils.runtime_toolchain_mounts import normalize_runtime_languages
from ..utils.others import _sanitize_for_json

# Import your helper classes
from ..custom_types import TaskState, AttackStrategyConfig, Sample, RunnerResult, ServerConfig, ExperimentConfig
from ..utils.container_prep import container_preparation

# Use standard logging instead of setup_logging to ensure proper propagation
LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)

# Add console handler to root if not already present
if not any(isinstance(h, logging.StreamHandler) for h in LOGGER.handlers):
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)  # Only INFO and above to console
    formatter = logging.Formatter('[%(task_id)s] %(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    LOGGER.addHandler(console_handler)


MAX_ATTEMPTS = 2


# Result files are shared by all RedTeamRunner instances in this Python process.
# A per-instance lock is not enough when two client requests run the same
# dataset/software/model at the same time.  These process-wide locks/cache avoid
# corrupting or losing entries and avoid re-reading the whole JSON file on every
# sample completion.
_RESULT_FILE_LOCKS: dict[str, threading.RLock] = {}
_RESULT_FILE_LOCKS_GUARD = threading.Lock()
_RESULT_FILE_CACHE: dict[str, dict[str, Any]] = {}


def _get_result_file_lock(path: Path) -> threading.RLock:
    key = str(path.resolve())
    with _RESULT_FILE_LOCKS_GUARD:
        lock = _RESULT_FILE_LOCKS.get(key)
        if lock is None:
            lock = threading.RLock()
            _RESULT_FILE_LOCKS[key] = lock
        return lock


def _load_result_file_from_disk(path: Path, logger: logging.LoggerAdapter | None = None) -> list[dict[str, Any]]:
    if not path.exists():
        return []

    try:
        content = path.read_text(encoding="utf-8").replace("\x00", "")
        if not content.strip():
            return []
        loaded = json.loads(content)
        if isinstance(loaded, list):
            return [item for item in loaded if isinstance(item, dict)]
        if logger:
            logger.warning(f"Result file {path} is not a JSON list; ignoring content")
        return []
    except Exception as e:
        if logger:
            logger.warning(f"Failed to load results from {path}: {e}")
        return []


def _ensure_result_file_cache(path: Path, logger: logging.LoggerAdapter | None = None) -> dict[str, Any]:
    """
    Must be called while holding _get_result_file_lock(path).
    Cache is invalidated if another process changed the file mtime.
    """
    key = str(path.resolve())
    mtime_ns = path.stat().st_mtime_ns if path.exists() else None
    cached = _RESULT_FILE_CACHE.get(key)
    if cached is not None and cached.get("mtime_ns") == mtime_ns:
        return cached

    results = _load_result_file_from_disk(path, logger=logger)
    by_sample_id: dict[str, dict[str, Any]] = {}
    for item in results:
        sample_id = item.get("sample_id")
        if sample_id:
            by_sample_id[sample_id] = item

    cached = {
        "mtime_ns": mtime_ns,
        "results": results,
        "by_sample_id": by_sample_id,
    }
    _RESULT_FILE_CACHE[key] = cached
    return cached

class TaggedQueue:
    """
    Wraps an asyncio.Queue to automatically tag items with a sample_id.
    Used for the frame_queue so the solver doesn't need to know about sample_ids.
    """
    def __init__(self, original_queue: asyncio.Queue, sample_id: str, main_loop: asyncio.AbstractEventLoop):
        self.queue = original_queue
        self.sample_id = sample_id
        self.main_loop = main_loop

    def put_nowait(self, item):
        # Wrap the raw item (bytes) into a dict
        payload = {
            "type": "frame",
            "data": item,  # This is the raw image bytes
            "sample_id": self.sample_id
        }
        # Use the thread-safe approach used in your original code
        self.main_loop.call_soon_threadsafe(self.queue.put_nowait, payload)

    async def put(self, item):
        payload = {
            "type": "frame",
            "data": item,
            "sample_id": self.sample_id
        }
        # For async put, we just use call_soon_threadsafe for simplicity 
        # as we are crossing thread boundaries usually
        self.main_loop.call_soon_threadsafe(self.queue.put_nowait, payload)

class RedTeamRunner:
    def __init__(self, 
        exp_config: ExperimentConfig,
        queues: Dict[str, asyncio.Queue],
        loop: asyncio.AbstractEventLoop,
        task_id: str = "default_task",
        server_config: ServerConfig = ServerConfig(),
    ):
        self.exp_config = exp_config
        self.server_config = server_config
        self.queues = queues
        self.main_loop = loop or asyncio.get_event_loop()
        self.task_id = task_id


        ########################### ExperimentConfig ##########################################
        self.agent = self.exp_config.agent
        self.software = self.exp_config.agent.software
        self.attack_method_name = self.exp_config.attack_method_name
        self.env_image_name = self.exp_config.env_image_name

        ##### Dataset Settings ######
        self.dataset_name = self.exp_config.dataset_name
        self.filter_dict = self.exp_config.filter_dict or {}

        ##### Parallellism Settings ######
        self.concurrency = self.exp_config.concurrency

        ##### Evaluation Settings #####
        self.skip_completed = self.exp_config.skip_completed
        self.stream_skipped_results = self.exp_config.stream_skipped_results
        self.user = self.exp_config.user
        self.screenshot_time = self.exp_config.screenshot_time or 1.0
        self.log_level = self.exp_config.log_level
        self.debug_port = self.exp_config.debug_port

        ########################### ExperimentConfig ##########################################

        self.results_dir = os.path.join(self.server_config.results_base_path, self.user)
        self.log_path = os.path.join("exp", self.task_id)

        self.result_file_path = self._generate_result_file_path()
        self.result_file_lock = _get_result_file_lock(self.result_file_path)
        
        self.logger = logging.LoggerAdapter(LOGGER, {'task_id': self.task_id})
        
        self.logger.info(f"Initialized RedTeamRunner with dataset: {self.dataset_name}, attack method: {self.attack_method_name}, Batch Size: {self.concurrency}")
        self.logger.info(f"Result file: {self.result_file_path}")
        
        self.completed_experiments: Dict[str, Any] = self._load_completed_experiments() if self.skip_completed else {}

        if self.skip_completed:
            self.logger.info(f"Skip completed: enabled, found {len(self.completed_experiments)} completed experiments")
    
    def _generate_result_file_path(self) -> Path:
        """
        Generate a stable result file path based on the run configuration.
        Same configuration will always use the same file, enabling resume functionality.
        Format: results/{dataset}_{attack_method}_{software}_{model}.json
        """
        # Create results directory if not exists
        results_dir = Path(self.results_dir)
        results_dir.mkdir(exist_ok=True, parents=True)
        
        # Clean model name for filename (remove special characters)
        clean_model = self.agent.model.model_name.replace('/', '_').replace(':', '_')
        clean_attack = self.attack_method_name.replace('/', '_').replace(':', '_') if self.attack_method_name else 'no_attack'
        
        # Create filename without timestamp - same config = same file
        if not self.exp_config.defense.enabled:
            filename = f"{self.dataset_name}_{clean_attack}_{self.software}_{clean_model}.json"
        else:
            hash_defense = str(hash(json.dumps(self.exp_config.defense.model_dump(), sort_keys=True)))[1:8]
            filename = f"{self.dataset_name}_{clean_attack}_{self.software}_{clean_model}_{hash_defense}.json"
        
        return results_dir / filename
    
    def _load_completed_experiments(self) -> Dict[str, Any]:
        """
        Load completed experiment sample IDs from the result file if it exists.
        Returns a set of completed sample_ids.
        """
        completed: Dict[str, Any] = {}
        
        if not self.result_file_path.exists():
            self.logger.info(f"No existing result file found at {self.result_file_path}. Starting fresh.")
            return completed
        
        with self.result_file_lock:
            cache = _ensure_result_file_cache(self.result_file_path, logger=self.logger)
            for sample_id, result in cache["by_sample_id"].items():
                if result.get("status") == "success":
                    completed[sample_id] = result

        self.logger.info(f"Loaded {len(completed)} completed experiments from {self.result_file_path.name}")
        
        return completed
    
    def _is_experiment_completed(self, sample_id: str, sample: Sample) -> bool:
        """
        Check if an experiment with the given sample_id has been completed.
        """
        if sample_id in self.completed_experiments.keys():
            completed_sample = self.completed_experiments[sample_id].get("sample", {})
            if completed_sample == sample.model_dump():
                return True
            else:
                pdb.set_trace()
                self.logger.warning(f"Sample ID {sample_id} marked as completed but the sample data has changed. Re-running experiment...")
                return False
    
    def _save_result_incremental(self, result: Dict[str, Any]):
        with self.result_file_lock:
            try:
                cache = _ensure_result_file_cache(self.result_file_path, logger=self.logger)
                results: list[dict[str, Any]] = cache["results"]
                by_sample_id: dict[str, dict[str, Any]] = cache["by_sample_id"]

                sanitized_result = _sanitize_for_json(result)
                sample_id = sanitized_result.get("sample_id")

                # Replace the existing entry for this sample instead of appending
                # duplicates.  This keeps resume-state small and deterministic.
                if sample_id and sample_id in by_sample_id:
                    old_obj = by_sample_id[sample_id]
                    try:
                        idx = results.index(old_obj)
                        results[idx] = sanitized_result
                    except ValueError:
                        results.append(sanitized_result)
                    by_sample_id[sample_id] = sanitized_result
                else:
                    results.append(sanitized_result)
                    if sample_id:
                        by_sample_id[sample_id] = sanitized_result

                self.result_file_path.parent.mkdir(parents=True, exist_ok=True)
                tmp_path = self.result_file_path.with_suffix(self.result_file_path.suffix + f".tmp.{os.getpid()}.{threading.get_ident()}")
                indent_env = os.getenv("RESULT_JSON_INDENT", "0").strip()
                json_indent = int(indent_env) if indent_env and indent_env != "0" else None
                with open(tmp_path, 'w', encoding="utf-8") as f:
                    json.dump(
                        results,
                        f,
                        indent=json_indent,
                        ensure_ascii=False,
                        default=str,
                        separators=None if json_indent else (",", ":"),
                    )
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp_path, self.result_file_path)

                cache["mtime_ns"] = self.result_file_path.stat().st_mtime_ns
            except Exception as e:
                self.logger.error(f"Failed to save result: {e}", exc_info=True)
                try:
                    if 'tmp_path' in locals() and tmp_path.exists():
                        tmp_path.unlink()
                except Exception:
                    pass

    def _save_sample_artifact(self, result: RunnerResult) -> None:
        """Write a per-sample terminal record alongside local logs and frames."""
        safe_sample_id = "".join(c if c.isalnum() or c in "._-" else "_" for c in result.sample_id)[:180]
        sample_dir = Path(self.log_path) / "samples" / safe_sample_id
        sample_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = sample_dir / "result.json"
        artifact_path.write_text(
            json.dumps(_sanitize_for_json(result.model_dump()), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _save_sample_container_logs(self, sample_id: str, manager: EnvironmentManager) -> None:
        """Place cleanup-time container diagnostics beside their sample record.

        Some automation-server versions do not emit log SSE events even when
        ``stream_logs`` is requested. Docker logs are the reliable fallback.
        """
        safe_sample_id = "".join(c if c.isalnum() or c in "._-" else "_" for c in sample_id)[:180]
        sample_dir = Path(self.log_path) / "samples" / safe_sample_id
        sample_dir.mkdir(parents=True, exist_ok=True)
        for environment_name, environment in manager.environments.items():
            container_name = getattr(environment, "container_name", None)
            if not container_name:
                continue
            source = Path(self.log_path) / f"{container_name}.log"
            if not source.exists():
                continue
            safe_environment_name = "".join(
                c if c.isalnum() or c in "._-" else "_" for c in str(environment_name)
            )
            destination = sample_dir / f"{safe_environment_name}.container.log"
            try:
                shutil.copyfile(source, destination)
            except OSError as exc:
                self.logger.warning("Could not save sample container log %s: %s", source, exc)

    def _resolve_runtime_languages_for_sample(self, sample: Sample) -> list[str]:
        candidates: list[Any] = []
        if isinstance(self.filter_dict, dict):
            candidates.append(self.filter_dict.get("language"))
            candidates.append(self.filter_dict.get("languages"))

        metadata = sample.metadata if isinstance(sample.metadata, dict) else {}
        candidates.append(metadata.get("language"))
        candidates.append(metadata.get("languages"))

        resolved: list[str] = []
        seen: set[str] = set()
        for candidate in candidates:
            if candidate is None:
                continue
            try:
                normalized = normalize_runtime_languages(candidate)
            except ValueError as exc:
                self.logger.warning(f"Ignoring invalid runtime language config '{candidate}': {exc}")
                continue

            for language in normalized:
                if language not in seen:
                    seen.add(language)
                    resolved.append(language)
        return resolved

    async def run_single_sample(
        self,
        sample: Sample,
        scorers: Dict[str, Callable] | None = None,
        container_preparation_fn: Callable | None = None,
        sample_id: str | None = None,
        headers: Dict | None = None,
        vm: VMInstance | None = None,
        save_result: bool = True,
    ) -> RunnerResult:
        """
        Run a single sample through the evaluation pipeline.
        
        Args:
            sample: The sample to evaluate
            file_attacks: List of file attacks to inject
            scorers: List of scorer functions to evaluate results
            container_preparation_fn: Function to prepare the container environment
            sample_id: Unique identifier for this sample run
            headers: VM session headers (for IDE mode)
            vm_ip: VM IP address (for IDE mode)
            vm_ssh_port: VM SSH port (for IDE mode)
            save_result: Whether to save the result to file
            
        Returns:
            RunnerResult containing the evaluation result
        """
        scorers = scorers or {}
        sample_id = sample_id or f"sample_{sample.id}_{int(time.time())}"
        
        # Setup Environment Manager
        attacker_manager_args: dict[str, Any] = {
            "agent": self.agent,
            "log_path": self.log_path,
            "task_id": self.task_id,
            "debug_port": self.debug_port,
            "env_image_name": self.env_image_name if self.env_image_name else None,
            "runtime_languages": sample.metadata.get("repo", {}).get("toolchains") if sample.metadata and isinstance(sample.metadata, dict) else [sample.language],
            "runtime_toolchain_root": "./docker_prep/languages/toolchains",
            "https_proxy": self.exp_config.https_proxy,
            "host_ip": self.exp_config.host_ip,
        }
        
        if headers and vm:
            attacker_manager_args.update({
                "vm_ip": vm.session_info.ip,
                "vm_ssh_port": vm.session_info.ssh_port,
            })
        if sample.attacker_domain:
            attacker_manager_args["attacker_domain"] = sample.attacker_domain
        if sample.html_domain:
            attacker_manager_args["html_domain"] = sample.html_domain
        
        # log_queue = self.queues.get("log") if self.queues else None
        # target_loop = self.main_loop
        attacker_manager = EnvironmentManager(**attacker_manager_args)

        def run_solver_isolated(solver_func, task_id_for_thread, sample_id_for_thread):
            set_task_id(task_id_for_thread)
            set_sample_id(sample_id_for_thread)

            new_thread_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_thread_loop)
            
            try:
                return new_thread_loop.run_until_complete(
                    solver_func()
                )
            finally:
                new_thread_loop.close()
        
        try:
            # Setup environment
            attacker_state = attacker_manager.setup()

            # Run container preparation if provided
            if container_preparation_fn:
                container_preparation_fn(
                    self.exp_config,
                    sample,
                    attacker_state.code_server_container.container,
                    attacker_manager.web_server.ports['8080/tcp'],
                    attacker_manager.web_server.ports['8081/tcp'],
                    workspace_base_path=self.server_config.workspace_base_path,
                )

            raw_frame_queue = self.queues['frame'] if self.queues else None
            tagged_frame_queue = None
            if raw_frame_queue:
                tagged_frame_queue = TaggedQueue(raw_frame_queue, sample_id, self.main_loop)

            # Create scorer
            assert self.queues is not None, "Queues must be provided for scoring"
            scorer = wrap_scorer_with_reporting(
                scorers,
                result_queue=self.queues['result'],
                loop=self.main_loop
            )
            
            start_time = time.time()
            self.logger.info(f"🚀 [Worker] Running Task: {sample_id}")
            
            # Create task state
            state = TaskState(
                sample=sample,
                exp_config=self.exp_config,
                env_state=attacker_state,
                epoch=0,
            )
            
            # Run solver and scorer
            current_loop = asyncio.get_running_loop()

            solve_func = partial(
                vm_solve,
                state=state,
                agent=self.exp_config.agent,
                vm_config_path=self.server_config.vm_config_path,
                screenshot_time=self.screenshot_time,
                manager=attacker_manager,
                vm=vm,
                frame_queue=tagged_frame_queue,
                main_loop=asyncio.get_running_loop(),
                log_level=self.log_level,
                debug_port=self.debug_port,
                stream_screenshots=self.exp_config.stream_frames,
                stream_logs=self.exp_config.stream_logs,
            )
        
            result_state = await current_loop.run_in_executor(
                None,  # Use default ThreadPoolExecutor
                run_solver_isolated,
                solve_func,
                self.task_id,
                sample_id,
            )
            result = await scorer(result_state)
            
            # Prepare result data - return RunnerResult object
            result_data = RunnerResult(
                sample_id=str(sample_id),
                status="success",
                timestamp=datetime.now().isoformat(),
                result=result,
                stats={
                    "started_at": start_time,
                    "completed_at": time.time(),
                    "duration": time.time() - start_time
                },
                sample=sample,
            )
            
            # Save result if requested
            if save_result:
                self._save_result_incremental(result_data.model_dump())
            self._save_sample_artifact(result_data)
            
            return result_data
        except asyncio.CancelledError:
            self.logger.warning("🛑 Task cancelled! Cleaning up immediately...")
            if headers and vm:
                self.logger.info(f"📡 [Worker] Sending cancellation signal to Remote Server {vm.session_info.ip}...")
                try:
                    import requests
                    # The VM API port is usually 8000 based on your code
                    cancel_url = f"http://{vm.session_info.ip}:8000/api/v1/session/cancel_execution"
                    
                    # We use a short timeout because we don't want to block cleanup
                    requests.post(cancel_url, headers=headers, timeout=10.0)
                    
                except Exception as e:
                    self.logger.warning(f"⚠️ Failed to cancel remote session: {e}")
            raise
        except Exception as exc:
            error_data = RunnerResult(
                sample_id=str(sample_id),
                status="error",
                timestamp=datetime.now().isoformat(),
                stats={
                    "started_at": start_time if "start_time" in locals() else time.time(),
                    "completed_at": time.time(),
                    "duration": time.time() - start_time if "start_time" in locals() else 0.0,
                },
                sample=sample,
                error=f"{type(exc).__name__}: {exc}",
            )
            if save_result:
                self._save_result_incremental(error_data.model_dump())
            self._save_sample_artifact(error_data)
            self.logger.exception("Sample %s failed; persisted error artifact", sample_id)
            return error_data
            
        finally:
            # Cleanup environment
            self.logger.info("🧹 [Worker] Cleaning up Environment for current context...")
            
            try:
                attacker_manager.cleanup()
                self._save_sample_container_logs(str(sample_id), attacker_manager)
            except Exception as e:
                self.logger.warning(f"⚠️ Error during environment cleanup: {e}")

    async def _process_sample_flow(self, sample: Sample, dataset_scorer: Callable, semaphore: asyncio.Semaphore) -> Optional[RunnerResult]:
        """
        Handles the full lifecycle of a SINGLE sample with parallel support:
        1. Checks skip logic
        2. Acquires resources (VM)
        3. Runs attack loop (retries) with Infrastructure Retry Support
        4. Releases resources
        """
        async with semaphore:
            base_sample_id = f"{self.dataset_name}_{self.attack_method_name}_{sample.id}"
            token = set_sample_id(base_sample_id)
            
            if self.skip_completed and self._is_experiment_completed(base_sample_id, sample):
                self.logger.info(f"⏭️  Skipping completed experiment: {base_sample_id}")

                if not self.stream_skipped_results:
                    self.logger.info(f"[{base_sample_id}] Skipped result not streamed; fetch it from the completed-results endpoint if needed.")
                    return None

                try:
                    result_queue = self.queues.get("result") if self.queues else None
                    result_payload = self.completed_experiments.get(base_sample_id, {}).get("result", None)
                    if result_queue is None:
                        self.logger.error(f"[{base_sample_id}] CRITICAL ERROR: result_queue is None")
                        return None
                    if result_payload is None:
                        self.logger.error(f"[{base_sample_id}] CRITICAL ERROR: result_payload is None (experiment marked completed but data missing)")
                        return None
                    self.main_loop.call_soon_threadsafe(result_queue.put_nowait, result_payload)
                    self.logger.info(f"[{base_sample_id}] Skipped result replay scheduled. Payload keys: {list(result_payload.keys()) if isinstance(result_payload, dict) else 'N/A'}")
                except Exception as e:
                    self.logger.error(f"[{base_sample_id}] CRITICAL ERROR pushing to queue: {e}")
                return None

            self.logger.info(f"▶️  Starting Sample ID: {sample.id}")

            vm = None
            headers = {}
            
            try:
                if self.software.endswith("ide"):
                    try:
                        vm = await acquire_vm_for_session(software_type=self.software)
                        headers = vm.session_info.headers
                        self.logger.info(f"[{sample.id}] Acquired VM {vm.vm_id} (IP: {vm.session_info.ip}) (VNC port: {vm.session_info.vnc_port})")
                    except Exception as e:
                        self.logger.error(f"[{sample.id}] Failed to acquire VM: {e}")
                        return RunnerResult(
                            sample_id=base_sample_id,
                            sample=sample,
                            status="error",
                            error="VM Acquisition Failed",
                            timestamp=datetime.now().isoformat(),
                        )

                session_config = AttackStrategyConfig(
                    mode=self.attack_method_name.split('_')[-1],
                    model=self.exp_config.attack_model_name,
                    base_url=os.environ.get("ATTACK_LLM_BASE_URL", "https://api.gpt.ge/v1"),
                    api_key=os.environ.get("ATTACK_LLM_API_KEY", os.environ.get("AGENT_API_KEY", "")),
                    max_rounds=MAX_ATTEMPTS,
                )
                attack_session = build_attack_session(self.attack_method_name, sample, session_config)
                
                attempt = attack_session.start(sample)
                attempt_idx = 0
                final_result = None

                while attempt:
                    processed_sample = attempt.sample if attempt.sample else sample
                    final_scorers = {"default_scorer": dataset_scorer}
                    
                    try:
                        result_data = await self.run_single_sample(
                            sample=processed_sample,
                            scorers=final_scorers,
                            container_preparation_fn=container_preparation,
                            sample_id=base_sample_id,
                            headers=headers,
                            vm=vm,
                            save_result=True,
                        )

                        # --- LOGIC FOR ATTACK SUCCESS/FAILURE (SCORER) ---
                        scorer_result = result_data.result if result_data.result else None
                        scorer_status = (scorer_result.task_success if scorer_result else "success").lower()
                        attack_status = result_data.result.attack_success if result_data.result else "failure"

                        if attack_status == "success":
                            result_data.metadata.update({
                                "attack_attempt": attempt_idx,
                                "attack_payload": attempt.metadata,
                            })
                            result_data.attempts = attempt_idx + 1
                            final_result = result_data
                            break
                        
                        # --- SCORER SAID FAILURE: GENERATE NEW ATTACK ---
                        feedback_messages = [f"Scorer status: {scorer_status}"]
                        env_feedback = {}
                        if scorer_result and scorer_result.feedback:
                            if 'messages' in scorer_result.feedback:
                                feedback_messages.extend(scorer_result.feedback['messages'])
                            if 'env' in scorer_result.feedback:
                                env_feedback.update(scorer_result.feedback['env'])

                        feedback = AttackFeedback(
                            status="failure",
                            messages=feedback_messages,
                            env=env_feedback,
                            scorer=scorer_result.model_dump() if scorer_result else {},
                        )
                        next_attempt = attack_session.next_attempt(feedback)
                        attempt_idx += 1

                        if next_attempt is None:
                            break

                        attempt = next_attempt

                    except Exception as e:
                        # --- LOGIC FOR INFRASTRUCTURE ERROR (EXCEPTION) ---
                        traceback.print_exception(e)
                        self.logger.error(f"❌ [{sample.id}] Exception during execution: {e}")
                        
                        attempt_idx += 1
                        
                        if attempt_idx < MAX_ATTEMPTS and "IDE interaction failed" not in str(e):
                            self.logger.info(f"🔄 [{sample.id}] Infrastructure error detected ({type(e).__name__}). Retrying SAME attack payload (Attempt {attempt_idx}/{MAX_ATTEMPTS})...")
                            time.sleep(2)
                            # Continue loop without calling next_attempt()
                            # This re-uses the current 'attempt' object
                            continue
                        else:
                            self.logger.error(f"❌ [{sample.id}] Failed after {attempt_idx} attempts (Infrastructure error)", exc_info=True)
                            final_result = RunnerResult(
                                sample_id=base_sample_id,
                                status="error",
                                error=f"Infrastructure error after {attempt_idx} attempts: {str(e)}",
                                timestamp=datetime.now().isoformat(),
                                attempts=attempt_idx,
                                attack_payload=attempt.metadata,
                                sample=sample,
                            )
                            self._save_result_incremental(final_result.model_dump())
                            break

                return final_result

            finally:
                if self.software.endswith("ide") and vm is not None:
                    try:
                        await release_vm_session(vm)
                        self.logger.info(f"[{sample.id}] Released VM {vm.vm_id}")
                    except Exception as e:
                        self.logger.warning(f"Failed to release VM: {e}")

    async def _run_inner(self) -> List[RunnerResult]:
        try:
            samples = load_dataset(self.dataset_name, filter_dict=self.filter_dict, dataset_base_path=self.server_config.dataset_base_path, k_runs=self.exp_config.k_runs, sample_n=self.exp_config.sample_n)
            dataset_scorer = load_scorer(self.dataset_name, filter_dict=self.filter_dict, dataset_base_path=self.server_config.dataset_base_path)
        except Exception as e:
            self.logger.error(f"Failed to load dataset: {e}")
            return []

        num_total_samples = len(samples)
        self.logger.info(f"Starting execution for {num_total_samples} samples with Concurrency={self.concurrency}")

        semaphore = asyncio.Semaphore(self.concurrency)
        
        # Progress tracking
        completed_count = 0
        progress_lock = asyncio.Lock()
        
        async def track_progress(sample, dataset_scorer, semaphore):
            """Wrapper to track completion progress"""
            nonlocal completed_count
            result = await self._process_sample_flow(sample, dataset_scorer, semaphore)
            
            async with progress_lock:
                completed_count += 1
                self.logger.info(f"======{completed_count}/{num_total_samples}========")
            
            return result
        
        tasks = []
        for sample in samples:
            task = asyncio.create_task(
                track_progress(sample, dataset_scorer, semaphore)
            )
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        clean_results = []
        for r in results:
            if isinstance(r, Exception):
                self.logger.error(f"Task failed with exception: {r}")
            elif r is not None:
                clean_results.append(r)

        self.logger.info(f"🎉 Run completed! Results saved to: {self.result_file_path}")
        return clean_results

    def run(self) -> List[RunnerResult]:
        try:
            return asyncio.run(self._run_inner())
        except Exception as e:
            self.logger.critical(f"Runner thread failed: {e}", exc_info=True)
            raise
