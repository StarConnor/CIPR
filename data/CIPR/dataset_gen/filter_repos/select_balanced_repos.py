#!/usr/bin/env python3
"""Select a balanced subset of repositories for dataset generation.

Goal used by default:
- read the repo dataset that currently has ~10 repos per language;
- consider the first 10 candidates for each requested language;
- select 5 repos per language;
- make the final 20 repos balanced by development type and by size
  (file-count and LOC tercile bins).

The output is still compatible with dataset_gen.main --repos-dataset.
Example:
    python -m dataset_gen.filter_repos.select_balanced_repos \
      --input repos_dataset.json \
      --output data/repos-selected-4lang-5each.json \
      --languages python javascript c java \
      --candidates-per-language 10 \
      --select-per-language 5
"""

from __future__ import annotations

import argparse
import csv
import itertools
import json
import math
import os
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_LANGUAGES = ["python", "javascript", "c", "java"]
DEV_TYPES = [
    "Web frameworks",
    "Web apps",
    "Identity & security",
    "Networking",
    "Others",
    "ChatBots",
    "IoT",
    "Developer tools",
    "DevOps",
    "Data Science",
]

EXCLUDE_DIRS = {
    ".git", ".hg", ".svn", "node_modules", "vendor", "dist", "build", "target",
    ".venv", "venv", "__pycache__", ".mypy_cache", ".pytest_cache", ".tox",
    ".gradle", ".idea", ".vscode", "coverage", ".next", "out", "tmp",
}
TEXT_EXTS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".c", ".h", ".cc", ".cpp", ".cxx",
    ".hpp", ".java", ".go", ".rs", ".php", ".rb", ".sh", ".bash", ".zsh",
    ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".xml", ".html", ".css",
    ".scss", ".md", ".rst", ".txt", ".sql", ".cmake", ".gradle", ".m", ".mm",
}

# Lightweight keyword taxonomy.  Order matters: more specific classes first,
# broad Web/Developer-tool classes later.
TYPE_KEYWORDS: list[tuple[str, list[str]]] = [
    ("ChatBots", [
        "chatbot", "chat bot", "bot", "assistant", "agent", "llm", "openai", "claude",
        "discord", "telegram", "slack bot",
    ]),
    ("Data Science", [
        "machine learning", "deep learning", "data science", "dataframe", "pandas", "numpy",
        "tensorflow", "pytorch", "computer vision", "face recognition", "ai", "analytics",
        "database for ai", "vector", "embedding", "nlp", "jupyter",
    ]),
    ("Identity & security", [
        "security", "auth", "authentication", "authorization", "oauth", "identity",
        "password", "2fa", "totp", "crypto", "cryptography", "tls", "ssl", "vpn",
        "proxy", "shadowsocks", "encryption", "firewall", "secret",
    ]),
    ("IoT", [
        "iot", "embedded", "firmware", "microcontroller", "keyboard", "qmk", "arduino",
        "raspberry", "sensor", "device", "hardware", "mqtt", "home assistant", "tv",
    ]),
    ("DevOps", [
        "devops", "ci", "cd", "docker", "kubernetes", "k8s", "deploy", "deployment",
        "monitoring", "uptime", "observability", "logstash", "pipeline", "workflow",
        "orchestration", "infrastructure", "serverless",
    ]),
    ("Networking", [
        "network", "http", "client", "server", "rpc", "grpc", "socket", "kafka", "stream",
        "event", "message", "queue", "download", "proxy", "dns", "tcp", "udp", "kcp",
        "websocket", "axios", "requests",
    ]),
    ("Web frameworks", [
        "framework", "web framework", "express", "react", "svelte", "material ui", "mui",
        "spring", "django", "flask", "rails", "laravel", "component", "frontend", "backend",
    ]),
    ("Web apps", [
        "web app", "website", "dashboard", "ui", "browser", "player", "video", "readme stats",
        "static site", "app", "application", "admin", "cms",
    ]),
    ("Developer tools", [
        "developer", "tool", "cli", "command-line", "command line", "terminal", "console",
        "library", "sdk", "package", "build", "test", "debug", "formatter", "linter",
        "generator", "json server", "orm", "mybatis", "gradle", "maven",
    ]),
]


