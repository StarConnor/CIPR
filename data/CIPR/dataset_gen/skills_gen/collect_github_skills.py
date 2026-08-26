"""Collect GitHub agent skills and rules without language filtering.

The old collector searched for ``<language> skills`` and then tried to find a
small number of language-specific development skills.  That produced low-recall,
low-star repositories.  This refactor treats skills/rules as a global pool:

* collect up to ``--target-skills`` individual Claude/Codex-style skill folders
  (directories containing ``SKILL.md``);
* collect up to ``--target-rules`` individual agent-rule files such as
  ``AGENTS.md``, ``CLAUDE.md``, ``.cursorrules`` and ``.cursor/rules/*.mdc``;
* rank repositories by GitHub stars, copy each item independently, and write
  manifests so ``dataset_gen.main`` can randomly sample one skill/rule per
  generated sample.

Environment:
    GITHUB_TOKEN       strongly recommended; required for GitHub code search
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

import requests
try:
    from tqdm import tqdm
except Exception:  # pragma: no cover - tqdm is optional
    tqdm = None  # type: ignore

DEFAULT_OUTPUT_DIR = Path("data/skills")
DEFAULT_RULES_OUTPUT_DIR = Path("data/rules")
DEFAULT_CACHE_DIR = Path("data/skills/_repo_cache")
DEFAULT_RATE_LIMIT_BUFFER_SECONDS = 8

EXCLUDE_DIRS = {
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    "dist",
    "build",
    "target",
    ".next",
    ".cache",
    "vendor",
}

RULE_FILENAMES = {
    "AGENTS.md",
    "CLAUDE.md",
    "GEMINI.md",
    "CODEX.md",
    ".cursorrules",
    ".windsurfrules",
}


@dataclass
class RepoCandidate:
    full_name: str
    clone_url: str
    html_url: str
    stars: int
    description: str
    default_branch: str
    source: str = ""


@dataclass
class SkillRecord:
    id: str
    type: str
    language: str
    full_name: str
    html_url: str
    stars: int
    source_path: str
    saved_dir: str
    skill_md_path: str


@dataclass
class RuleRecord:
    id: str
    type: str
    full_name: str
    html_url: str
    stars: int
    source_path: str
    saved_path: str
    rule_kind: str


class GitHubRateLimitError(RuntimeError):
    def __init__(self, status_code: int, reset_epoch: int | None, message: str):
        self.status_code = status_code
        self.reset_epoch = reset_epoch
        super().__init__(message)


def progress(iterable=None, **kwargs):
    """Small tqdm wrapper so the script still works if tqdm is unavailable."""
    if tqdm is None:
        return iterable if iterable is not None else _NoopProgress(**kwargs)
    return tqdm(iterable, **kwargs) if iterable is not None else tqdm(**kwargs)


class _NoopProgress:
    def __init__(self, *args, **kwargs):
        self.n = kwargs.get("initial", 0)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def update(self, n: int = 1) -> None:
        self.n += n

    def set_postfix(self, *args, **kwargs) -> None:
        return None

    def close(self) -> None:
        return None


def log(message: str) -> None:
    if tqdm is not None:
        tqdm.write(message)
    else:
        print(message)


def slug_repo(full_name: str) -> str:
    return full_name.replace("/", "__")


def safe_slug(text: str, max_len: int = 120) -> str:
    text = re.sub(r"[^A-Za-z0-9._-]+", "_", text.strip("/"))
    text = re.sub(r"_+", "_", text).strip("._-")
    return (text or "item")[:max_len]


def github_headers() -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _parse_reset_epoch(value: str | None) -> int | None:
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _rate_remaining(resp: requests.Response) -> int | None:
    value = resp.headers.get("X-RateLimit-Remaining")
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def github_get_json(
    url: str,
    params: dict[str, Any] | None = None,
    *,
    retry_rate_limit: bool = True,
    max_rate_limit_retries: int = 3,
) -> dict[str, Any]:
    """GET JSON from GitHub, waiting for primary search/code-search limits.

    GitHub has separate buckets: core (usually 5000/hour), repository search
    (30/minute), and code search (10/minute).  The collector can easily exhaust
    code_search even when `curl /rate_limit` still shows thousands of core
    requests remaining.  When GitHub returns 403/429 with X-RateLimit-Remaining=0,
    sleep until X-RateLimit-Reset and retry instead of dropping the query.
    """
    attempt = 0
    while True:
        resp = requests.get(url, headers=github_headers(), params=params or {}, timeout=45)
        if resp.status_code not in {403, 429}:
            resp.raise_for_status()
            return resp.json()

        reset_epoch = _parse_reset_epoch(resp.headers.get("X-RateLimit-Reset"))
        remaining = _rate_remaining(resp)
        body = resp.text[:300].replace("\n", " ")
        is_primary_limit = remaining == 0 or "rate limit exceeded" in body.lower()
        if not retry_rate_limit or not is_primary_limit or attempt >= max_rate_limit_retries:
            raise GitHubRateLimitError(
                resp.status_code,
                reset_epoch,
                f"GitHub rate limited ({resp.status_code}); remaining={remaining}; "
                f"reset={reset_epoch}; {body}",
            )

        now = int(time.time())
        if reset_epoch and reset_epoch > now:
            wait_seconds = reset_epoch - now + DEFAULT_RATE_LIMIT_BUFFER_SECONDS
        else:
            # Secondary/abuse limits sometimes omit a useful reset timestamp.
            wait_seconds = 65
        attempt += 1
        log(
            f"[rate-limit] GitHub {resp.status_code}; remaining={remaining}; "
            f"sleeping {wait_seconds}s until retry {attempt}/{max_rate_limit_retries}"
        )
        time.sleep(wait_seconds)


def repo_item_to_candidate(item: dict[str, Any], source: str = "") -> RepoCandidate:
    return RepoCandidate(
        full_name=item["full_name"],
        clone_url=item["clone_url"],
        html_url=item["html_url"],
        stars=int(item.get("stargazers_count") or 0),
        description=item.get("description") or "",
        default_branch=item.get("default_branch") or "main",
        source=source,
    )


def fetch_repo_candidate(full_name: str, source: str = "", sleep: float = 0.05) -> RepoCandidate | None:
    try:
        item = github_get_json(f"https://api.github.com/repos/{full_name}")
        time.sleep(sleep)
        return repo_item_to_candidate(item, source=source)
    except Exception as exc:
        log(f"[warn] repo metadata failed for {full_name}: {exc}")
        return None


def merge_candidates(candidates: Iterable[RepoCandidate]) -> list[RepoCandidate]:
    by_name: dict[str, RepoCandidate] = {}
    for cand in candidates:
        old = by_name.get(cand.full_name)
        if old is None or cand.stars > old.stars:
            by_name[cand.full_name] = cand
        elif old and cand.source and cand.source not in old.source:
            old.source = f"{old.source};{cand.source}" if old.source else cand.source
    return sorted(by_name.values(), key=lambda c: (-c.stars, c.full_name.lower()))


def paged_search(url: str, base_params: dict[str, Any], max_items: int, sleep: float) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    per_page = min(100, max(10, base_params.get("per_page", 100)))
    max_pages = min(10, (max_items + per_page - 1) // per_page)
    for page in range(1, max_pages + 1):
        params = dict(base_params, per_page=per_page, page=page)
        data = github_get_json(url, params=params)
        items = data.get("items") or []
        out.extend(items)
        time.sleep(sleep)
        if len(items) < per_page or len(out) >= max_items:
            break
    return out[:max_items]


def skill_code_queries() -> list[str]:
    # Multiple broad queries are intentional: GitHub code search caps each query,
    # so overlap-deduping across queries gives much higher recall.
    return [
        "filename:SKILL.md path:skills",
        "filename:SKILL.md path:.claude/skills",
        "filename:SKILL.md path:claude-skills",
        "filename:SKILL.md Claude skill",
        "filename:SKILL.md Codex skill",
        "filename:SKILL.md agent skill",
        "filename:SKILL.md allowed-tools",
        "filename:SKILL.md description name",
        'filename:SKILL.md "##" "Instructions"',
        'filename:SKILL.md "When to use"',
        'filename:SKILL.md "coding"',
        'filename:SKILL.md "development"',
    ]


def skill_repo_queries() -> list[str]:
    return [
        "claude skills SKILL.md in:name,description,readme",
        "codex skills SKILL.md in:name,description,readme",
        "agent skills SKILL.md in:name,description,readme",
        '"Claude Code" skills in:name,description,readme',
        '"AI agent" skills in:name,description,readme',
        '"skill marketplace" claude in:name,description,readme',
        '"awesome" "claude" "skills" in:name,description,readme',
    ]


def rule_code_queries() -> list[str]:
    return [
        "filename:AGENTS.md",
        "filename:CLAUDE.md",
        "filename:CODEX.md",
        "filename:GEMINI.md",
        "filename:.cursorrules",
        "filename:.windsurfrules",
        "path:.cursor/rules extension:mdc",
        "path:.cursor/rules extension:md",
        "path:.github/copilot-instructions.md",
    ]


def rule_repo_queries() -> list[str]:
    return [
        "AGENTS.md in:readme,description",
        "CLAUDE.md in:readme,description",
        ".cursorrules in:readme,description",
        "cursor rules in:readme,description",
        "agent rules in:readme,description",
    ]


def search_repos_from_code(queries: list[str], max_repos: int, sleep: float, source_prefix: str) -> list[RepoCandidate]:
    if not os.environ.get("GITHUB_TOKEN"):
        log("[warn] GITHUB_TOKEN is not set; GitHub code search is unavailable")
        return []

    names: dict[str, str] = {}
    per_query = min(1000, max(100, max_repos * 3 // max(1, len(queries))))
    query_iter = progress(queries, total=len(queries), desc=f"{source_prefix} code queries", unit="query")
    for query in query_iter:
        try:
            items = paged_search("https://api.github.com/search/code", {"q": query}, per_query, sleep)
        except Exception as exc:
            log(f"[warn] code search failed query={query!r}: {exc}")
            continue
        for item in items:
            full_name = (item.get("repository") or {}).get("full_name")
            if full_name:
                names.setdefault(full_name, query)
        log(f"[search] code query={query!r}: repos_so_far={len(names)}")
        if hasattr(query_iter, "set_postfix"):
            query_iter.set_postfix(repos=len(names))
        if len(names) >= max_repos * 2:
            break

    candidates: list[RepoCandidate] = []
    metadata_items = list(names.items())[: max_repos * 3]
    for i, (full_name, query) in enumerate(
        progress(metadata_items, total=len(metadata_items), desc=f"{source_prefix} repo metadata", unit="repo")
    ):
        if i >= max_repos * 3:
            break
        cand = fetch_repo_candidate(full_name, source=f"{source_prefix}:code:{query}", sleep=sleep)
        if cand:
            candidates.append(cand)
    return merge_candidates(candidates)[:max_repos]


def search_repos_from_repo_search(queries: list[str], max_repos: int, sleep: float, source_prefix: str) -> list[RepoCandidate]:
    candidates: list[RepoCandidate] = []
    per_query = min(1000, max(100, max_repos * 3 // max(1, len(queries))))
    query_iter = progress(queries, total=len(queries), desc=f"{source_prefix} repo queries", unit="query")
    for query in query_iter:
        try:
            items = paged_search(
                "https://api.github.com/search/repositories",
                {"q": query, "sort": "stars", "order": "desc"},
                per_query,
                sleep,
            )
        except Exception as exc:
            log(f"[warn] repo search failed query={query!r}: {exc}")
            continue
        for item in items:
            candidates.append(repo_item_to_candidate(item, source=f"{source_prefix}:repo:{query}"))
        log(f"[search] repo query={query!r}: candidates_so_far={len(candidates)}")
        if hasattr(query_iter, "set_postfix"):
            query_iter.set_postfix(candidates=len(candidates))
    return merge_candidates(candidates)[:max_repos]


def search_candidates(kind: str, max_repos: int, sleep: float) -> list[RepoCandidate]:
    if kind == "skills":
        code = search_repos_from_code(skill_code_queries(), max_repos=max_repos, sleep=sleep, source_prefix="skills")
        repo = search_repos_from_repo_search(skill_repo_queries(), max_repos=max_repos, sleep=sleep, source_prefix="skills")
    elif kind == "rules":
        code = search_repos_from_code(rule_code_queries(), max_repos=max_repos, sleep=sleep, source_prefix="rules")
        repo = search_repos_from_repo_search(rule_repo_queries(), max_repos=max_repos, sleep=sleep, source_prefix="rules")
    else:
        raise ValueError(f"unknown kind: {kind}")
    return merge_candidates(code + repo)[:max_repos]


def run(cmd: list[str], cwd: Path | None = None, timeout: int | None = None) -> None:
    subprocess.run(cmd, cwd=str(cwd) if cwd else None, check=True, timeout=timeout)


def clone_or_update(candidate: RepoCandidate, cache_dir: Path, force: bool = False, timeout: int | None = None) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    dst = cache_dir / slug_repo(candidate.full_name)
    if force and dst.exists():
        shutil.rmtree(dst)
    if dst.exists():
        return dst
    try:
        run(["git", "clone", "--depth", "1", candidate.clone_url, str(dst)], timeout=timeout)
    except Exception:
        if dst.exists():
            shutil.rmtree(dst, ignore_errors=True)
        raise
    return dst


def read_text_limited(path: Path, max_chars: int = 20000) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")[:max_chars]
    except Exception:
        return ""


def is_excluded(path: Path, root: Path) -> bool:
    try:
        parts = path.relative_to(root).parts
    except ValueError:
        parts = path.parts
    return any(part in EXCLUDE_DIRS for part in parts)


def find_skill_md_file(skill_dir: Path) -> Path | None:
    for child in skill_dir.iterdir() if skill_dir.exists() else []:
        if child.is_file() and child.name.lower() == "skill.md":
            return child
    return None


def discover_leaf_skill_dirs(repo_dir: Path, max_skills: int = 500) -> list[Path]:
    out: list[Path] = []
    for skill_md in (p for p in repo_dir.rglob("*") if p.is_file() and p.name.lower() == "skill.md"):
        if is_excluded(skill_md, repo_dir):
            continue
        # Avoid copying a repository-root SKILL.md unless it sits in a plausible
        # agent-skill collection; root files are often project docs.
        parent = skill_md.parent
        rel = parent.relative_to(repo_dir).as_posix()
        if rel == "." and not any((repo_dir / name).exists() for name in ("skills", ".claude")):
            continue
        text = read_text_limited(skill_md, 12000).lower()
        if not looks_like_skill_md(text, rel):
            continue
        out.append(parent)
        if len(out) >= max_skills:
            break
    return sorted(set(out), key=lambda p: p.relative_to(repo_dir).as_posix())


def looks_like_skill_md(text: str, rel_path: str) -> bool:
    signal_terms = ["skill", "description", "instructions", "allowed-tools", "when to use", "agent", "claude", "codex"]
    path_signal = any(part in rel_path.lower() for part in ["skill", ".claude"])
    hits = sum(term in text for term in signal_terms)
    if len(text.strip()) < 80:
        return False
    return path_signal or hits >= 2


def ignore_for_copy(dir_path: str, names: list[str]) -> set[str]:
    ignored = {n for n in names if n in EXCLUDE_DIRS}
    for n in names:
        p = Path(dir_path) / n
        try:
            if p.is_file() and p.stat().st_size > 2_000_000:
                ignored.add(n)
        except OSError:
            ignored.add(n)
    return ignored


def copy_one_skill(repo_dir: Path, candidate: RepoCandidate, skill_dir: Path, output_dir: Path, idx: int, overwrite: bool) -> SkillRecord:
    rel = skill_dir.relative_to(repo_dir).as_posix()
    item_id = f"skill_{idx:04d}__{safe_slug(slug_repo(candidate.full_name))}__{safe_slug(rel)}"
    dest = output_dir / "items" / item_id
    if overwrite and dest.exists():
        shutil.rmtree(dest)
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(skill_dir, dest, ignore=ignore_for_copy)
    return SkillRecord(
        id=item_id,
        type="skill",
        language="all",
        full_name=candidate.full_name,
        html_url=candidate.html_url,
        stars=candidate.stars,
        source_path=rel,
        saved_dir=str(dest),
        skill_md_path=str(find_skill_md_file(dest) or (dest / "SKILL.md")),
    )


def discover_rule_files(repo_dir: Path, max_rules: int = 500) -> list[Path]:
    out: list[Path] = []
    for p in repo_dir.rglob("*"):
        if len(out) >= max_rules:
            break
        if is_excluded(p, repo_dir) or not p.is_file():
            continue
        rel = p.relative_to(repo_dir).as_posix()
        name = p.name
        if name in RULE_FILENAMES:
            pass
        elif rel == ".github/copilot-instructions.md":
            pass
        elif rel.startswith(".cursor/rules/") and p.suffix.lower() in {".md", ".mdc"}:
            pass
        else:
            continue
        try:
            if p.stat().st_size < 80 or p.stat().st_size > 500_000:
                continue
        except OSError:
            continue
        text = read_text_limited(p, 4000).lower()
        if looks_like_rule_file(text, rel):
            out.append(p)
    return sorted(set(out), key=lambda p: p.relative_to(repo_dir).as_posix())


def looks_like_rule_file(text: str, rel_path: str) -> bool:
    if rel_path.endswith(".mdc") and ("description:" in text or "globs:" in text or "alwaysapply" in text):
        return True
    terms = ["instruction", "guideline", "rule", "agent", "claude", "codex", "cursor", "repository", "code", "test", "do not", "must"]
    return sum(t in text for t in terms) >= 2


def rule_kind(path: Path, repo_dir: Path) -> str:
    rel = path.relative_to(repo_dir).as_posix()
    if rel.startswith(".cursor/rules/"):
        return "cursor-rule"
    if rel == ".github/copilot-instructions.md":
        return "copilot-instructions"
    return path.name


def copy_one_rule(repo_dir: Path, candidate: RepoCandidate, rule_file: Path, output_dir: Path, idx: int, overwrite: bool) -> RuleRecord:
    rel = rule_file.relative_to(repo_dir).as_posix()
    suffix = rule_file.suffix or ".txt"
    item_id = f"rule_{idx:04d}__{safe_slug(slug_repo(candidate.full_name))}__{safe_slug(rel)}"
    dest = output_dir / "items" / f"{item_id}{suffix}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    if overwrite and dest.exists():
        dest.unlink()
    shutil.copy2(rule_file, dest)
    return RuleRecord(
        id=item_id,
        type="rule",
        full_name=candidate.full_name,
        html_url=candidate.html_url,
        stars=candidate.stars,
        source_path=rel,
        saved_path=str(dest),
        rule_kind=rule_kind(rule_file, repo_dir),
    )


def append_jsonl(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def collect_skills(args: argparse.Namespace) -> list[SkillRecord]:
    args.output_dir.mkdir(parents=True, exist_ok=True)
    candidates = search_candidates("skills", max_repos=args.max_repos, sleep=args.github_sleep)
    log(f"[skills] found {len(candidates)} candidate repos")
    records: list[SkillRecord] = []
    seen_source: set[tuple[str, str]] = set()
    with progress(total=args.target_skills, desc="collect skills", unit="skill") as pbar:
        for repo_index, cand in enumerate(candidates, start=1):
            if len(records) >= args.target_skills:
                break
            pbar.set_postfix(repo=f"{repo_index}/{len(candidates)} {cand.full_name[:32]}", stars=cand.stars)
            log(f"[skills] checking {cand.full_name} ({cand.stars}★)")
            try:
                repo_dir = clone_or_update(cand, args.cache_dir, force=args.force_clone, timeout=args.clone_timeout)
                dirs = discover_leaf_skill_dirs(repo_dir, max_skills=args.max_items_per_repo)
                copied = 0
                for skill_dir in dirs:
                    if len(records) >= args.target_skills:
                        break
                    rel = skill_dir.relative_to(repo_dir).as_posix()
                    key = (cand.full_name, rel)
                    if key in seen_source:
                        continue
                    seen_source.add(key)
                    rec = copy_one_skill(repo_dir, cand, skill_dir, args.output_dir, len(records) + 1, overwrite=args.overwrite)
                    records.append(rec)
                    append_jsonl(args.output_dir / "selected_skills.jsonl", asdict(rec))
                    copied += 1
                    pbar.update(1)
                log(f"  copied {copied} skill(s); total={len(records)}/{args.target_skills}")
            except Exception as exc:
                append_jsonl(args.output_dir / "errors.jsonl", {"candidate": asdict(cand), "error": repr(exc)})
                log(f"  error: {exc}")
    return records


def collect_rules(args: argparse.Namespace) -> list[RuleRecord]:
    args.rules_output_dir.mkdir(parents=True, exist_ok=True)
    candidates = search_candidates("rules", max_repos=args.max_rule_repos, sleep=args.github_sleep)
    log(f"[rules] found {len(candidates)} candidate repos")
    records: list[RuleRecord] = []
    seen_source: set[tuple[str, str]] = set()
    with progress(total=args.target_rules, desc="collect rules", unit="rule") as pbar:
        for repo_index, cand in enumerate(candidates, start=1):
            if len(records) >= args.target_rules:
                break
            pbar.set_postfix(repo=f"{repo_index}/{len(candidates)} {cand.full_name[:32]}", stars=cand.stars)
            log(f"[rules] checking {cand.full_name} ({cand.stars}★)")
            try:
                repo_dir = clone_or_update(cand, args.cache_dir, force=args.force_clone, timeout=args.clone_timeout)
                files = discover_rule_files(repo_dir, max_rules=args.max_rules_per_repo)
                copied = 0
                for rule_file in files:
                    if len(records) >= args.target_rules:
                        break
                    rel = rule_file.relative_to(repo_dir).as_posix()
                    key = (cand.full_name, rel)
                    if key in seen_source:
                        continue
                    seen_source.add(key)
                    rec = copy_one_rule(repo_dir, cand, rule_file, args.rules_output_dir, len(records) + 1, overwrite=args.overwrite)
                    records.append(rec)
                    append_jsonl(args.rules_output_dir / "selected_rules.jsonl", asdict(rec))
                    copied += 1
                    pbar.update(1)
                log(f"  copied {copied} rule(s); total={len(records)}/{args.target_rules}")
            except Exception as exc:
                append_jsonl(args.rules_output_dir / "errors.jsonl", {"candidate": asdict(cand), "error": repr(exc)})
                log(f"  error: {exc}")
    return records


def write_manifest(path: Path, records: list[dict[str, Any]], description: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        "metadata": {
            "total": len(records),
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "description": description,
        },
        "data": records,
    }
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Collect a global pool of GitHub agent skills and rules")
    p.add_argument("--target-skills", type=int, default=2400, help="number of individual skill directories to collect")
    p.add_argument("--target-rules", type=int, default=2400, help="number of individual rule files to collect")
    p.add_argument("--max-repos", type=int, default=1000, help="maximum skill candidate repos to inspect")
    p.add_argument("--max-rule-repos", type=int, default=3000, help="maximum rule candidate repos to inspect")
    p.add_argument("--max-items-per-repo", type=int, default=500, help="maximum SKILL.md directories to copy from one repo")
    p.add_argument("--max-rules-per-repo", type=int, default=200, help="maximum rule files to copy from one repo")
    p.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    p.add_argument("--rules-output-dir", type=Path, default=DEFAULT_RULES_OUTPUT_DIR)
    p.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    p.add_argument("--github-sleep", type=float, default=0.25)
    p.add_argument("--clone-timeout", type=int, default=180, help="seconds before abandoning a slow git clone")
    p.add_argument("--collect", nargs="+", choices=["skills", "rules"], default=["skills", "rules"], help="which pools to collect")
    p.add_argument("--overwrite", action="store_true", help="overwrite copied items")
    p.add_argument("--force-clone", action="store_true", help="delete and re-clone cached repos")

    # Backward-compatible no-op arguments from the old language-specific CLI.
    p.add_argument("--languages", nargs="+", default=None, help=argparse.SUPPRESS)
    p.add_argument("--per-language", type=int, default=None, help=argparse.SUPPRESS)
    p.add_argument("--candidates-per-language", type=int, default=None, help=argparse.SUPPRESS)
    p.add_argument("--search-mode", default=None, help=argparse.SUPPRESS)
    p.add_argument("--use-llm", action="store_true", help=argparse.SUPPRESS)
    p.add_argument("--model", default=None, help=argparse.SUPPRESS)
    p.add_argument("--min-confidence", type=float, default=None, help=argparse.SUPPRESS)
    p.add_argument("--skill-min-confidence", type=float, default=None, help=argparse.SUPPRESS)
    p.add_argument("--max-skills-per-repo", type=int, default=None, help=argparse.SUPPRESS)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    if args.max_skills_per_repo is not None:
        args.max_items_per_repo = args.max_skills_per_repo

    skill_records: list[SkillRecord] = []
    rule_records: list[RuleRecord] = []
    if "skills" in args.collect:
        skill_records = collect_skills(args)
        write_manifest(
            args.output_dir / "manifest.json",
            [asdict(r) for r in skill_records],
            "Global GitHub Claude/Codex-style skill directories; language is intentionally not filtered.",
        )
        log(f"Wrote skills manifest with {len(skill_records)} items: {args.output_dir / 'manifest.json'}")
    if "rules" in args.collect:
        rule_records = collect_rules(args)
        write_manifest(
            args.rules_output_dir / "manifest.json",
            [asdict(r) for r in rule_records],
            "Global GitHub coding-agent rule files sampled from AGENTS/CLAUDE/CODEX/Cursor-style rules.",
        )
        log(f"Wrote rules manifest with {len(rule_records)} items: {args.rules_output_dir / 'manifest.json'}")


if __name__ == "__main__":
    main()
