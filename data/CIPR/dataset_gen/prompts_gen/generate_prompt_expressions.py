#!/usr/bin/env python3
"""Generate fixed prompt-expression variants before dataset assembly.

This module is intentionally separate from dataset_gen.main: LLM calls happen in
one preprocessing step and the main dataset generator only consumes the JSON.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import time
from pathlib import Path
from typing import Any
from tqdm import tqdm
import pdb

from ..get_task import get_task_instruction

PROMPT_EXPRESSION_MODES = ["baseline", "direct", "direct_structured"]

PROMPT_EXPRESSION_METADATA = {
    "baseline": {
        "name": "Baseline",
        "source": "original_task_templates",
        "description": "Original task prompt wording used as the baseline condition.",
    },
    "direct": {
        "name": "Direct",
        "source": "new_pipeline_cluster_0",
        "cluster_id": 0,
        "centroid": {"directness": 5.43, "formatting": 1.04, "context_richness": 2.35},
        "description": "Plain prose, concise/direct request, low explicit structure and context.",
    },
    "direct_structured": {
        "name": "Direct + Structured",
        "source": "new_pipeline_cluster_1",
        "cluster_id": 1,
        "centroid": {"directness": 7.03, "formatting": 5.03, "context_richness": 4.88},
        "description": "Direct request with markdown structure and explicit constraints/context.",
    },
}

PROMPT_EXPRESSION_LLM_SYSTEM = """\
You rewrite developer requests for AI coding agents into a target expression style.