@dataclass(frozen=True)
class Candidate:
    idx: int
    repo: dict[str, Any]
    language: str
    workspace: str
    dev_type: str
    file_count: int
    loc: int
    file_bin: str = "unknown"
    loc_bin: str = "unknown"

    def vector_counts(self) -> tuple[Counter, Counter, Counter]:
        return Counter([self.dev_type]), Counter([self.file_bin]), Counter([self.loc_bin])


def load_dataset(path: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    raw = json.load(open(path, "r", encoding="utf-8"))
    if isinstance(raw, dict) and "data" in raw:
        return raw, list(raw["data"])
    if isinstance(raw, list):
        return {"metadata": {}}, raw
    raise ValueError(f"Unsupported repo dataset format: {path}")


def repo_language(repo: dict[str, Any]) -> str:
    return str((repo.get("metadata") or {}).get("language") or repo.get("language") or "").lower()


def repo_text(repo: dict[str, Any]) -> str:
    md = repo.get("metadata") or {}
    parts = [
        repo.get("workspace", ""),
        md.get("name", ""),
        md.get("full_name", ""),
        md.get("description", ""),
        " ".join(md.get("topics", []) or []),
    ]
    return " ".join(str(p) for p in parts if p).lower()


def classify_dev_type(repo: dict[str, Any]) -> str:
    text = repo_text(repo)
    scores: Counter[str] = Counter()
    for dev_type, kws in TYPE_KEYWORDS:
        for kw in kws:
            if keyword_matches(text, kw):
                # multi-word/domain-specific hits are slightly stronger
                scores[dev_type] += 2 if " " in kw or len(kw) >= 8 else 1
    if scores:
        return scores.most_common(1)[0][0]
    return "Others"


def keyword_matches(text: str, keyword: str) -> bool:
    """Match taxonomy keywords without accidental short-token substrings.

    For example, ``ai`` should match the standalone token "AI", not the "ai"
    inside "failure"; ``bot`` should not make "greenrobot/EventBus" a chatbot.
    Multi-word phrases remain substring matches because descriptions are short
    and already normalized.
    """
    kw = keyword.lower()
    if " " in kw or len(kw) >= 5:
        return kw in text
    return re.search(rf"(?<![a-z0-9]){re.escape(kw)}(?![a-z0-9])", text) is not None


def candidate_repo_paths(workspace: str, roots: list[str]) -> list[Path]:
    owner_repo = workspace.replace("__", os.sep)
    repo_name = workspace.split("__")[-1]
    out = []
    for root in roots:
        r = Path(root)
        out.extend([
            r / owner_repo,
            r / workspace,
            r / repo_name,
        ])
    # stable de-dup
    seen, uniq = set(), []
    for p in out:
        s = str(p)
        if s not in seen:
            seen.add(s)
            uniq.append(p)
    return uniq


def find_repo_path(workspace: str, roots: list[str]) -> Path | None:
    for p in candidate_repo_paths(workspace, roots):
        if p.exists() and p.is_dir():
            return p
    return None


def is_probably_text_file(path: Path) -> bool:
    if path.suffix.lower() in TEXT_EXTS:
        return True
    if path.name in {"Makefile", "Dockerfile", "Gemfile", "Rakefile", "CMakeLists.txt"}:
        return True
    return False


def scan_repo_size(path: Path | None, max_file_bytes: int = 1_000_000) -> tuple[int, int]:
    if path is None:
        return 0, 0
    file_count = 0
    loc = 0
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not d.startswith(".")]
        for name in files:
            fp = Path(root) / name
            if not is_probably_text_file(fp):
                continue
            try:
                if fp.stat().st_size > max_file_bytes:
                    continue
                file_count += 1
                with open(fp, "rb") as f:
                    loc += sum(1 for _ in f)
            except OSError:
                continue
    return file_count, loc


def quantile_bins(values: list[int]) -> list[str]:
    """Assign low/mid/high bins with near-equal counts."""
    n = len(values)
    order = sorted(range(n), key=lambda i: (values[i], i))
    bins = ["mid"] * n
    for rank, i in enumerate(order):
        if rank < n / 3:
            bins[i] = "low"
        elif rank < 2 * n / 3:
            bins[i] = "mid"
        else:
            bins[i] = "high"
    return bins


