#!/usr/bin/env python3
"""Analyse coding-agent redteam experiment results.

The script is intentionally dependency-free (stdlib only).  It scans result_*.json
files produced by run_exp.sh / agent_red.queue_server, joins them with the source
dataset (e.g. data/ciip/dataset.json), and writes CSV/Markdown tables plus simple
SVG figures for attack success rate (ASR), task success rate (TSR), coverage, and
breakdowns by dataset variables.

Typical usage:

  # Analyse CIIP results under test/exp/dataset and write to test/analysis/ciip
  python test/analyse_result.py \
      --dataset data/ciip/dataset.json \
      --results-root test/exp/dataset \
      --dataset-name ciip \
      --out test/analysis/ciip

  # Include all folders whose path contains "ciip" (ciip, ciip1, ...)
  python test/analyse_result.py --dataset data/ciip/dataset.json --dataset-name ciip --match contains

  # Also works for already archived completed-exp folders
  python test/analyse_result.py --dataset data/ipi_file_dataset/dataset.json --results-root test/completed-exp --dataset-name ipi_file_dataset

Outputs:
  - records.csv: one row per result JSON
  - summary_by_experiment.csv/.md: model/run-level metrics
  - breakdown_by_<field>.csv/.md: ASR/TSR grouped by repo/language/task/payload/craft_method/...
  - pivot_<field>_by_model.csv/.md: ASR pivot tables
  - dataset_quality.csv/.md: dataset distribution and current result coverage by field
  - figures/*.svg: bar charts and heatmaps viewable in a browser/Markdown
"""
from __future__ import annotations

import argparse
import csv
import html
import json
import math
import re
import statistics
from datetime import datetime
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

# Fields that matter most for CIIP-style dataset quality / ASR analysis.
DEFAULT_BREAKDOWNS = [
    "model",
    "agent",
    "repo",
    "language",
    "task",
    "payload_id",
    "payload_category",
    "category",
    "subcategory",
    "craft_method",
    "injection_type",
]


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def dataset_items(dataset_path: Path) -> list[dict[str, Any]]:
    if not dataset_path or not dataset_path.exists():
        return []
    data = load_json(dataset_path)
    if isinstance(data, dict):
        for key in ("data", "samples", "items", "dataset"):
            if isinstance(data.get(key), list):
                return data[key]
        # Fall back to list-like dict values.
        vals = [v for v in data.values() if isinstance(v, dict) and "id" in v]
        return vals
    if isinstance(data, list):
        return data
    return []


def norm_bool(value: Any) -> int | None:
    """Convert common result values to {1,0,None}."""
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        if math.isnan(value) if isinstance(value, float) else False:
            return None
        return 1 if value > 0 else 0
    s = str(value).strip().lower()
    if s in {"success", "succeeded", "pass", "passed", "true", "yes", "y", "1", "ok"}:
        return 1
    if s in {"failure", "failed", "fail", "false", "no", "n", "0", "error", "timeout", "none"}:
        return 0
    return None


def score_from_scores(result: dict[str, Any], score_name: str) -> int | None:
    scores = result.get("scores")
    if not isinstance(scores, dict):
        return None
    for scorer_values in scores.values():
        if not isinstance(scorer_values, list):
            continue
        for item in scorer_values:
            if isinstance(item, dict) and item.get("name") == score_name:
                return norm_bool(item.get("value"))
    return None


def first_nonempty(*values: Any) -> str:
    for v in values:
        if v is None:
            continue
        if isinstance(v, (list, tuple)):
            if v:
                return ";".join(map(str, v))
            continue
        s = str(v).strip()
        if s:
            return s
    return ""


def get_nested(obj: dict[str, Any] | None, path: str, default: Any = "") -> Any:
    cur: Any = obj or {}
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur


def short_repo(repo_url_or_name: Any) -> str:
    s = str(repo_url_or_name or "").strip().rstrip("/")
    if not s:
        return ""
    s = re.sub(r"\.git$", "", s)
    if "github.com/" in s:
        return s.split("github.com/", 1)[1]
    return s


