#!/usr/bin/env python3
"""
Fix CIIR dataset prompt-injection targets that point to files missing at the
issue checkout commit.

What it does:
1. Scans experiment result JSON files for errors like:
   "Injection script failed ... No such file or directory".
2. Maps the failing sample_id back to data/ciir/dataset.json.
3. Checks the target file against the commit that env_setup_script checks out.
4. Chooses an existing replacement file from that same commit.
5. Updates both prompt_injections[*].target_file_path and the base64-encoded
   target embedded in prompt_injections[*].injection_script.

Default is dry-run. Use --apply to modify the dataset. A .bak timestamp backup
is created before writing.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import shutil
import subprocess
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

ERR_RE = re.compile(
    r"Injection script failed for file '(?P<abs>[^']+)'.*?No such file or directory",
    re.S,
)
SCRIPT_TARGET_RE = re.compile(
    r"target=\"\$\(printf %s '(?P<b64>[^']+)' \| base64 -d\)\""
)
CHECKOUT_RE = re.compile(r"git\s+-C\s+/home/devuser/project\s+checkout\s+-f\s+([0-9a-f]{7,40})")
FETCH_RE = re.compile(r"git\s+-C\s+/home/devuser/project\s+fetch(?:\s+--depth=1)?\s+origin\s+([0-9a-f]{7,40})")

DEFAULT_RESULT_GLOBS = [
    "test/exp/dataset/opencode_cli/ciir/deepseek-v4-pro-5/result_*.json",
    "results/zfk-2/ciir_static_file_*.json",
]

LOW_VALUE_NAMES = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock", "cargo.lock",
    "go.sum", "gemfile.lock", "composer.lock", "license", "copying",
}
PREFERRED_NAMES = (
    "README.md", "README.rst", "README.txt", "package.json", "pyproject.toml",
    "setup.py", "pom.xml", "build.gradle", "Makefile", "CMakeLists.txt",
)
SOURCE_EXTS = {".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".c", ".h", ".cpp", ".hpp", ".go", ".rs", ".rb", ".php", ".kt", ".scala", ".cs"}

TEXT_EXTS = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".c", ".h", ".cpp", ".hpp",
    ".go", ".rs", ".rb", ".php", ".sh", ".md", ".rst", ".txt", ".json", ".yaml",
    ".yml", ".toml", ".xml", ".gradle", ".kt", ".scala", ".cs",
}


def run(cmd: list[str], cwd: Path | None = None, check: bool = True) -> str:
    p = subprocess.run(cmd, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if check and p.returncode != 0:
        raise RuntimeError(f"command failed: {' '.join(cmd)}\nstdout={p.stdout}\nstderr={p.stderr}")
    return p.stdout


def normalize_sample_id(sample_id: str) -> str:
    # aggregate ids look like ciir_static_file_<raw sample id>
    prefix = "ciir_static_file_"
    if sample_id.startswith(prefix):
        return sample_id[len(prefix):]
    return sample_id


def extract_missing_path(err_text: str) -> str | None:
    m = ERR_RE.search(err_text)
    if not m:
        return None
    abs_path = m.group("abs")
    project_prefix = "/home/devuser/project/"
    if abs_path.startswith(project_prefix):
        return abs_path[len(project_prefix):]
    return abs_path


def scan_result_file(path: Path) -> list[tuple[str, str, str]]:
    """Return [(raw_sample_id, missing_rel_path, source_file)]."""
    try:
        data = json.loads(path.read_text(errors="replace"))
    except Exception:
        return []

    out: list[tuple[str, str, str]] = []

    def consider(obj: dict[str, Any]):
        sid = obj.get("sample_id")
        if not sid:
            return
        # Error may be in aggregate wrapper; per-sample result files usually do not
        # have wrapper errors, but keep this generic.
        texts = []
        for key in ("error", "exception", "message"):
            if obj.get(key):
                texts.append(str(obj.get(key)))
        # Avoid scanning huge raw_chat_history unless the wrapper clearly failed.
        for txt in texts:
            if "Injection script failed" in txt and "No such file or directory" in txt:
                missing = extract_missing_path(txt)
                if missing:
                    out.append((normalize_sample_id(str(sid)), missing, str(path)))

    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                consider(item)
    elif isinstance(data, dict):
        consider(data)

    return out


def scan_failures(globs: list[str]) -> dict[str, dict[str, Any]]:
    failures: dict[str, dict[str, Any]] = {}
    for pat in globs:
        for path in sorted(Path().glob(pat)):
            for sid, missing, src in scan_result_file(path):
                rec = failures.setdefault(sid, {"missing_paths": set(), "sources": []})
                rec["missing_paths"].add(missing)
                rec["sources"].append(src)
    return failures


def get_checkout_commit(sample: dict[str, Any]) -> str | None:
    script = sample.get("env_setup_script") or ""
    m = CHECKOUT_RE.search(script) or FETCH_RE.search(script)
    return m.group(1) if m else None


def repo_url(sample: dict[str, Any]) -> str | None:
    return (((sample.get("metadata") or {}).get("repo") or {}).get("url"))


def repo_cache_path(cache_dir: Path, sample: dict[str, Any]) -> Path:
    workspace = sample.get("workspace") or sample["id"].split("_p_", 1)[0].removeprefix("r_")
    return cache_dir / workspace.replace("/", "__")


def ensure_repo(cache_dir: Path, sample: dict[str, Any], commit: str, allow_clone: bool) -> Path | None:
    """Return a local git repo containing commit, or None if unavailable."""
    candidates: list[Path] = []
    workspace = sample.get("workspace") or ""
    url = repo_url(sample) or ""
    if "github.com/" in url:
        owner_repo = url.rstrip("/").removesuffix(".git").split("github.com/", 1)[1]
        owner, repo = owner_repo.split("/", 1)
        candidates.extend([
            Path("temp_workspace") / owner / repo,
            Path("temp_workspace") / workspace / repo,
            Path("temp_workspace") / workspace,
        ])
    candidates.append(repo_cache_path(cache_dir, sample))

    for c in candidates:
        if (c / ".git").exists():
            got = run(["git", "cat-file", "-e", f"{commit}^{{commit}}"], cwd=c, check=False)
            if subprocess.run(["git", "cat-file", "-e", f"{commit}^{{commit}}"], cwd=c, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0:
                return c
            # Try fetching the exact commit into existing clone.
            subprocess.run(["git", "fetch", "--depth=1", "origin", commit], cwd=c, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if subprocess.run(["git", "cat-file", "-e", f"{commit}^{{commit}}"], cwd=c, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0:
                return c

    dest = repo_cache_path(cache_dir, sample)
    if not allow_clone:
        return None
    url = repo_url(sample)
    if not url:
        return None
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.exists():
        print(f"[clone] {url} -> {dest}")
        run(["git", "clone", "--filter=blob:none", "--no-checkout", url, str(dest)])
    try:
        run(["git", "fetch", "--depth=1", "origin", commit], cwd=dest)
    except RuntimeError:
        return None
    return dest


def git_file_exists(repo: Path, commit: str, rel: str) -> bool:
    return subprocess.run(["git", "cat-file", "-e", f"{commit}:{rel}"], cwd=repo, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0


def list_files(repo: Path, commit: str) -> list[str]:
    out = run(["git", "ls-tree", "-r", "--name-only", commit], cwd=repo)
    return [line.strip() for line in out.splitlines() if line.strip()]


def file_score(path: str, old_target: str) -> tuple[int, int, str]:
    p = Path(path)
    old = Path(old_target)
    name = p.name.lower()
    ext = p.suffix.lower()
    score = 0
    if p.name == old.name:
        score += 1000
    if ext == old.suffix.lower() and ext:
        score += 500
    if any(part in {"test", "tests", "src", "lib", "config", "cmd", "pkg", "internal"} for part in p.parts):
        score += 80
    if p.name in PREFERRED_NAMES:
        score += 60
    if ext in SOURCE_EXTS:
        score += 140
    elif ext in TEXT_EXTS:
        score += 50
    if name in LOW_VALUE_NAMES:
        score -= 200
    if "docs" in p.parts:
        score -= 120
    if path.endswith(".d.ts"):
        score -= 80
    if "dist" in p.parts or "vendor" in p.parts or "node_modules" in p.parts:
        score -= 500
    # Prefer shorter paths among equally good candidates.
    return (-score, len(path), path)


def choose_replacement(repo: Path, commit: str, old_target: str) -> str | None:
    if git_file_exists(repo, commit, old_target):
        return old_target
    files = list_files(repo, commit)
    candidates = []
    old_ext = Path(old_target).suffix.lower()
    for f in files:
        p = Path(f)
        if p.suffix.lower() in TEXT_EXTS or p.name in PREFERRED_NAMES or p.suffix.lower() == old_ext:
            candidates.append(f)
    if not candidates:
        candidates = files
    if not candidates:
        return None
    return sorted(candidates, key=lambda f: file_score(f, old_target))[0]


def patch_injection_script(script: str, new_target: str) -> str:
    b64 = base64.b64encode(new_target.encode()).decode()
    new_line = f"target=\"$(printf %s '{b64}' | base64 -d)\""
    if SCRIPT_TARGET_RE.search(script):
        return SCRIPT_TARGET_RE.sub(new_line, script, count=1)
    return script


def apply_fix_to_sample(sample: dict[str, Any], old_target: str, new_target: str) -> int:
    changed = 0
    for inj in sample.get("prompt_injections") or []:
        if inj.get("target_file_path") == old_target:
            inj["target_file_path"] = new_target
            changed += 1
        script = inj.get("injection_script")
        if isinstance(script, str):
            patched = patch_injection_script(script, new_target)
            if patched != script:
                inj["injection_script"] = patched
                changed += 1
    return changed


def build_checks_from_all_samples(samples: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Build the same structure as scan_failures(), but from every current dataset target."""
    checks: dict[str, dict[str, Any]] = {}
    for sample in samples:
        sid = sample.get("id")
        if not sid:
            continue
        targets = {
            inj.get("target_file_path")
            for inj in (sample.get("prompt_injections") or [])
            if isinstance(inj.get("target_file_path"), str) and inj.get("target_file_path")
        }
        if targets:
            checks[sid] = {"missing_paths": targets, "sources": ["dataset"]}
    return checks


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="data/ciir/dataset.json")
    ap.add_argument("--result-glob", action="append", dest="result_globs", default=[])
    ap.add_argument("--cache-dir", default=".cache/ciir_fix_repos")
    ap.add_argument("--apply", action="store_true", help="write changes to dataset.json")
    ap.add_argument("--clone", action="store_true", help="clone/fetch repos if not available locally")
    ap.add_argument(
        "--all-samples",
        action="store_true",
        help=(
            "check every current prompt_injections target in the dataset against "
            "the checkout commit from env_setup_script, instead of using old result errors"
        ),
    )
    args = ap.parse_args()

    dataset_path = Path(args.dataset)
    dataset = json.loads(dataset_path.read_text())
    samples = dataset["data"] if isinstance(dataset, dict) and "data" in dataset else dataset
    by_id = {s["id"]: s for s in samples}

    if args.all_samples:
        failures = build_checks_from_all_samples(samples)
        print(f"Checking {len(failures)} samples from current dataset prompt_injections")
    else:
        result_globs = args.result_globs or DEFAULT_RESULT_GLOBS
        failures = scan_failures(result_globs)
        print(f"Found {len(failures)} samples with injection-file-not-found errors")
        if not failures:
            return 0

    planned = []
    already_fixed = []
    ok = []
    unresolved = []
    skipped_no_commit = []

    for sid, info in sorted(failures.items()):
        sample = by_id.get(sid)
        if not sample:
            unresolved.append((sid, "sample id not found in dataset"))
            continue

        commit = get_checkout_commit(sample)
        if not commit:
            # Many prepare_env/run_test samples do not checkout an issue commit. Those
            # are not the problematic class described here, so skip them in all-sample mode.
            if args.all_samples:
                skipped_no_commit.append(sid)
            else:
                unresolved.append((sid, "no checkout commit in env_setup_script"))
            continue

        repo = ensure_repo(Path(args.cache_dir), sample, commit, allow_clone=args.clone)
        if repo is None:
            unresolved.append((sid, "repo/commit unavailable; rerun with --clone or prepare temp_workspace clone"))
            continue

        current_targets = {
            inj.get("target_file_path")
            for inj in (sample.get("prompt_injections") or [])
            if isinstance(inj.get("target_file_path"), str)
        }

        for target in sorted(info["missing_paths"]):
            if target not in current_targets:
                # Old result files may still contain a historical error, but the
                # dataset may already point at a different path.
                current = sorted(t for t in current_targets if isinstance(t, str))
                already_fixed.append((sid, target, ",".join(current)))
                continue

            if git_file_exists(repo, commit, target):
                ok.append((sid, target, str(repo), commit))
                continue

            replacement = choose_replacement(repo, commit, target)
            if not replacement:
                unresolved.append((sid, f"no replacement found for {target}"))
                continue
            planned.append((sid, target, replacement, str(repo), commit))

    if ok:
        print(f"\nExisting targets OK: {len(ok)}")
        for sid, target, repo, commit in ok[:30]:
            print(f"[OK] {sid}: {target}  ({repo}@{commit[:8]})")
        if len(ok) > 30:
            print(f"... {len(ok) - 30} more OK targets omitted")

    if already_fixed:
        print("\nAlready fixed in current dataset:")
        for sid, old, current in already_fixed:
            print(f"[DONE] {sid}: old missing target {old}; current target(s): {current}")

    print("\nPlanned fixes:")
    for sid, old, new, repo, commit in planned:
        print(f"[FIX] {sid}: {old} -> {new}  ({repo}@{commit[:8]})")

    if skipped_no_commit:
        print(f"\nSkipped {len(skipped_no_commit)} samples without checkout commit in env_setup_script")

    if unresolved:
        print("\nUnresolved:")
        for sid, reason in unresolved:
            print(f"[MISS] {sid}: {reason}")

    if args.apply and planned:
        backup = dataset_path.with_suffix(dataset_path.suffix + f".bak.{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        shutil.copy2(dataset_path, backup)
        print(f"\nBackup written: {backup}")
        n_changes = 0
        for sid, old, new, _repo, _commit in planned:
            if old == new:
                continue
            n_changes += apply_fix_to_sample(by_id[sid], old, new)
        tmp = dataset_path.with_suffix(dataset_path.suffix + ".tmp")
        tmp.write_text(json.dumps(dataset, indent=2, ensure_ascii=False) + "\n")
        os.replace(tmp, dataset_path)
        print(f"Applied {n_changes} field/script changes to {dataset_path}")
    else:
        print("\nDry-run only. Re-run with --apply to write dataset changes.")

    return 1 if unresolved else 0


if __name__ == "__main__":
    raise SystemExit(main())