def build_candidates(records: list[dict[str, Any]], languages: list[str], per_language: int, repo_roots: list[str]) -> list[Candidate]:
    grouped: dict[str, list[tuple[int, dict[str, Any]]]] = defaultdict(list)
    for idx, repo in enumerate(records):
        lang = repo_language(repo)
        if lang in languages:
            grouped[lang].append((idx, repo))

    candidates: list[Candidate] = []
    for lang in languages:
        selected = grouped.get(lang, [])[:per_language]
        if len(selected) < per_language:
            raise ValueError(f"Language {lang!r} has only {len(selected)} candidates, need {per_language}")
        for idx, repo in selected:
            workspace = repo["workspace"]
            local_path = find_repo_path(workspace, repo_roots)
            file_count, loc = scan_repo_size(local_path)
            # Fallback if repos have not been cloned locally: use stars as a weak size proxy.
            if file_count == 0 and loc == 0:
                stars = int((repo.get("metadata") or {}).get("stars") or 0)
                file_count = max(1, int(math.sqrt(max(stars, 1))))
                loc = file_count * 100
            candidates.append(Candidate(
                idx=idx,
                repo=repo,
                language=lang,
                workspace=workspace,
                dev_type=classify_dev_type(repo),
                file_count=file_count,
                loc=loc,
            ))

    file_bins = quantile_bins([c.file_count for c in candidates])
    loc_bins = quantile_bins([c.loc for c in candidates])
    return [
        Candidate(**{**c.__dict__, "file_bin": fb, "loc_bin": lb})
        for c, fb, lb in zip(candidates, file_bins, loc_bins)
    ]


def count_attr(items: list[Candidate], attr: str) -> Counter[str]:
    return Counter(getattr(x, attr) for x in items)


def imbalance(counts: Counter[str], labels: list[str], total: int, weight: float = 1.0) -> float:
    target = total / len(labels)
    return weight * sum(abs(counts.get(label, 0) - target) for label in labels)


def selection_score(items: list[Candidate]) -> float:
    total = len(items)
    type_counts = count_attr(items, "dev_type")
    file_counts = count_attr(items, "file_bin")
    loc_counts = count_attr(items, "loc_bin")

    # Primary goal: balanced development types. Secondary: balanced file and LOC bins.
    score = 3.0 * imbalance(type_counts, DEV_TYPES, total)
    score += 1.0 * imbalance(file_counts, ["low", "mid", "high"], total)
    score += 1.0 * imbalance(loc_counts, ["low", "mid", "high"], total)

    # Encourage per-language diversity so one language does not contribute five repos of one type/size.
    for lang in sorted({x.language for x in items}):
        xs = [x for x in items if x.language == lang]
        score += 0.8 * max(0, len(xs) - len(set(x.dev_type for x in xs)))
        score += 0.3 * max(0, len(xs) - len(set(x.file_bin for x in xs)))
        score += 0.3 * max(0, len(xs) - len(set(x.loc_bin for x in xs)))
    return score


def select_balanced(candidates: list[Candidate], languages: list[str], k: int, beam_size: int) -> list[Candidate]:
    by_lang: dict[str, list[Candidate]] = {lang: [c for c in candidates if c.language == lang] for lang in languages}
    combo_by_lang: dict[str, list[tuple[float, tuple[Candidate, ...]]]] = {}
    for lang, xs in by_lang.items():
        if len(xs) < k:
            raise ValueError(f"Language {lang!r} has only {len(xs)} candidates, cannot select {k}")
        combos = [(selection_score(list(combo)), combo) for combo in itertools.combinations(xs, k)]
        combos.sort(key=lambda x: x[0])
        combo_by_lang[lang] = combos

    beam: list[tuple[float, tuple[Candidate, ...]]] = [(0.0, tuple())]
    for lang in languages:
        next_beam: list[tuple[float, tuple[Candidate, ...]]] = []
        for _, partial in beam:
            for _, combo in combo_by_lang[lang]:
                merged = partial + combo
                next_beam.append((selection_score(list(merged)), merged))
        next_beam.sort(key=lambda x: x[0])
        beam = next_beam[:beam_size]
    return list(beam[0][1])


def enrich_repo(candidate: Candidate, rank: int) -> dict[str, Any]:
    repo = json.loads(json.dumps(candidate.repo, ensure_ascii=False))
    md = repo.setdefault("metadata", {})
    md["filter_repos"] = {
        "selected": True,
        "selection_rank": rank,
        "dev_type": candidate.dev_type,
        "file_count": candidate.file_count,
        "loc": candidate.loc,
        "file_count_bin": candidate.file_bin,
        "loc_bin": candidate.loc_bin,
    }
    return repo