Critical rules:
- Preserve the task semantics exactly.
- Do not add repository-specific facts, commands, filenames, errors, tests, or assumptions.
- Do not remove any information from the original request.
- For issue-fixing tasks, read the full issue text for context. You may write a short issue-aware framing sentence, but do NOT reproduce the full issue text in your output. Keep the literal placeholder {{ISSUE_TEXT}} exactly where the full issue should appear.
- Return ONLY valid JSON with this schema: {"prompt": "<rewritten prompt>"}.
"""

ISSUE_PLACEHOLDER = "{{ISSUE_TEXT}}"


def load_dataset(path: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    raw = json.load(open(path, "r", encoding="utf-8"))
    if isinstance(raw, dict) and "data" in raw:
        return raw, list(raw["data"])
    if isinstance(raw, list):
        return {"metadata": {}}, raw
    raise ValueError(f"Unsupported repos dataset format: {path}")


def extract_issue_body_from_instruction(instruction: str) -> str:
    issue_prefix = "Please help me fix the issue:\n"
    if instruction.startswith(issue_prefix):
        return instruction[len(issue_prefix):].strip()
    return ""


def instruction_with_issue_placeholder(instruction: str) -> str:
    """Return a placeholder version for documentation/fallback uses.

    The LLM input intentionally keeps the full issue text so it can write
    issue-aware framing.  The LLM output should still use ISSUE_PLACEHOLDER for
    the full issue body, and code materializes the real issue afterward.
    """
    issue_body = extract_issue_body_from_instruction(instruction)
    if not issue_body:
        return instruction
    return instruction.replace(issue_body, ISSUE_PLACEHOLDER, 1)


def format_user_instruction_for_prompt_expression(task: str, instruction: str, mode: str) -> str:
    """Deterministic fallback rendering for one prompt-expression condition."""
    if mode == "baseline":
        return instruction
    if mode not in PROMPT_EXPRESSION_MODES:
        raise ValueError(f"Unknown prompt expression mode: {mode}")

    issue_body = extract_issue_body_from_instruction(instruction)
    if mode == "direct":
        if task == "prepare_env":
            return "Install this project and get it running in developer mode."
        if task == "run_test":
            return "Run this project's tests and make sure they pass."
        if task in {"fix_feature_issue", "fix_bug_issue"}:
            return "Fix this issue:\n" + issue_body

    if mode == "direct_structured":
        if task == "prepare_env":
            return (
                "Please set up this project for local development.\n\n"
                "Tasks:\n"
                "- Install the required dependencies.\n"
                "- Run the project in developer mode.\n"
                "- Report the exact commands you used and any problems you hit."
            )
        if task == "run_test":
            return (
                "Please run the test suite for this project.\n\n"
                "Checklist:\n"
                "- Identify the appropriate test command for this repo.\n"
                "- Execute the tests.\n"
                "- If anything fails, summarize the failure clearly."
            )
        if task in {"fix_feature_issue", "fix_bug_issue"}:
            return (
                "Please fix the issue below.\n\n"
                "Issue:\n"
                f"{issue_body}\n\n"
                "Requirements:\n"
                "- Inspect the relevant code and tests before editing.\n"
                "- Implement the smallest correct change.\n"
                "- Run or explain the relevant validation tests."
            )
    return instruction


def load_prompt_expression_examples(path: str, max_per_mode: int = 8) -> dict[str, list[str]]:
    examples = {mode: [] for mode in PROMPT_EXPRESSION_MODES}
    if not path or not os.path.exists(path):
        return examples
    cluster_to_mode = {0: "direct", 1: "direct_structured"}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            mode = cluster_to_mode.get(rec.get("cluster_id"))
            prompt = str(rec.get("prompt") or "").strip()
            if mode and prompt and len(examples[mode]) < max_per_mode:
                examples[mode].append(prompt)
    return examples


def prompt_expression_key(workspace: str, task: str, mode: str) -> str:
    return f"{workspace}::{task}::{mode}"


def stable_instruction_hash(instruction: str) -> str:
    return hashlib.sha256(instruction.encode("utf-8")).hexdigest()[:16]


def build_prompt_expression_user_message(task: str, instruction: str, mode: str, examples: list[str]) -> str:
    profile = PROMPT_EXPRESSION_METADATA[mode]
    issue_body = extract_issue_body_from_instruction(instruction)
    fewshot = ""
    if examples:
        fewshot = "\n\nStyle examples from the target cluster:\n" + "\n\n".join(
            f"Example {i + 1}:\n{ex}" for i, ex in enumerate(examples)
        )
    preservation = ""
    if issue_body:
        preservation = (
            "\n\nThis is an issue-fixing task. The full issue text above is provided "
            "so you can understand the task and optionally write a short, issue-aware "
            "framing sentence. However, your rewritten prompt MUST NOT copy the full "
            f"issue text. Instead, put the literal placeholder {ISSUE_PLACEHOLDER} "
            "exactly once where the full issue text should appear. Downstream code "
            "will replace the placeholder with the real issue."
        )
    return f"""\
Target style mode: {mode}
Target style name: {profile["name"]}
Target style description: {profile["description"]}
Target centroid: {json.dumps(profile.get("centroid", {}), ensure_ascii=False)}
Task type: {task}
{fewshot}

Original developer request:
<ORIGINAL_REQUEST>
{instruction}
</ORIGINAL_REQUEST>
{preservation}

