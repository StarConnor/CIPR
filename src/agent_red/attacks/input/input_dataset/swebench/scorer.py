import pdb
from typing import Any, Callable, Dict, List, Optional, Tuple
from functools import partial
from pathlib import Path, PurePosixPath
from .constants import (
    DOCKER_PATCH,
    DOCKER_USER,
    DOCKER_WORKDIR,
    GIT_APPLY_CMDS,
    LOG_TEST_OUTPUT,
    UTF8,
    APPLY_PATCH_FAIL,
    APPLY_PATCH_PASS,
)
from .grading import get_eval_report, exec_run_with_timeout
from .....custom_types import ScoreResult, TaskState, EvaluationError
import logging
from .....utils.others import docker_write_str_to_file

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

def get_patch_content(container):
    """Get the patch content from the container."""
    # Find the patch file in the project's root path in a fuzzing way
    exit_code, patch_path = container.exec_run(
        f"find . -type f -name '*patch' -print -quit",
        workdir=DOCKER_WORKDIR,
        user=DOCKER_USER,
    )
    if exit_code != 0:
        raise EvaluationError(
            "get_patch_content",
            f"Failed to find patch file: {patch_path.output.decode(UTF8)}",
            logger,
        )
    patch_content = container.exec_run(
        f"cat {patch_path.output.decode(UTF8).strip()}",
        workdir=DOCKER_WORKDIR,
        user=DOCKER_USER,
    )
    if patch_content.exit_code != 0:
        raise EvaluationError(
            "get_patch_content",
            f"Failed to get patch content: {patch_content.output.decode(UTF8)}",
            logger,
        )
    return patch_content.output.decode(UTF8).strip()

def evaluation(state: TaskState):
    container = state.env_state.running_environments.get("code_server").container
    test_spec = state.sample.metadata
    instance_id = test_spec['instance_id']
    pred = get_patch_content(container)
    timeout = 1_800
    docker_write_str_to_file(
        # pred[KEY_PREDICTION],
        DOCKER_PATCH,
        container_name=container.name,
        container=container,
    )
    # Attempt to apply patch to container (TODO: FIX THIS)
    applied_patch = False
    for git_apply_cmd in GIT_APPLY_CMDS:
        val = container.exec_run(
            f"{git_apply_cmd} {DOCKER_PATCH}",
            workdir=DOCKER_WORKDIR,
            user=DOCKER_USER,
        )
        if val.exit_code == 0:
            logger.info(f"{APPLY_PATCH_PASS}:\n{val.output.decode(UTF8)}")
            applied_patch = True
            break
        else:
            logger.info(f"Failed to apply patch to container: {git_apply_cmd}")
    if not applied_patch:
        logger.info(f"{APPLY_PATCH_FAIL}:\n{val.output.decode(UTF8)}")
        raise EvaluationError(
            instance_id,
            f"{APPLY_PATCH_FAIL}:\n{val.output.decode(UTF8)}",
            logger,
        )

    # Get git diff before running eval script
    git_diff_output_before = (
        container.exec_run(
            "git -c core.fileMode=false diff", workdir=DOCKER_WORKDIR
        )
        .output.decode(UTF8)
        .strip()
    )
    logger.info(f"Git diff before:\n{git_diff_output_before}")

    docker_write_str_to_file(
        test_spec.eval_script,
        "/eval.sh",
        container_name=container.name,
        container=container,
    )

    # Run eval script, write output to logs
    test_output, timed_out, total_runtime = exec_run_with_timeout(
        container, "/bin/bash /eval.sh", timeout
    )

    # Get git diff after running eval script (ignore permission changes)
    git_diff_output_after = (
        container.exec_run(
            "git -c core.fileMode=false diff", workdir=DOCKER_WORKDIR
        )
        .output.decode(UTF8)
        .strip()
    )

    # Check if git diff changed after running eval script
    logger.info(f"Git diff after:\n{git_diff_output_after}")
    if git_diff_output_after != git_diff_output_before:
        logger.info("Git diff changed after running eval script")

    # Get report from test output
    logger.info(f"Grading answer for {instance_id}...")
    report = get_eval_report(
        test_spec=test_spec,
        prediction=pred,
        test_log_path=test_output,
        include_tests_status=True,
    )
    logger.info(
        f"report: {report}\n"
        f"Result for {instance_id}: resolved: {report[instance_id]['resolved']}"
    )

    eval_completed = True
    return {
        "completed": eval_completed,
        "resolved": report.get(instance_id, {}).get("resolved", False),
    }


def get_evaluation() -> Callable[[TaskState, Any], List[ScoreResult]]:
    """Check whether the store value indicates completion."""

    return evaluation