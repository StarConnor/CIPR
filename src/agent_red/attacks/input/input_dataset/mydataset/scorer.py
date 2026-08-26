import pdb
from pathlib import Path
import os
from json import JSONDecodeError


from typing import Callable, Optional, Dict, Any, List
# from inspect_ai.solver import TaskState
from .....custom_types import ScoreResult, TaskState
import importlib.util
from functools import partial
import asyncio

data_base_path = Path(__file__).parent.parent.parent.parent.parent.parent / "data" / "data_sample"
task_a_data_path = data_base_path / "task a"
task_d_data_path = data_base_path / "task d"
API_KEY = os.environ.get("AGENT_API_KEY")
BASE_URL = os.environ.get("AGENT_BASE_URL") or "https://api.gpt.ge/v1"

def load_module(file_path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def load_mydataset_evaluator(category: str):
    if category == "binary_classification":
        module = load_module(task_a_data_path / "a1" / "binary_classification" / "evaluation.py", "evaluation")
        return module.evaluate_binary_detection_task
    # module = load_module(task_a_data_path / "a1" / "vulnerability_classification" / "evaluation.py", "evaluation")
    # category_mapping.update({"vulnerability_classification": module.evaluate_vulnerability_detection_task})
    elif category == "vulnerability_localization":
        module = load_module(task_a_data_path / "a1" / "vulnerability_localization" / "evaluation.py", "evaluation")
        return module.evaluate_vulnerability_localization_task

    elif category == "cross_file_repair":
        module = load_module(task_a_data_path / "a2" / "cross_file_repair" / "evaluation.py", "evaluation")
        return module.evaluate_cross_file_repair_task
    
    elif category == "function_level_repair":
        module = load_module(task_a_data_path / "a2" / "function_level_repair" / "evaluation.py", "evaluation")
        return module.evaluate_function_level_repair_task
    
    elif category == "single_line_repair":
        module = load_module(task_a_data_path / "a2" / "single_line_repair" / "evaluation.py", "evaluation")
        return module.evaluate_single_line_repair_task

    elif category == "function_body_completion":
        module = load_module(task_a_data_path / "a3" / "function_body_completion" / "evaluation.py", "evaluation")
        return module.evaluate_function_body_completion_task

    elif category == "line_completion":
        module = load_module(task_a_data_path / "a3" / "line_completion" / "evaluation.py", "evaluation")
        return module.evaluate_line_completion_task

    elif category == "middle_code_completion":
        module = load_module(task_a_data_path / "a3" / "middle_code_completion" / "evaluation.py", "evaluation")
        return module.evaluate_middle_code_completion_task
    
    elif category == "direct_prompt_injection":
        module = load_module(task_d_data_path / "d1" / "direct_prompt_injection" / "evaluation.py", "evaluation")
        return module.evaluate_direct_prompt_injection_task
    
    else: 
        raise ValueError(f"Unknown category: {category}")

STORE_KEY_ATTACK_SUCCESSFUL = "attack-was-successful-score-my-dataset"
import json
import re

def extract_json_pattern(first_prompt: str) -> str | None:
    """
    Extract the JSON template that appears specifically after:
        'in the following JSON format:'
    and before any later text.
    """

    marker = "in the following JSON format:"
    idx = first_prompt.find(marker)
    if idx == -1:
        return None

    # Start searching right after the marker
    substring = first_prompt[idx + len(marker):]

    brace_stack = []
    start = None

    for i, ch in enumerate(substring):
        if ch == '{':
            if not brace_stack:
                start = i
            brace_stack.append('{')
        elif ch == '}':
            if brace_stack:
                brace_stack.pop()
                if not brace_stack and start is not None:
                    return substring[start:i+1]

    return None


def build_regex_from_pattern(pattern: str) -> re.Pattern:
    """
    Turns the pattern JSON into a regex that can match the real JSON object.
    Supports cases like: true or false
    """
    # Escape the whole pattern first
    escaped = re.escape(pattern)

    # Replace the escaped 'true or false' with unescaped regex group
    escaped = escaped.replace(re.escape("true or false"), r"(true|false)")

    # Allow whitespace differences (optional)
    escaped = escaped.replace(r"\ ", r"\s*")

    # Compile the regex
    return re.compile(escaped)

def extract_real_json(conversation: str, regex: re.Pattern) -> dict | None:
    match = regex.search(conversation)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return None

def evaluation(eval_function: Callable[[Dict[str, Any], str, str], Dict[str, Any]], state: TaskState) -> List[ScoreResult]:
    task = state.sample.metadata

    if "direct_prompt_injection" in task.get("task_type", ""):
        task.update({"agent_output": [m.model_dump() for m in state.messages]})
        task.update({"agent_behavior_log": state.commands_executed})
    else:
        messages = [m.content for m in state.messages]
        pattern = extract_json_pattern(messages.pop(0))
        regex = build_regex_from_pattern(pattern)
        real_json = extract_real_json("\n".join(messages), regex)
        if not real_json:
            raise JSONDecodeError("Could not extract JSON from the conversation.")
        task.update({"agent_output": real_json})

    # if eval_function can be awaited
    # if asyncio.iscoroutinefunction(eval_function):
    #     score = await eval_function(task, api_key=API_KEY, base_url=BASE_URL)
    # else:
    try:
        score = eval_function(task, api_key=API_KEY, base_url=BASE_URL)
    except TypeError:
        score = eval_function(task)
    
    scores = [
        ScoreResult(
            name=key,
            value=float(value),
            explanation=None,
        )
        for key, value in score.items()
    ]
    return scores

def get_evaluation(category:str) -> Callable[[TaskState, Any], List[ScoreResult]]:
    """Check whether the store value indicates completion."""
    eval_function = load_mydataset_evaluator(category)

    return partial(evaluation, eval_function=eval_function)