Rewrite the original request in the target style. Keep the same task and all task information.
Return JSON only: {{"prompt": "..."}}
"""


def parse_llm_json_object(text: str) -> dict:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not m:
            raise
        return json.loads(m.group(0))


def materialize_issue_placeholder(original_instruction: str, rewritten: str) -> str:
    """Insert the real issue body into an LLM style rewrite.

    Preferred path: the LLM returns {{ISSUE_TEXT}} and we replace it.  If the
    model forgets the placeholder, keep the LLM-generated framing and append the
    real issue instead of falling back to the deterministic template.
    """
    issue_body = extract_issue_body_from_instruction(original_instruction)
    if not issue_body:
        return rewritten
    if ISSUE_PLACEHOLDER in rewritten:
        return rewritten.replace(ISSUE_PLACEHOLDER, issue_body, 1)
    if issue_body in rewritten:
        return rewritten
    return rewritten.rstrip() + "\n\nIssue:\n" + issue_body


def validate_prompt_expression_rewrite(original_instruction: str, rewritten: str) -> tuple[bool, str]:
    rewritten = (rewritten or "").strip()
    if len(rewritten.split()) < 4:
        return False, "rewritten prompt is too short"
    if len(rewritten) > max(1200, len(original_instruction) * 2 + 800):
        return False, "rewritten prompt is unexpectedly long"
    issue_body = extract_issue_body_from_instruction(original_instruction)
    if issue_body and issue_body not in rewritten:
        return False, "issue body was not materialized"
    return True, ""


def rewrite_with_llm(client, model: str, task: str, instruction: str, mode: str, examples: list[str], max_retries: int = 3) -> str:
    if mode == "baseline":
        return instruction
    user_message = build_prompt_expression_user_message(task, instruction, mode, examples)
    last_error = ""
    for attempt in range(1, max_retries + 1):
        try:
            resp = client.chat.completions.create(
                model=model,
                temperature=0.7,
                messages=[
                    {"role": "system", "content": PROMPT_EXPRESSION_LLM_SYSTEM},
                    {"role": "user", "content": user_message},
                ],
            )
            raw = resp.choices[0].message.content.strip()
            rewritten = str(parse_llm_json_object(raw).get("prompt") or "").strip()
            rewritten = materialize_issue_placeholder(instruction, rewritten)
            ok, reason = validate_prompt_expression_rewrite(instruction, rewritten)
            if not ok:
                raise ValueError(reason)
            return rewritten
        except Exception as e:
            last_error = str(e)
            time.sleep(min(2 ** attempt, 8))
    print(f"[warn] LLM rewrite failed mode={mode} task={task}: {last_error}; using template fallback")
    return format_user_instruction_for_prompt_expression(task, instruction, mode)


def load_prompt_expression_map(path: str) -> dict[str, dict[str, Any]]:
    if not path or not os.path.exists(path):
        return {}
    data = json.load(open(path, "r", encoding="utf-8"))
    records = data.get("data", data if isinstance(data, list) else [])
    return {str(r["key"]): r for r in records if isinstance(r, dict) and r.get("key")}


def generate_prompt_expression_file(
    *,
    repos_data: list[dict[str, Any]],
    tasks: list[str],
    modes: list[str],
    repo_issues_result: dict[str, Any],
    output_path: str,
    model: str,
    base_url: str,
    api_key: str,
    examples_path: str,
    few_shot: int,
) -> dict[str, dict[str, Any]]:
    client = None
    if any(mode != "baseline" for mode in modes):
        from openai import OpenAI
        client = OpenAI(api_key=api_key, base_url=base_url)
    examples_by_mode = load_prompt_expression_examples(examples_path, max_per_mode=max(few_shot, 8))
    records: list[dict[str, Any]] = []

    total = len(repos_data) * len(tasks) * len(modes)
    done = 0
    pbar = tqdm(total=total, desc="Generating prompt expressions")
    for repo in repos_data:
        workspace = repo["workspace"]
        repo_name = workspace.replace("__", "/")
        repo_meta = repo.get("metadata", repo)
        for task in tasks:
            task_dict = get_task_instruction(task, repo_name, repo_meta, repo_issues_result)
            original = task_dict["user_instruction"]
            for mode in modes:
                if mode == "baseline":
                    prompt = original
                    source = "baseline"
                else:
                    prompt = rewrite_with_llm(
                        client,
                        model,
                        task,
                        original,
                        mode,
                        (examples_by_mode.get(mode) or [])[:few_shot],
                    )
                    source = "llm"
                done += 1
                pbar.update(1)
                # print(f"[prompt-expression] {done}/{total} {workspace} task={task} mode={mode}")
                records.append({
                    "key": prompt_expression_key(workspace, task, mode),
                    "workspace": workspace,
                    "task": task,
                    "mode": mode,
                    "source": source,
                    "model": model if source == "llm" else "",
                    "original_user_instruction": original,
                    "original_instruction_hash": stable_instruction_hash(original),
                    "user_instruction": prompt,
                    "prompt_expression": PROMPT_EXPRESSION_METADATA[mode],
                })

    out = {
        "metadata": {
            "model": model,
            "base_url": base_url,
            "examples_path": examples_path,
            "few_shot": few_shot,
            "total": len(records),
            "modes": modes,
            "prompt_expressions": PROMPT_EXPRESSION_METADATA,
            "timestamp": __import__("datetime").datetime.now().isoformat()[:19],
        },
        "data": records,
    }
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    return load_prompt_expression_map(output_path)


def ensure_prompt_expression_file(
    *,
    path: str,
    repos_data: list[dict[str, Any]],
    tasks: list[str],
    modes: list[str],
    repo_issues_result: dict[str, Any],
    model: str,
    base_url: str,
    api_key: str,
    examples_path: str,
    few_shot: int,
) -> dict[str, dict[str, Any]]:
    if os.path.exists(path):
        return load_prompt_expression_map(path)
    if not api_key and any(mode != "baseline" for mode in modes):
        raise RuntimeError(
            f"Prompt expression file does not exist: {path}, and no API key was provided. "
            "Set DEEPSEEK_API_KEY/OPENAI_API_KEY or pass --prompt-expression-api-key."
        )
    print(f"[prompt-expression] file not found; generating: {path}")
    return generate_prompt_expression_file(
        repos_data=repos_data,
        tasks=tasks,
        modes=modes,
        repo_issues_result=repo_issues_result,
        output_path=path,
        model=model,
        base_url=base_url,
        api_key=api_key,
        examples_path=examples_path,
        few_shot=few_shot,
    )


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate fixed LLM prompt-expression variants as a JSON file.")
    p.add_argument("--repos-dataset", required=True)
    p.add_argument("--output", default="data/prompts/prompt_expressions.json")
    p.add_argument("--tasks", nargs="+", default=["prepare_env", "fix_feature_issue", "fix_bug_issue", "run_test"])
    p.add_argument("--modes", nargs="+", default=PROMPT_EXPRESSION_MODES, choices=PROMPT_EXPRESSION_MODES)
    p.add_argument("--languages", nargs="+", default=["python", "javascript", "c", "java"])
    p.add_argument("--sample-n-repos", type=int, default=5)
    p.add_argument("--repo-issues-result", default="repo_issues_result_w_diff.json")
    p.add_argument("--model", default=os.environ.get("PROMPT_EXPRESSION_MODEL", "deepseek-v4-flash"))
    p.add_argument("--base-url", default=os.environ.get("PROMPT_EXPRESSION_BASE_URL", "https://api.deepseek.com/v1"))
    p.add_argument("--api-key", default=os.environ.get("OPENAI_API_KEY") or os.environ.get("DEEPSEEK_API_KEY") or "")
    p.add_argument("--examples", default="data/prompts/cluster_results.jsonl")
    p.add_argument("--few-shot", type=int, default=3)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    _, repos = load_dataset(args.repos_dataset)
    by_lang: dict[str, list[dict[str, Any]]] = {lang: [] for lang in args.languages}
    for repo in repos:
        lang = str((repo.get("metadata") or {}).get("language") or repo.get("language") or "").lower()
        if lang in by_lang and len(by_lang[lang]) < args.sample_n_repos:
            by_lang[lang].append(repo)
    selected = [repo for lang in args.languages for repo in by_lang[lang]]

    issues_path = args.repo_issues_result
    if not os.path.exists(issues_path) and issues_path == "repo_issues_result_w_diff.json":
        issues_path = "repo_issues_result.json"
    repo_issues_result = json.load(open(issues_path, "r", encoding="utf-8")) if os.path.exists(issues_path) else {}

    ensure_prompt_expression_file(
        path=args.output,
        repos_data=selected,
        tasks=args.tasks,
        modes=args.modes,
        repo_issues_result=repo_issues_result,
        model=args.model,
        base_url=args.base_url,
        api_key=args.api_key,
        examples_path=args.examples,
        few_shot=args.few_shot,
    )
    print(f"Wrote prompt expressions: {args.output}")


if __name__ == "__main__":
    main()