def infer_path_parts(path: Path, results_root: Path) -> dict[str, str]:
    """Infer agent/dataset/model/run from both supported layouts.

    Supported examples:
      test/exp/dataset/cc_cli/ciip/deepseek-v4-flash-1/result_*.json
      test/exp/dataset/ciip/deepseek-v4-flash-1/result_*.json
      test/completed-exp/cline-cli-deepseek-ipi-file-lite/result_*.json
    """
    try:
        rel = path.relative_to(results_root)
        parts = rel.parts
    except Exception:
        parts = path.parts
    out = {"agent_path": "", "dataset_path": "", "run_dir": path.parent.name}
    if len(parts) >= 4:  # agent / dataset / model-run / file
        out["agent_path"] = parts[0]
        out["dataset_path"] = parts[1]
        out["run_dir"] = parts[2]
    elif len(parts) >= 3:  # dataset / model-run / file
        out["dataset_path"] = parts[0]
        out["run_dir"] = parts[1]
    return out


def split_model_run(run_dir: str) -> tuple[str, str]:
    m = re.match(r"^(.*?)-(\d+)$", run_dir)
    if m:
        return m.group(1), m.group(2)
    return run_dir, ""



def parse_time_value(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        # milliseconds if it looks like a JS timestamp
        return float(value) / 1000.0 if float(value) > 10_000_000_000 else float(value)
    text = str(value).strip()
    if not text:
        return 0.0
    if text.isdigit():
        return parse_time_value(int(text))
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()
    except Exception:
        return 0.0


def sample_changed(current_dataset_sample: dict[str, Any], result_sample: dict[str, Any]) -> int | None:
    if not current_dataset_sample or not result_sample:
        return None
    # Compare the fields that influence skip_completed and injection/evaluation.
    # This intentionally ignores result-only fields and ordering noise.
    important = [
        "id", "task", "user_instruction", "metadata", "env_setup_script",
        "workspace", "prompt_injections", "evaluation",
        "category", "subcategory", "attacker_domain", "attacker_endpoint",
        "html_domain", "html_endpoint", "script_to_fetch_from_attacker_server",
    ]
    cur = {k: current_dataset_sample.get(k) for k in important}
    old = {k: result_sample.get(k) for k in important}
    return 0 if cur == old else 1

def extract_record(path: Path, results_root: Path, dataset_by_id: dict[str, dict[str, Any]], result_obj: dict[str, Any] | None = None, ref_suffix: str = "") -> dict[str, Any]:
    result = result_obj if result_obj is not None else load_json(path)
    sample = result.get("sample") if isinstance(result.get("sample"), dict) else {}
    sample_id = first_nonempty(result.get("sample_id"), sample.get("id"), path.stem.removeprefix("result_"))
    # Aggregate RunnerResult wrappers may prefix ids as
    # <dataset>_<attack_method>_<raw_sample_id>.  CIIR/CIIP raw ids start with
    # r_, so strip up to that marker for dataset joins and coverage counts.
    if isinstance(sample_id, str) and not sample_id.startswith("r_") and "_r_" in sample_id:
        sample_id = sample_id[sample_id.index("_r_") + 1:]
    ds = dataset_by_id.get(sample_id, {})

    # Some runners prefix result file names differently; fall back to matching suffix.
    if not ds:
        for did, item in dataset_by_id.items():
            if sample_id.endswith(did) or did.endswith(sample_id):
                ds = item
                break

    meta = result.get("metadata") if isinstance(result.get("metadata"), dict) else {}
    sample_meta = sample.get("metadata") if isinstance(sample.get("metadata"), dict) else {}
    ds_meta = ds.get("metadata") if isinstance(ds.get("metadata"), dict) else {}
    merged_meta = {**ds_meta, **sample_meta, **meta}

    repo = first_nonempty(
        get_nested(merged_meta, "repo.url"),
        get_nested(sample, "metadata.repo.url"),
        get_nested(ds, "metadata.repo.url"),
        sample.get("workspace"),
        ds.get("workspace"),
    )
    repo_name = short_repo(first_nonempty(sample.get("workspace"), ds.get("workspace"), repo))
    language = first_nonempty(
        get_nested(merged_meta, "repo.language"),
        get_nested(ds, "metadata.repo.language"),
    ).lower()
    payload_id = first_nonempty(get_nested(merged_meta, "payload.id"), get_nested(ds, "metadata.payload.id"))
    payload_category = first_nonempty(get_nested(merged_meta, "payload.category"), get_nested(ds, "metadata.payload.category"))
    craft_method = first_nonempty(merged_meta.get("craft_method"), get_nested(ds, "metadata.craft_method"))
    task = first_nonempty(sample.get("task"), ds.get("task"), merged_meta.get("task"), get_nested(ds, "metadata.task"))
    category = first_nonempty(sample.get("category"), ds.get("category"))
    subcategory = first_nonempty(sample.get("subcategory"), ds.get("subcategory"))

    injections = result.get("prompt_injections") or sample.get("prompt_injections") or ds.get("prompt_injections") or []
    inj_types = sorted({str(x.get("injection_type", "")) for x in injections if isinstance(x, dict) and x.get("injection_type")})
    target_files = sorted({str(x.get("target_file_path", "")) for x in injections if isinstance(x, dict) and x.get("target_file_path")})

    path_parts = infer_path_parts(path, results_root)
    exp_config = result.get("exp_config") if isinstance(result.get("exp_config"), dict) else {}
    agent_cfg = exp_config.get("agent") if isinstance(exp_config.get("agent"), dict) else {}
    model_cfg = agent_cfg.get("model") if isinstance(agent_cfg.get("model"), dict) else {}
    model_from_run, run_n = split_model_run(path_parts["run_dir"])
    model = first_nonempty(model_cfg.get("model_name"), model_from_run)
    agent = first_nonempty(agent_cfg.get("software"), path_parts["agent_path"])

    attack = norm_bool(result.get("attack_success"))
    task_s = norm_bool(result.get("task_success"))
    alert = norm_bool(result.get("alert_success"))
    if attack is None:
        attack = score_from_scores(result, "attack_success")
    if task_s is None:
        task_s = score_from_scores(result, "task_success")
    if alert is None:
        alert = score_from_scores(result, "alert_success")

    commands = result.get("commands_executed") or []
    web_log = result.get("web_server_log") or []
    record = {
        "result_path": str(path) + ref_suffix,
        "source_file": str(path),
        "source_ref": ref_suffix.lstrip("#"),
        "file_mtime": path.stat().st_mtime if path.exists() else 0,
        "result_timestamp": first_nonempty(result.get("time_stamp"), result.get("timestamp"), result.get("_wrapper_timestamp")),
        "result_time_sort": max(parse_time_value(first_nonempty(result.get("time_stamp"), result.get("timestamp"), result.get("_wrapper_timestamp"))), path.stat().st_mtime if path.exists() else 0),
        "sample_changed": sample_changed(ds, sample),
        "sample_id": sample_id,
        "dataset_path": path_parts["dataset_path"],
        "agent": agent,
        "model": model,
        "run": run_n,
        "run_dir": path_parts["run_dir"],
        "experiment": "/".join(x for x in [agent, path_parts["dataset_path"], path_parts["run_dir"]] if x),
        "repo": repo_name,
        "repo_url": repo,
        "language": language,
        "task": task,
        "payload_id": payload_id,
        "payload_category": payload_category,
        "category": category,
        "subcategory": subcategory,
        "craft_method": craft_method,
        "injection_type": ";".join(inj_types),
        "target_files": ";".join(target_files),
        "attack_success": attack,
        "task_success": task_s,
        "alert_success": alert,
        "compromise_success": 1 if attack == 1 and task_s == 1 else 0 if attack is not None and task_s is not None else None,
        "attack_without_task": 1 if attack == 1 and task_s == 0 else 0 if attack is not None and task_s is not None else None,
        "commands_count": len(commands) if isinstance(commands, list) else "",
        "history_length": result.get("history_length", ""),
        "web_log_count": len(web_log) if isinstance(web_log, list) else "",
        "has_feedback": int(bool(result.get("feedback"))),
    }
    return record



def iter_result_objects(path: Path) -> list[tuple[dict[str, Any], str]]:
    """Return normalised result objects from either per-sample or aggregate JSON.

    Supported formats:
      - test/exp/.../result_<sample>.json: a single result dict
      - results/<user>/<dataset>_<attack>_<agent>_<model>.json: a list of
        RunnerResult wrappers, each usually containing a nested ``result`` dict.

    The returned ref_suffix is appended to result_path so callers can distinguish
    entries from the same aggregate file.
    """
    data = load_json(path)
    if isinstance(data, dict):
        return [(data, "")]
    if not isinstance(data, list):
        return []

    out: list[tuple[dict[str, Any], str]] = []
    for idx, item in enumerate(data):
        if not isinstance(item, dict):
            continue
        inner = item.get("result")
        if isinstance(inner, dict):
            result = dict(inner)
            # Preserve wrapper-level data that does not exist in the inner
            # scorer result.  Use prefixed keys to avoid changing metrics.
            result.setdefault("sample", item.get("sample"))
            result.setdefault("metadata", item.get("metadata"))
            result.setdefault("exp_config", item.get("exp_config"))
            result["_wrapper_sample_id"] = item.get("sample_id")
            result["_wrapper_status"] = item.get("status")
            result["_wrapper_error"] = item.get("error")
            result["_wrapper_timestamp"] = item.get("timestamp")
        else:
            result = dict(item)
        sid = str(result.get("sample_id") or item.get("sample_id") or idx)
        out.append((result, f"#{sid}"))
    return out

def find_result_files(results_root: Path, dataset_name: str = "", match: str = "exact") -> list[Path]:
    # Per-sample client outputs are named result_*.json.  Server-side resume
    # files under results/<user>/ are aggregate *.json lists, so include both.
    files = sorted({*results_root.rglob("result_*.json"), *results_root.rglob("*.json")})
    files = [p for p in files if not any(part.startswith(".") for part in p.parts) and ".tmp" not in p.name and ".bak" not in p.name]
    if not dataset_name:
        return files
    selected = []
    for p in files:
        parts = p.parts
        if match == "contains":
            ok = any(dataset_name in part for part in parts) or dataset_name in p.name
        else:
            # For aggregate result filenames use the stable pattern
            # <dataset>_<attack_method>_<agent>_<model>.json.  Avoid matching
            # datasets like ciir_test_file when dataset_name is ciir.
            aggregate_exact = any(
                p.name.startswith(f"{dataset_name}_{attack}_")
                for attack in ("static_file", "no_attack")
            )
            ok = dataset_name in parts or aggregate_exact
        if ok:
            selected.append(p)
    return selected


def mean_rate(rows: list[dict[str, Any]], field: str) -> float | None:
    vals = [r[field] for r in rows if isinstance(r.get(field), int)]
    if not vals:
        return None
    return sum(vals) / len(vals)


def wilson_ci(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    phat = successes / n
    denom = 1 + z*z/n
    centre = (phat + z*z/(2*n)) / denom
    margin = z * math.sqrt((phat*(1-phat) + z*z/(4*n)) / n) / denom
    return max(0.0, centre - margin), min(1.0, centre + margin)


def summarise(rows: list[dict[str, Any]], group_fields: list[str]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        key = tuple(str(r.get(f, "") or "(empty)") for f in group_fields)
        groups[key].append(r)
    out = []
    for key, rs in groups.items():
        attack_vals = [r["attack_success"] for r in rs if isinstance(r.get("attack_success"), int)]
        task_vals = [r["task_success"] for r in rs if isinstance(r.get("task_success"), int)]
        alert_vals = [r["alert_success"] for r in rs if isinstance(r.get("alert_success"), int)]
        comp_vals = [r["compromise_success"] for r in rs if isinstance(r.get("compromise_success"), int)]
        attack_n = len(attack_vals)
        attack_s = sum(attack_vals)
        lo, hi = wilson_ci(attack_s, attack_n) if attack_n else (None, None)
        row = {f: v for f, v in zip(group_fields, key)}
        row.update({
            "n_results": len(rs),
            "n_samples": len({r.get("sample_id") for r in rs}),
            "attack_successes": attack_s,
            "asr": attack_s / attack_n if attack_n else None,
            "asr_ci95_low": lo,
            "asr_ci95_high": hi,
            "task_successes": sum(task_vals),
            "tsr": sum(task_vals) / len(task_vals) if task_vals else None,
            "alert_successes": sum(alert_vals),
            "alert_rate": sum(alert_vals) / len(alert_vals) if alert_vals else None,
            "compromise_successes": sum(comp_vals),
            "compromise_rate": sum(comp_vals) / len(comp_vals) if comp_vals else None,
        })
        out.append(row)
    out.sort(key=lambda x: (-(x.get("n_results") or 0), str(tuple(x.get(f, "") for f in group_fields))))
    return out


def dataset_quality(samples: list[dict[str, Any]], rows: list[dict[str, Any]], fields: list[str]) -> list[dict[str, Any]]:
    def sample_field(s: dict[str, Any], f: str) -> str:
        meta = s.get("metadata") if isinstance(s.get("metadata"), dict) else {}
        if f == "repo":
            return short_repo(first_nonempty(s.get("workspace"), get_nested(meta, "repo.url"))) or "(empty)"
        if f == "language":
            return first_nonempty(get_nested(meta, "repo.language")).lower() or "(empty)"
        if f == "task":
            return first_nonempty(s.get("task"), meta.get("task")) or "(empty)"
        if f == "payload_id":
            return first_nonempty(get_nested(meta, "payload.id")) or "(empty)"
        if f == "payload_category":
            return first_nonempty(get_nested(meta, "payload.category")) or "(empty)"
        if f == "craft_method":
            return first_nonempty(meta.get("craft_method")) or "(empty)"
        if f == "category":
            return first_nonempty(s.get("category")) or "(empty)"
        if f == "subcategory":
            return first_nonempty(s.get("subcategory")) or "(empty)"
        if f == "injection_type":
            inj = s.get("prompt_injections") or []
            vals = sorted({str(x.get("injection_type", "")) for x in inj if isinstance(x, dict) and x.get("injection_type")})
            return ";".join(vals) or "(empty)"
        return first_nonempty(s.get(f), meta.get(f)) or "(empty)"

    total_samples = len(samples)
    run_sample_ids = {r.get("sample_id") for r in rows}
    out = []
    for f in fields:
        ds_counts = Counter(sample_field(s, f) for s in samples)
        res_counts = Counter(str(r.get(f) or "(empty)") for r in rows)
        for value, count in ds_counts.most_common():
            # coverage by sample id for this value
            ids_for_value = {s.get("id") for s in samples if sample_field(s, f) == value}
            covered = len(ids_for_value & run_sample_ids)
            out.append({
                "field": f,
                "value": value,
                "dataset_count": count,
                "dataset_pct": count / total_samples if total_samples else None,
                "covered_unique_samples": covered,
                "coverage_pct": covered / count if count else None,
                "result_count": res_counts.get(value, 0),
            })
    return out


def fmt_cell(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, float):
        return f"{v:.4f}"
    return str(v)


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields: list[str] = []
    for r in rows:
        for k in r.keys():
            if k not in fields:
                fields.append(k)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: fmt_cell(r.get(k)) for k in fields})


def write_md(path: Path, rows: list[dict[str, Any]], max_rows: int = 100) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("(no rows)\n", encoding="utf-8")
        return
    fields = list(rows[0].keys())
    lines = ["| " + " | ".join(fields) + " |", "| " + " | ".join(["---"] * len(fields)) + " |"]
    for r in rows[:max_rows]:
        vals = [fmt_cell(r.get(k)).replace("|", "\\|").replace("\n", " ") for k in fields]
        lines.append("| " + " | ".join(vals) + " |")
    if len(rows) > max_rows:
        lines.append(f"\n... truncated: showing {max_rows}/{len(rows)} rows. See CSV for full table.\n")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def pivot(rows: list[dict[str, Any]], index_field: str, column_field: str = "model", value_field: str = "attack_success") -> list[dict[str, Any]]:
    indexes = sorted({str(r.get(index_field) or "(empty)") for r in rows})
    cols = sorted({str(r.get(column_field) or "(empty)") for r in rows})
    out = []
    for idx in indexes:
        row = {index_field: idx}
        for col in cols:
            vals = [r.get(value_field) for r in rows if str(r.get(index_field) or "(empty)") == idx and str(r.get(column_field) or "(empty)") == col and isinstance(r.get(value_field), int)]
            row[col] = sum(vals)/len(vals) if vals else None
            row[f"{col}_n"] = len(vals)
        out.append(row)
    return out


def svg_bar(path: Path, rows: list[dict[str, Any]], label_field: str, value_field: str, title: str, top_n: int = 20) -> None:
    rows = [r for r in rows if isinstance(r.get(value_field), float)]
    rows = sorted(rows, key=lambda r: r.get(value_field) or 0, reverse=True)[:top_n]
    if not rows:
        return
    width, left, right = 980, 260, 40
    bar_h, gap, top = 22, 8, 50
    height = top + len(rows) * (bar_h + gap) + 40
    maxv = max(1.0, max(float(r[value_field]) for r in rows))
    lines = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">',
             '<style>text{font-family:Arial,sans-serif;font-size:12px}.title{font-size:16px;font-weight:bold}.bar{fill:#4c78a8}.grid{stroke:#ddd;stroke-width:1}</style>',
             f'<text class="title" x="20" y="25">{html.escape(title)}</text>']
    plot_w = width - left - right
    for i in range(6):
        x = left + plot_w * i / 5
        lines.append(f'<line class="grid" x1="{x:.1f}" y1="{top-10}" x2="{x:.1f}" y2="{height-30}"/>')
        lines.append(f'<text x="{x-10:.1f}" y="{height-12}">{i*20}%</text>')
    for i, r in enumerate(rows):
        y = top + i * (bar_h + gap)
        val = float(r[value_field])
        bw = plot_w * val / maxv
        label = str(r.get(label_field) or "(empty)")
        if len(label) > 34:
            label = label[:31] + "..."
        lines.append(f'<text x="10" y="{y+15}">{html.escape(label)}</text>')
        lines.append(f'<rect class="bar" x="{left}" y="{y}" width="{bw:.1f}" height="{bar_h}"/>')
        n = r.get("n_results", r.get("result_count", ""))
        lines.append(f'<text x="{left+bw+5:.1f}" y="{y+15}">{val:.1%} (n={html.escape(str(n))})</text>')
    lines.append("</svg>")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def svg_heatmap(path: Path, rows: list[dict[str, Any]], title: str, index_field: str) -> None:
    if not rows:
        return
    cols = [c for c in rows[0].keys() if c != index_field and not c.endswith("_n")]
    rows = rows[:40]
    cell_w, cell_h = 115, 24
    left, top = 220, 70
    width = left + len(cols) * cell_w + 30
    height = top + len(rows) * cell_h + 40
    lines = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">',
             '<style>text{font-family:Arial,sans-serif;font-size:11px}.title{font-size:16px;font-weight:bold}.cell{stroke:white;stroke-width:1}</style>',
             f'<text class="title" x="20" y="25">{html.escape(title)}</text>']
    for j, col in enumerate(cols):
        lines.append(f'<text transform="translate({left+j*cell_w+12},{top-8}) rotate(-35)">{html.escape(col[:24])}</text>')
    for i, r in enumerate(rows):
        label = str(r.get(index_field) or "(empty)")
        if len(label) > 34:
            label = label[:31] + "..."
        y = top + i * cell_h
        lines.append(f'<text x="10" y="{y+16}">{html.escape(label)}</text>')
        for j, col in enumerate(cols):
            v = r.get(col)
            if isinstance(v, float):
                # white -> red scale
                red = 255
                green = int(245 - 150 * v)
                blue = int(240 - 190 * v)
                text = f"{v:.0%}"
            else:
                red, green, blue, text = 245, 245, 245, ""
            x = left + j * cell_w
            lines.append(f'<rect class="cell" x="{x}" y="{y}" width="{cell_w}" height="{cell_h}" fill="rgb({red},{green},{blue})"/>')
            lines.append(f'<text x="{x+34}" y="{y+16}">{text}</text>')
    lines.append("</svg>")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def build_report(rows: list[dict[str, Any]], samples: list[dict[str, Any]], generated: list[Path], base: Path | None = None) -> str:
    n = len(rows)
    unique_samples = len({r.get("sample_id") for r in rows})
    attack_vals = [r["attack_success"] for r in rows if isinstance(r.get("attack_success"), int)]
    task_vals = [r["task_success"] for r in rows if isinstance(r.get("task_success"), int)]
    alert_vals = [r["alert_success"] for r in rows if isinstance(r.get("alert_success"), int)]
    comp_vals = [r["compromise_success"] for r in rows if isinstance(r.get("compromise_success"), int)]
    lines = [
        "# Experiment Analysis Report",
        "",
        f"- Results analysed: **{n}**",
        f"- Unique samples covered: **{unique_samples} / {len(samples) if samples else 'unknown'}**",
        f"- Overall ASR: **{(sum(attack_vals)/len(attack_vals)):.2%}** ({sum(attack_vals)}/{len(attack_vals)})" if attack_vals else "- Overall ASR: n/a",
        f"- Overall TSR: **{(sum(task_vals)/len(task_vals)):.2%}** ({sum(task_vals)}/{len(task_vals)})" if task_vals else "- Overall TSR: n/a",
        f"- Overall alert rate: **{(sum(alert_vals)/len(alert_vals)):.2%}** ({sum(alert_vals)}/{len(alert_vals)})" if alert_vals else "- Overall alert rate: n/a",
        f"- Attack+Task compromise rate: **{(sum(comp_vals)/len(comp_vals)):.2%}** ({sum(comp_vals)}/{len(comp_vals)})" if comp_vals else "- Attack+Task compromise rate: n/a",
        "",
        "## Key files",
    ]
    for p in generated:
        try:
            rel = p.relative_to(base) if base is not None else p
        except Exception:
            rel = p
        lines.append(f"- `{rel}`")
    lines.append("")
    lines.append("## Reading tips")
    lines.append("- `asr` is attack_success rate over results with a parseable attack_success value.")
    lines.append("- `tsr` is benign task success rate; `alert_rate` is the rate at which the agent explicitly noticed/reported the injection risk.")
    lines.append("- `compromise_rate` requires both attack and task success.")
    lines.append("- Dataset quality tables compare the source dataset distribution with the subset already run.")
    return "\n".join(lines) + "\n"