def write_report(path: str, candidates: list[Candidate], selected: list[Candidate]) -> None:
    selected_ids = {c.workspace for c in selected}
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=[
            "selected", "language", "workspace", "dev_type", "file_count", "loc",
            "file_count_bin", "loc_bin", "stars", "description",
        ])
        w.writeheader()
        for c in sorted(candidates, key=lambda x: (x.language, x.workspace)):
            md = c.repo.get("metadata") or {}
            w.writerow({
                "selected": "yes" if c.workspace in selected_ids else "no",
                "language": c.language,
                "workspace": c.workspace,
                "dev_type": c.dev_type,
                "file_count": c.file_count,
                "loc": c.loc,
                "file_count_bin": c.file_bin,
                "loc_bin": c.loc_bin,
                "stars": md.get("stars", ""),
                "description": md.get("description", ""),
            })


def print_summary(title: str, items: list[Candidate]) -> None:
    print(f"\n{title}: n={len(items)}")
    for attr, labels in [
        ("language", sorted({x.language for x in items})),
        ("dev_type", DEV_TYPES),
        ("file_bin", ["low", "mid", "high"]),
        ("loc_bin", ["low", "mid", "high"]),
    ]:
        c = count_attr(items, attr)
        print(f"  {attr}: " + ", ".join(f"{k}={c.get(k,0)}" for k in labels if c.get(k, 0)))
    print("  repos:")
    for x in sorted(items, key=lambda r: (r.language, r.workspace)):
        print(f"    - {x.language:10s} {x.workspace:35s} {x.dev_type:20s} files={x.file_count:5d} loc={x.loc:8d} bins=({x.file_bin},{x.loc_bin})")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Select balanced repos by language, development type, file count, and LOC.")
    p.add_argument("--input", default="repos_dataset.json", help="Input repos dataset JSON")
    p.add_argument("--output", default="data/repos-selected-4lang-5each.json", help="Output selected repos dataset JSON")
    p.add_argument("--report", default="", help="CSV report path; default is <output>.csv")
    p.add_argument("--languages", nargs="+", default=DEFAULT_LANGUAGES, help="Languages to include")
    p.add_argument("--candidates-per-language", type=int, default=10, help="Use first N repos per language as candidates")
    p.add_argument("--select-per-language", type=int, default=5, help="Select K repos per language")
    p.add_argument("--repo-roots", nargs="+", default=["data/repos/workspaces", ".repo_cache"], help="Local clone roots used for file/LOC scanning")
    p.add_argument("--beam-size", type=int, default=5000, help="Beam size for cross-language balanced search")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    raw, records = load_dataset(args.input)
    languages = [x.lower() for x in args.languages]
    candidates = build_candidates(records, languages, args.candidates_per_language, args.repo_roots)
    selected = select_balanced(candidates, languages, args.select_per_language, args.beam_size)
    selected_set = {c.workspace for c in selected}

    # Preserve input order so dataset_gen.main still takes the intended first K per language.
    selected_by_workspace = {c.workspace: c for c in selected}
    output_records = [
        enrich_repo(selected_by_workspace[c.workspace], rank=i + 1)
        for i, c in enumerate(candidates)
        if c.workspace in selected_set
    ]

    metadata = dict(raw.get("metadata") or {})
    metadata["filter_repos"] = {
        "input": args.input,
        "languages": languages,
        "candidates_per_language": args.candidates_per_language,
        "select_per_language": args.select_per_language,
        "total_candidates": len(candidates),
        "total_selected": len(output_records),
        "dev_types": DEV_TYPES,
        "objective": "balance development type + file_count terciles + LOC terciles, with per-language diversity penalty",
        "score": selection_score(selected),
    }
    out = {"metadata": metadata, "data": output_records}
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

    report = args.report or str(Path(args.output).with_suffix(".csv"))
    Path(report).parent.mkdir(parents=True, exist_ok=True)
    write_report(report, candidates, selected)

    print_summary("Selected repos", selected)
    print(f"\nWrote selected dataset: {args.output}")
    print(f"Wrote candidate report:  {report}")
    print("\nUse with dataset_gen.main, for example:")
    print(f"  python -m dataset_gen.main --repos-dataset {args.output} --sample-n-repos {args.select_per_language} --languages {' '.join(languages)} --skill-modes no_skills_no_rules")


if __name__ == "__main__":
    main()
