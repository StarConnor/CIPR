#!/usr/bin/env python3
"""
Standalone local runner for CLI coding-agent redteam experiments.

Goals:
- No client/server process and no WebSocket/HTTP result streaming.
- Reuse the same core ExperimentConfig/RedTeamRunner/container_preparation path as
  the server implementation, so local results are schema-compatible.
- Support both single-sample debugging and dataset-level parallel execution.
- Support CLI agents only. IDE/VM agents are intentionally rejected.

Examples:
  # Single sample
  uv run python standalone/run_local_exp.py \
    --dataset ciir \
    --sample-id r_yarrick__iodine_p_exfil_001_c_llm_t_run_test \
    --agent opencode_cli \
    --model deepseek-v4-pro \
    --run-name debug-iodine

  # Dataset run with local container parallelism
  uv run python standalone/run_local_exp.py \
    --dataset ciir \
    --agent opencode_cli \
    --model deepseek-v4-pro \
    --concurrency 8 \
    --sample-n 100 \
    --run-name ciir-opencode-deepseek-100

  # Use a server-compatible ExperimentConfig JSON as input, overriding only paths
  uv run python standalone/run_local_exp.py --request-json request.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import time
import uuid
import threading
from pathlib import Path
from typing import Any, Optional

# Add parent directory to path so we can import src, and run from project root so
# existing relative paths in configs/docker_prep/temp_workspace keep working.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

from src.agent_red.custom_types import AgentConfig, ExperimentConfig, ModelConfig, RunnerResult, ServerConfig
from src.agent_red.engine.runner import RedTeamRunner
from src.agent_red.scorer import default_scorer
from src.agent_red.utils.container_prep import container_preparation
from src.agent_red.utils.load_dataset import load_dataset


LOGGER = logging.getLogger("StandaloneLocalRunner")


class InlineCallbackLoop:
    """Tiny loop facade for queue callbacks in standalone mode.

    RedTeamRunner/scorer_wrapper call loop.call_soon_threadsafe(...) to enqueue
    messages for the server's WebSocket pushers. Here there is no server loop,
    so execute the callback immediately. With NullQueue this is a no-op.
    """

    def call_soon_threadsafe(self, callback: Any, *args: Any) -> None:
        callback(*args)


class NullQueue:
    """In-process no-op queue used to satisfy RedTeamRunner's queue interface.

    The server uses asyncio queues to forward frames/results/logs to WebSocket or
    HTTP clients. In standalone mode there is no client to stream to, and the
    authoritative result is written by RedTeamRunner to the local JSON result
    file. Dropping queued items avoids both network transfer and large in-memory
    duplicate result buffers.
    """

    def put_nowait(self, _item: Any) -> None:
        return None

    def __bool__(self) -> bool:
        # Prevent frame streaming wrappers from being created.
        return False


class LocalFrameQueue:
    """Save streamed screenshot frames to local files/videos in standalone mode."""

    def __init__(self, task_id: str, fps: float = 30.0):
        self.frame_dir = PROJECT_ROOT / "exp" / task_id / "frames"
        self.frame_dir.mkdir(parents=True, exist_ok=True)
        self.fps = fps
        self._counter = 0
        self._lock = threading.Lock()
        self._video_writers: dict[str, Any] = {}
        self._frame_dimensions: dict[str, tuple[int, int]] = {}
        self._cv2 = None
        self._np = None
        self._video_disabled_reason: str | None = None

    @staticmethod
    def _safe_sample_id(sample_id: str) -> str:
        return "".join(c if c.isalnum() or c in "._-" else "_" for c in sample_id)[:180]

    def _ensure_video_deps(self) -> bool:
        if self._video_disabled_reason:
            return False
        if self._cv2 is not None and self._np is not None:
            return True
        try:
            import cv2  # type: ignore
            import numpy as np  # type: ignore
            self._cv2 = cv2
            self._np = np
            return True
        except Exception as exc:
            self._video_disabled_reason = str(exc)
            LOGGER.warning("Video recording disabled because OpenCV/numpy is unavailable: %s", exc)
            return False

    def _write_video_frame(self, safe_sample_id: str, data: bytes) -> None:
        if not self._ensure_video_deps():
            return
        nparr = self._np.frombuffer(data, self._np.uint8)
        frame = self._cv2.imdecode(nparr, self._cv2.IMREAD_COLOR)
        if frame is None:
            return
        height, width = frame.shape[:2]
        if safe_sample_id not in self._video_writers:
            sample_frame_dir = self.frame_dir / safe_sample_id
            sample_frame_dir.mkdir(parents=True, exist_ok=True)
            video_path = sample_frame_dir / "trajectory.avi"
            fourcc = self._cv2.VideoWriter_fourcc(*"XVID")
            self._video_writers[safe_sample_id] = self._cv2.VideoWriter(str(video_path), fourcc, self.fps, (width, height))
            self._frame_dimensions[safe_sample_id] = (width, height)
        current_width, current_height = self._frame_dimensions[safe_sample_id]
        if (width, height) != (current_width, current_height):
            frame = self._cv2.resize(frame, (current_width, current_height))
        self._video_writers[safe_sample_id].write(frame)

    def put_nowait(self, item: Any) -> None:
        if item is None:
            self.close()
            return
        sample_id = "unknown"
        data = item
        if isinstance(item, dict):
            sample_id = str(item.get("sample_id") or sample_id)
            data = item.get("data")
        if not isinstance(data, (bytes, bytearray)):
            return
        data_bytes = bytes(data)
        safe_sample_id = self._safe_sample_id(sample_id)
        with self._lock:
            self._counter += 1
            # Refresh the current frame like test/run_exp.py did.
            sample_frame_dir = self.frame_dir / safe_sample_id
            sample_frame_dir.mkdir(parents=True, exist_ok=True)
            latest_path = sample_frame_dir / "latest.png"
            latest_path.write_bytes(data_bytes)
            self._write_video_frame(safe_sample_id, data_bytes)

    def close(self) -> None:
        with self._lock:
            for writer in self._video_writers.values():
                try:
                    writer.release()
                except Exception:
                    pass
            self._video_writers.clear()
            self._frame_dimensions.clear()

    def __bool__(self) -> bool:
        return True


class LocalResultQueue:
    """Print concise per-sample progress from scorer result payloads."""

    def __init__(self, total: int | None = None):
        self.total = total
        self._seen: set[str] = set()
        self._lock = threading.Lock()
        self._started_at = time.monotonic()

    @staticmethod
    def _format_duration(seconds: float) -> str:
        seconds = max(0, int(seconds))
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:d}h{minutes:02d}m{seconds:02d}s" if hours else f"{minutes:d}m{seconds:02d}s"

    def put_nowait(self, item: Any) -> None:
        if item is None or not isinstance(item, dict):
            return
        sample_id = str(item.get("sample_id") or "unknown")
        with self._lock:
            if sample_id in self._seen:
                return
            self._seen.add(sample_id)
            idx = len(self._seen)
        task_success = item.get("task_success", "?")
        attack_success = item.get("attack_success", "?")
        alert_success = item.get("alert_success", "?")
        commands = len(item.get("commands_executed") or [])
        total_part = f"/{self.total}" if self.total else ""
        LOGGER.info(
            "RESULT %s%s sample=%s task=%s attack=%s alert=%s commands=%d",
            idx,
            total_part,
            sample_id,
            task_success,
            attack_success,
            alert_success,
            commands,
        )
        elapsed = time.monotonic() - self._started_at
        if self.total:
            eta = (elapsed / idx) * (self.total - idx) if idx else 0
            LOGGER.info(
                "PROGRESS %d/%d (%.1f%%) elapsed=%s ETA≈%s",
                idx,
                self.total,
                100 * idx / self.total,
                self._format_duration(elapsed),
                self._format_duration(eta),
            )
        else:
            LOGGER.info("PROGRESS completed=%d elapsed=%s", idx, self._format_duration(elapsed))

    def __bool__(self) -> bool:
        return True


def build_local_queues(exp_config: ExperimentConfig, task_id: str, total_samples: int | None = None) -> dict[str, Any]:
    return {
        "frame": LocalFrameQueue(task_id) if exp_config.stream_frames else NullQueue(),
        "result": LocalResultQueue(total_samples),
        "log": NullQueue(),
    }

def parse_json_object(value: Optional[str], *, field_name: str) -> dict[str, Any]:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON for {field_name}: {exc}") from exc
    if not isinstance(parsed, dict):
        raise SystemExit(f"{field_name} must be a JSON object")
    return parsed


def load_request_json(path: Optional[str]) -> dict[str, Any]:
    if not path:
        return {}
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    # Accept either a raw ExperimentConfig object or the common API envelope
    # shape {"data": {...}} / {"request": {...}}.
    if isinstance(data, dict) and isinstance(data.get("data"), dict) and "agent" in data["data"]:
        data = data["data"]
    if isinstance(data, dict) and isinstance(data.get("request"), dict):
        data = data["request"]
    if not isinstance(data, dict):
        raise SystemExit("--request-json must contain a JSON object")
    return data


def make_run_name(args: argparse.Namespace, exp_values: dict[str, Any]) -> str:
    if args.run_name:
        return args.run_name
    if exp_values.get("user") and exp_values.get("user") != "default":
        return str(exp_values["user"])
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    suffix = uuid.uuid4().hex[:6]
    sample_part = args.sample_id or "dataset"
    return f"local-{exp_values['dataset_name']}-{exp_values['agent'].software}-{exp_values['agent'].model.model_name}-{sample_part}-{timestamp}-{suffix}"


def build_agent(args: argparse.Namespace, request_data: dict[str, Any]) -> AgentConfig:
    if "agent" in request_data:
        agent = AgentConfig.model_validate(request_data["agent"])
    else:
        model_args = parse_json_object(args.model_args_json, field_name="--model-args-json")
        agent = AgentConfig(
            software=args.agent or "cc_cli",
            model=ModelConfig(
                model_name=args.model or "gpt-4o-mini",
                api_provider=args.api_provider or "OpenAI Compatible",
                model_args=model_args,
            ),
        )

    # AgentConfig.model_post_init() intentionally loads model API settings from
    # env/vm config. Explicit CLI overrides should win in standalone mode.
    if args.agent is not None:
        agent.software = args.agent
    if args.model is not None:
        agent.model.model_name = args.model
    if args.api_provider is not None:
        agent.model.api_provider = args.api_provider
    if args.model_args_json is not None:
        agent.model.model_args = parse_json_object(args.model_args_json, field_name="--model-args-json")
    # Precedence: explicit CLI flags > request JSON / model-specific env loaded
    # by AgentConfig.get_model_api() > generic AGENT_* fallback.  The old logic
    # let AGENT_API_KEY override CODEX_API_KEY/DEEPSEEK_API_KEY, which made model
    # selection unexpectedly change credentials in standalone runs.
    if args.api_key:
        agent.model.api_key = args.api_key
    elif not agent.model.api_key and os.getenv("AGENT_API_KEY"):
        agent.model.api_key = os.getenv("AGENT_API_KEY", "")
    if args.api_base_url:
        agent.model.base_url = args.api_base_url
    elif not agent.model.base_url and os.getenv("AGENT_BASE_URL"):
        agent.model.base_url = os.getenv("AGENT_BASE_URL", "")

    if not agent.software.endswith("_cli"):
        raise SystemExit(
            f"Standalone local runner only supports CLI agents, got {agent.software!r}. "
            "IDE/VM agents still require the VM management path."
        )
    return agent


def build_exp_config(args: argparse.Namespace, request_data: dict[str, Any]) -> ExperimentConfig:
    agent = build_agent(args, request_data)

    base: dict[str, Any] = dict(request_data)
    dataset_name = args.dataset or base.get("dataset_name") or "ciir"
    attack_method = args.attack_method or base.get("attack_method_name") or "static_file"
    filter_dict = (
        parse_json_object(args.filter_json, field_name="--filter-json")
        if args.filter_json is not None
        else base.get("filter_dict", {})
    )

    sample_n = args.sample_n if args.sample_n is not None else base.get("sample_n", -1)
    k_runs = args.k_runs if args.k_runs is not None else base.get("k_runs", 1)

    if args.start_id and args.start_index is not None:
        raise SystemExit("--start-id and --start-index are mutually exclusive")
    if args.first_n is not None and (args.start_id or args.start_index is not None):
        raise SystemExit("--first-n cannot be used together with --start-id/--start-index")

    if args.first_n is not None:
        if args.sample_id:
            raise SystemExit("--first-n cannot be used together with --sample-id")
        if args.first_n <= 0:
            raise SystemExit("--first-n must be positive")
        selected_samples = load_dataset(
            dataset_name=dataset_name,
            dataset_base_path=args.data_path,
            filter_dict=filter_dict,
            k_runs=k_runs,
            sample_n=sample_n,
        )
        if args.first_n > len(selected_samples):
            raise SystemExit(
                f"--first-n={args.first_n} exceeds the {len(selected_samples)} samples "
                "available after filtering."
            )
        filter_dict = dict(filter_dict)
        filter_dict["id"] = [sample.id for sample in selected_samples[:args.first_n]]
        LOGGER.info("Prefix selection enabled: running the first %d/%d loaded samples", args.first_n, len(selected_samples))

    elif args.start_id or args.start_index is not None:
        if args.sample_id:
            raise SystemExit("--start-id/--start-index cannot be used together with --sample-id")

        # Compute the suffix in exactly the same order that the runner will see:
        # load dataset -> sample_n -> k_runs -> existing filter_dict.  Then encode
        # that suffix as an id filter, which RedTeamRunner already understands.
        selected_samples = load_dataset(
            dataset_name=dataset_name,
            dataset_base_path=args.data_path,
            filter_dict=filter_dict,
            k_runs=k_runs,
            sample_n=sample_n,
        )
        if args.start_id:
            start_pos = next((i for i, sample in enumerate(selected_samples) if sample.id == args.start_id), None)
            if start_pos is None:
                preview = ", ".join(sample.id for sample in selected_samples[:10])
                raise SystemExit(
                    f"--start-id {args.start_id!r} not found after applying sample_n/k_runs/filter_json. "
                    f"First ids: {preview}"
                )
        else:
            start_pos = args.start_index
            assert start_pos is not None
            if start_pos < 0 or start_pos >= len(selected_samples):
                raise SystemExit(
                    f"--start-index must be in [0, {max(len(selected_samples) - 1, 0)}], got {start_pos}"
                )

        suffix_ids = [sample.id for sample in selected_samples[start_pos:]]
        filter_dict = dict(filter_dict)
        filter_dict["id"] = suffix_ids
        LOGGER.info(
            "Start selection enabled: running %d/%d samples from %s",
            len(suffix_ids),
            len(selected_samples),
            args.start_id if args.start_id else f"index {args.start_index}",
        )

    exp_values: dict[str, Any] = {
        "agent": agent,
        "dataset_name": dataset_name,
        "attack_method_name": attack_method,
        "env_image_name": args.image if args.image is not None else base.get("env_image_name"),
        "filter_dict": filter_dict,
        "sample_n": sample_n,
        "k_runs": k_runs,
        "concurrency": args.concurrency if args.concurrency is not None else base.get("concurrency", 1),
        "skip_completed": args.skip_completed if args.skip_completed else base.get("skip_completed", False),
        "stream_skipped_results": False,
        "fail_immediately_on_error": args.fail_immediately_on_error if args.fail_immediately_on_error else base.get("fail_immediately_on_error", False),
        "screenshot_time": args.screenshot_time if args.screenshot_time is not None else base.get("screenshot_time", 1.0),
        "log_level": args.log_level or base.get("log_level", "INFO"),
        "debug_port": args.debug_port if args.debug_port is not None else base.get("debug_port", -1),
        "stream_frames": False if args.no_stream_frames else base.get("stream_frames", True),
        "stream_logs": False if args.no_stream_logs else base.get("stream_logs", True),
    }
    exp_values["mode"] = "single_sample" if args.sample_id else base.get("mode", "dataset")
    if args.sample_id:
        exp_values["mode"] = "single_sample"
    exp_values["user"] = make_run_name(args, {**base, **exp_values})

    if args.https_proxy is not None:
        exp_values["https_proxy"] = args.https_proxy
    elif "https_proxy" in base:
        exp_values["https_proxy"] = base["https_proxy"]
    if args.host_ip is not None:
        exp_values["host_ip"] = args.host_ip
    elif "host_ip" in base:
        exp_values["host_ip"] = base["host_ip"]

    base.update(exp_values)
    exp_config = ExperimentConfig.model_validate(base)

    # ExperimentConfig.model_post_init() reloads proxy/host from environment;
    # make explicit request/CLI values win after validation.
    if "https_proxy" in exp_values:
        exp_config.https_proxy = exp_values["https_proxy"]
    if "host_ip" in exp_values:
        exp_config.host_ip = exp_values["host_ip"]

    if args.sample_id:
        samples = load_dataset(
            dataset_name=exp_config.dataset_name,
            dataset_base_path=args.data_path,
            filter_dict={"id": [args.sample_id]},
        )
        if not samples:
            raise SystemExit(f"Sample {args.sample_id!r} not found in dataset {exp_config.dataset_name!r}")
        exp_config.sample = samples[0]
    elif exp_config.mode == "single_sample" and exp_config.sample is None:
        raise SystemExit("single_sample mode requires --sample-id or a sample in --request-json")

    return exp_config

def build_server_config(args: argparse.Namespace) -> ServerConfig:
    return ServerConfig(
        dataset_base_path=args.data_path,
        workspace_base_path=args.workspace_path,
        results_base_path=args.results_path,
        vm_config_path=args.vm_config_path,
    )


def build_runner(exp_config: ExperimentConfig, server_config: ServerConfig, task_id: str, loop: Any, total_samples: int | None = None) -> RedTeamRunner:
    return RedTeamRunner(
        exp_config=exp_config,
        queues=build_local_queues(exp_config, task_id, total_samples),
        loop=loop,
        task_id=task_id,
        server_config=server_config,
    )


def close_local_queues(runner: RedTeamRunner) -> None:
    for queue in getattr(runner, "queues", {}).values():
        close = getattr(queue, "close", None)
        if callable(close):
            close()


def log_single_result(result: RunnerResult) -> None:
    LOGGER.info("\n%s", "=" * 80)
    LOGGER.info("EXECUTION RESULT")
    LOGGER.info("%s", "=" * 80)
    LOGGER.info("Sample ID: %s", result.sample_id)
    LOGGER.info("Status: %s", result.status)
    LOGGER.info("Duration: %.2fs", result.stats.get("duration", 0.0))
    if result.result:
        evaluation = result.result
        LOGGER.info("Task Success: %s", evaluation.task_success)
        LOGGER.info("Attack Success: %s", evaluation.attack_success)
        LOGGER.info("Alert Success: %s", evaluation.alert_success)
        LOGGER.info("Commands Executed: %d", len(evaluation.commands_executed))
        LOGGER.info("Trace Messages: %d", len(evaluation.trace))
    elif result.error:
        LOGGER.warning("Error: %s", result.error)
    LOGGER.info("%s\n", "=" * 80)


async def run_single_sample(exp_config: ExperimentConfig, server_config: ServerConfig, task_id: str) -> RunnerResult:
    assert exp_config.sample is not None, "single-sample mode requires exp_config.sample"
    runner = build_runner(exp_config, server_config, task_id, InlineCallbackLoop(), total_samples=1)
    LOGGER.info("Running single sample locally: dataset=%s sample=%s agent=%s model=%s", exp_config.dataset_name, exp_config.sample.id, exp_config.agent.software, exp_config.agent.model.model_name)
    started_at = time.time()
    try:
        result = await runner.run_single_sample(
            sample=exp_config.sample,
            scorers={"default_scorer": default_scorer},
            container_preparation_fn=container_preparation,
            sample_id=exp_config.sample.id,
            headers={},
            vm=None,
            save_result=True,
        )
    except Exception as exc:
        # Infrastructure/workflow failures previously escaped before the core
        # runner reached its success-only persistence block. Record them in the
        # same result file so a failed smoke test remains inspectable.
        result = RunnerResult(
            sample_id=exp_config.sample.id,
            status="error",
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            stats={"started_at": started_at, "completed_at": time.time(), "duration": time.time() - started_at},
            sample=exp_config.sample,
            error=f"{type(exc).__name__}: {exc}",
        )
        runner._save_result_incremental(result.model_dump())
        LOGGER.exception("Single-sample execution failed; error result saved to %s", runner.result_file_path)
    finally:
        close_local_queues(runner)
    log_single_result(result)
    LOGGER.info("Result file: %s", runner.result_file_path)
    if exp_config.stream_frames:
        LOGGER.info("Frames/video saved under: %s", PROJECT_ROOT / "exp" / task_id / "frames")
    return result



def estimate_dataset_total(exp_config: ExperimentConfig, server_config: ServerConfig) -> int | None:
    try:
        samples = load_dataset(
            exp_config.dataset_name,
            filter_dict=exp_config.filter_dict,
            dataset_base_path=server_config.dataset_base_path,
            k_runs=exp_config.k_runs,
            sample_n=exp_config.sample_n,
        )
        return len(samples)
    except Exception as exc:
        LOGGER.warning("Could not estimate dataset total: %s", exc)
        return None

def run_dataset(exp_config: ExperimentConfig, server_config: ServerConfig, task_id: str) -> list[RunnerResult]:
    # RedTeamRunner.run() owns its event loop via asyncio.run(), matching the
    # server's dataset execution path while avoiding any network-facing server.
    total_samples = estimate_dataset_total(exp_config, server_config)
    runner = build_runner(exp_config, server_config, task_id, InlineCallbackLoop(), total_samples=total_samples)
    LOGGER.info(
        "Running dataset locally: dataset=%s agent=%s model=%s concurrency=%d sample_n=%d k_runs=%d",
        exp_config.dataset_name,
        exp_config.agent.software,
        exp_config.agent.model.model_name,
        exp_config.concurrency,
        exp_config.sample_n,
        exp_config.k_runs,
    )
    if exp_config.skip_completed:
        LOGGER.info("Skip completed enabled: found %d successful historical samples in %s", len(runner.completed_experiments), runner.result_file_path)
    try:
        results = runner.run()
    finally:
        close_local_queues(runner)
    ok = sum(1 for r in results if r.status == "success")
    err = sum(1 for r in results if r.status == "error")
    LOGGER.info("Dataset run finished: total_returned=%d success=%d error=%d", len(results), ok, err)
    LOGGER.info("Result file: %s", runner.result_file_path)
    if exp_config.stream_frames:
        LOGGER.info("Frames/video saved under: %s", PROJECT_ROOT / "exp" / task_id / "frames")
    return results


def make_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run CLI coding-agent redteam experiments locally without the client/server layer.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    # Server-compatible config input.
    parser.add_argument("--request-json", help="Path to a JSON ExperimentConfig/request object. CLI flags override it.")

    # Experiment identity and selection.
    parser.add_argument("--dataset", help="Dataset name under --data-path.")
    parser.add_argument("--sample-id", help="Run exactly one sample. If omitted, run the dataset with --concurrency.")
    parser.add_argument("--filter-json", help="Dataset filter_dict JSON object, e.g. '{\"category\": [\"Exfiltration\"]}'. Ignored for --sample-id.")
    parser.add_argument("--sample-n", type=int, help="Randomly sample N dataset entries before filtering; -1 means all.")
    parser.add_argument("--k-runs", type=int, help="Repeat each loaded sample K times using the existing dataset loader semantics.")
    parser.add_argument("--first-n", type=int, help="Dataset mode only: deterministically run the first N loaded/filtered samples. Unlike --sample-n, this does not randomize selection.")
    parser.add_argument("--start-id", help="Dataset mode only: run the suffix of the loaded/filtered dataset starting from this sample id.")
    parser.add_argument("--start-index", type=int, help="Dataset mode only: run the suffix of the loaded/filtered dataset starting from this 0-based index.")
    parser.add_argument("--run-name", help="Local result namespace. Maps to ExperimentConfig.user and results/<run-name>/...")

    # Agent/model.
    parser.add_argument("--agent", help="CLI agent software, e.g. cc_cli or opencode_cli. Must end with _cli.")
    parser.add_argument("--model", help="Model name passed to the agent.")
    parser.add_argument("--api-provider", help="Model API provider label.")
    parser.add_argument("--api-key", help="Agent API key. Overrides AgentConfig/env-derived values.")
    parser.add_argument("--api-base-url", help="Agent API base URL. Overrides AgentConfig/env-derived values.")
    parser.add_argument("--model-args-json", help="JSON object assigned to ModelConfig.model_args.")

    # Execution behavior.
    parser.add_argument("--attack-method", help="Attack method name, same as server ExperimentConfig.attack_method_name.")
    parser.add_argument("--concurrency", type=int, help="Number of samples/containers to run in parallel for dataset mode.")
    parser.add_argument("--skip-completed", action="store_true", help="Reuse existing successful results in the same result file.")
    parser.add_argument("--fail-immediately-on-error", action="store_true", help="Keep ExperimentConfig-compatible flag; currently used by server paths.")
    parser.add_argument("--screenshot-time", type=float, help="Kept for compatibility with ExperimentConfig.")
    parser.add_argument("--log-level", help="Workflow log level.")
    parser.add_argument("--debug-port", type=int, help="Optional debug port mapping for CLI container.")
    parser.add_argument("--image", help="Docker image prefix passed as ExperimentConfig.env_image_name.")
    parser.add_argument("--no-stream-frames", action="store_true", help="Disable live screenshot/frame generation/streaming when supported by automation_server.")
    parser.add_argument("--no-stream-logs", action="store_true", help="Disable live log SSE streaming from automation_server when supported.")
    parser.add_argument("--verbose", action="store_true", help="Show detailed framework/container logs on the console. By default standalone prints concise progress and warnings/errors only.")

    # Local paths.
    parser.add_argument("--data-path", default="./data", help="Dataset base path.")
    parser.add_argument("--workspace-path", default="./temp_workspace", help="Workspace tarball/cache base path used by container_preparation.")
    parser.add_argument("--results-path", default="./results", help="Local results base path.")
    parser.add_argument("--vm-config-path", default="./configs", help="Agent YAML config path. Used by CLI agents too.")

    # Network/proxy env passed to containers, not a client/server transport.
    parser.add_argument("--https-proxy", default=None, help="Upstream HTTPS proxy for agent/container traffic. Defaults to env if omitted.")
    parser.add_argument("--host-ip", default=None, help="Host IP visible from containers. Defaults to env/HOST_IP behavior if omitted.")

    return parser



def configure_logging(args: argparse.Namespace, request_data: dict[str, Any]) -> None:
    effective_log_level = args.log_level or request_data.get("log_level", "INFO")
    if args.verbose:
        root_level = getattr(logging, str(effective_log_level).upper(), logging.INFO)
    else:
        root_level = logging.WARNING
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)s - %(name)s - %(message)s",
    )
    # Keep the terminal concise unless --verbose is requested, while retaining
    # an INFO-level file log for every standalone run.
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    for handler in root_logger.handlers:
        handler.setLevel(root_level)
    LOGGER.setLevel(logging.INFO)
    # The root console intentionally hides framework INFO logs in standalone
    # mode. Give the local runner its own concise console stream so users
    # always see dataset start, every completed sample, and ETA.
    if not any(getattr(handler, "name", "") == "standalone-progress" for handler in LOGGER.handlers):
        progress_handler = logging.StreamHandler()
        progress_handler.name = "standalone-progress"
        progress_handler.setLevel(logging.INFO)
        progress_handler.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s - %(name)s - %(message)s"))
        LOGGER.addHandler(progress_handler)
    if not args.verbose:
        # Keep high-signal output on the terminal. Detailed per-task logs still
        # live in result JSON, raw chat history, and exp/<task>/ files.
        for name in [
            "src.agent_red.engine.runner",
            "src.agent_red.environment_manager",
            "src.agent_red.env.docker_env",
            "src.agent_red.utils.container_prep",
            "src.agent_red.agent.ide_solver",
            "src.agent_red.agent.scorer_wrapper",
            "src.agent_red.scorer",
            "docker",
            "urllib3",
            "httpx",
            "httpcore",
            "requests",
        ]:
            logging.getLogger(name).setLevel(logging.WARNING)


def add_run_file_handler(task_id: str) -> Path:
    """Persist standalone logs even when stdout is redirected or collapsed."""
    log_path = PROJECT_ROOT / "exp" / task_id / "runner.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    root_logger = logging.getLogger()
    resolved = log_path.resolve()
    for handler in root_logger.handlers:
        if isinstance(handler, logging.FileHandler) and Path(handler.baseFilename).resolve() == resolved:
            return log_path
    handler = logging.FileHandler(log_path, encoding="utf-8")
    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s - %(name)s - %(message)s"))
    root_logger.addHandler(handler)
    return log_path

def main() -> int:
    parser = make_arg_parser()
    args = parser.parse_args()

    request_data = load_request_json(args.request_json)
    configure_logging(args, request_data)

    exp_config = build_exp_config(args, request_data)
    server_config = build_server_config(args)
    task_id = f"standalone-{exp_config.user}"
    run_log_path = add_run_file_handler(task_id)

    LOGGER.info("Standalone mode uses in-process no-op queues only; no WebSocket/HTTP result streaming is started.")
    LOGGER.info("Results are written locally under: %s/%s", server_config.results_base_path, exp_config.user)
    LOGGER.info("Run log is written to: %s", run_log_path)

    try:
        if exp_config.mode == "single_sample":
            result = asyncio.run(run_single_sample(exp_config, server_config, task_id))
            return 0 if result.status == "success" else 1
        results = run_dataset(exp_config, server_config, task_id)
        return 0 if all(r.status == "success" for r in results) else 1
    except KeyboardInterrupt:
        LOGGER.warning("Interrupted by user")
        return 130
    except Exception:
        LOGGER.exception("Fatal error")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