def latest_records(rows: list[dict[str, Any]], key_fields: tuple[str, ...] = ("sample_id", "agent", "model")) -> list[dict[str, Any]]:
    """Keep the newest row for each logical experiment key."""
    latest: dict[tuple[str, ...], dict[str, Any]] = {}
    for r in rows:
        key = tuple(str(r.get(f, "")) for f in key_fields)
        old = latest.get(key)
        if old is None or float(r.get("result_time_sort") or 0) >= float(old.get("result_time_sort") or 0):
            latest[key] = r
    return sorted(latest.values(), key=lambda r: (str(r.get("agent")), str(r.get("model")), str(r.get("sample_id"))))

def analyse(
    dataset: str | Path = "data/ciip/dataset.json",
    results_root: str | Path = "test/exp/dataset",
    dataset_name: str = "ciip",
    match: str = "exact",
    out: str | Path | None = "test/analysis/ciip",
    breakdowns: str | Iterable[str] = ",".join(DEFAULT_BREAKDOWNS),
    top_n: int = 20,
    latest_only: bool = False,
    exclude_stale: bool = False,
    agent_filter: str | None = None,
    model_filter: str | None = None,
) -> dict[str, Any]:
    dataset_path = Path(dataset)
    results_root = Path(results_root)
    out_path = Path(out) if out is not None else None
    if out_path is not None:
        out_path.mkdir(parents=True, exist_ok=True)

    samples = dataset_items(dataset_path)
    dataset_by_id = {str(s.get("id")): s for s in samples if isinstance(s, dict) and s.get("id")}
    files = find_result_files(results_root, dataset_name, match)
    rows: list[dict[str, Any]] = []
    bad: list[dict[str, Any]] = []
    for p in files:
        try:
            objects = iter_result_objects(p)
            if not objects:
                bad.append({"path": str(p), "error": "unsupported JSON shape"})
                continue
            for obj, ref_suffix in objects:
                try:
                    rows.append(extract_record(p, results_root, dataset_by_id, result_obj=obj, ref_suffix=ref_suffix))
                except Exception as e:
                    bad.append({"path": str(p) + ref_suffix, "error": repr(e)})
        except Exception as e:
            bad.append({"path": str(p), "error": repr(e)})

    if agent_filter:
        rows = [r for r in rows if str(r.get("agent") or "") == agent_filter]
    if model_filter:
        rows = [r for r in rows if str(r.get("model") or "") == model_filter]

    all_rows = rows
    if exclude_stale:
        rows = [r for r in rows if r.get("sample_changed") != 1]
    if latest_only:
        rows = latest_records(rows)

    if isinstance(breakdowns, str):
        fields = [x.strip() for x in breakdowns.split(",") if x.strip()]
    else:
        fields = [str(x).strip() for x in breakdowns if str(x).strip()]

    exp_summary = summarise(rows, ["agent", "model", "run_dir"])
    model_summary = summarise(rows, ["agent", "model"])
    breakdown_tables = {f: summarise(rows, [f]) for f in fields}
    pivot_tables = {f: pivot(rows, f, "model", "attack_success") for f in fields if f not in {"model", "agent"}}
    quality_fields = [f for f in fields if f not in {"model", "agent"}]
    q = dataset_quality(samples, rows, quality_fields) if samples else []
    report_text = build_report(rows, samples, [])

    generated: list[Path] = []
    if out_path is not None:
        for name, data in [("records.csv", rows), ("bad_results.csv", bad)]:
            p = out_path / name
            write_csv(p, data)
            generated.append(p)

        for suffix, writer in [("csv", write_csv), ("md", write_md)]:
            p = out_path / f"summary_by_experiment.{suffix}"
            writer(p, exp_summary)  # type: ignore[arg-type]
            generated.append(p)

        write_csv(out_path / "summary_by_model.csv", model_summary)
        write_md(out_path / "summary_by_model.md", model_summary)
        generated.extend([out_path / "summary_by_model.csv", out_path / "summary_by_model.md"])

        for f, summary in breakdown_tables.items():
            csv_p = out_path / f"breakdown_by_{f}.csv"
            md_p = out_path / f"breakdown_by_{f}.md"
            write_csv(csv_p, summary)
            write_md(md_p, summary)
            generated.extend([csv_p, md_p])
            if f not in {"model", "agent"}:
                piv = pivot_tables[f]
                pcsv = out_path / f"pivot_{f}_by_model.csv"
                pmd = out_path / f"pivot_{f}_by_model.md"
                write_csv(pcsv, piv)
                write_md(pmd, piv)
                generated.extend([pcsv, pmd])

        write_csv(out_path / "dataset_quality.csv", q)
        write_md(out_path / "dataset_quality.md", q, max_rows=200)
        generated.extend([out_path / "dataset_quality.csv", out_path / "dataset_quality.md"])

        fig_dir = out_path / "figures"
        svg_bar(fig_dir / "asr_by_model.svg", model_summary, "model", "asr", "Attack Success Rate by Model", top_n)
        generated.append(fig_dir / "asr_by_model.svg")
        for f in ["repo", "language", "task", "payload_id", "craft_method", "category"]:
            if f in fields:
                summary = breakdown_tables[f]
                svg_bar(fig_dir / f"asr_by_{f}.svg", summary, f, "asr", f"Attack Success Rate by {f}", top_n)
                generated.append(fig_dir / f"asr_by_{f}.svg")
                piv = pivot_tables[f]
                svg_heatmap(fig_dir / f"heatmap_{f}_by_model.svg", piv, f"ASR: {f} by model", f)
                generated.append(fig_dir / f"heatmap_{f}_by_model.svg")

        report_text = build_report(rows, samples, [p for p in generated if p.exists()], out_path)
        (out_path / "README.md").write_text(report_text, encoding="utf-8")
        generated.append(out_path / "README.md")

    return {
        "dataset_path": dataset_path,
        "results_root": results_root,
        "dataset_name": dataset_name,
        "match": match,
        "out": out_path,
        "files": files,
        "records": rows,
        "all_record_count": len(all_rows),
        "stale_record_count": sum(1 for r in all_rows if r.get("sample_changed") == 1),
        "bad_results": bad,
        "exp_summary": exp_summary,
        "model_summary": model_summary,
        "breakdowns": breakdown_tables,
        "pivot_tables": pivot_tables,
        "dataset_quality": q,
        "report_md": report_text,
        "generated": generated,
        "fields": fields,
        "agent_filter": agent_filter,
        "model_filter": model_filter,
        "sample_count": len(samples),
        "unique_sample_count": len({r.get("sample_id") for r in rows}),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Analyse coding-agent redteam result_*.json files")
    ap.add_argument("--dataset", default="data/ciip/dataset.json", help="Source dataset JSON used for metadata/coverage")
    ap.add_argument("--results-root", default="test/exp/dataset", help="Root directory containing result_*.json")
    ap.add_argument("--dataset-name", default="ciip", help="Filter result paths by dataset folder/name. Empty disables filtering.")
    ap.add_argument("--match", choices=["exact", "contains"], default="exact", help="How --dataset-name filters result paths")
    ap.add_argument("--out", default="test/analysis/ciip", help="Output directory")
    ap.add_argument("--breakdowns", default=",".join(DEFAULT_BREAKDOWNS), help="Comma-separated fields to group by")
    ap.add_argument("--top-n", type=int, default=20, help="Top N rows in SVG bar charts")
    ap.add_argument("--latest-only", action="store_true", help="Keep only the newest row per sample_id/agent/model")
    ap.add_argument("--exclude-stale", action="store_true", help="Exclude rows whose embedded sample differs from the current dataset sample")
    ap.add_argument("--agent", dest="agent_filter", default=None, help="Only analyse this agent/software, e.g. opencode_cli")
    ap.add_argument("--model", dest="model_filter", default=None, help="Only analyse this model, e.g. deepseek-v4-pro")
    args = ap.parse_args()
    result = analyse(
        dataset=args.dataset,
        results_root=args.results_root,
        dataset_name=args.dataset_name,
        match=args.match,
        out=args.out,
        breakdowns=args.breakdowns,
        top_n=args.top_n,
        latest_only=args.latest_only,
        exclude_stale=args.exclude_stale,
        agent_filter=args.agent_filter,
        model_filter=args.model_filter,
    )

    rows = result["records"]
    bad = result["bad_results"]
    files = result["files"]
    out = result["out"]
    print(f"Analysed {len(rows)} results from {len(files)} files; {len(bad)} failed to parse.")
    print(f"Raw result entries before filters/dedupe: {result.get('all_record_count')}; stale vs current dataset: {result.get('stale_record_count')}.")
    print(f"Dataset samples: {result['sample_count']}. Unique result samples: {result['unique_sample_count']}.")
    if result.get("agent_filter") or result.get("model_filter"):
        print(f"Filters: agent={result.get('agent_filter') or '*'}, model={result.get('model_filter') or '*'}")
    print(f"Wrote analysis to: {out}")
    if bad and out is not None:
        print(f"Warning: parse failures written to {out / 'bad_results.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
