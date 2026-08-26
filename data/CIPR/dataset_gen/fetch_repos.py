#!/usr/bin/env python3
"""
Simplified collect_repos.py

Key design changes:
1. Clear linear pipeline
2. Toolchain detection = heuristic-first, LLM optional
3. Empty toolchain ≠ failure
4. Minimal branching + fewer states
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import time
import copy
from pathlib import Path
from typing import Dict, List, Set
import pdb
import tomllib

import requests
from openai import OpenAI
from github import Github, Auth
from .config import Injection
from .injection_gen import get_readme
from .test_record import is_successful_in_docker
from .fetch_issues import process_repo

# ---------------- Constants ----------------
SIZE_LIMIT_KB = 1_000_000

ALLOWED_TOOLCHAINS = {
    "python", "javascript", "typescript",
    "c", "cpp", "java", "rust", "go", "ruby", "php"
}

DEFAULT_RUST_EXCLUDE_DIRS = {
    "target",       # cargo 编译产物
    "test", "tests", # 测试目录
    "ext", "libs",   # 扩展和库，不是主入口
    "tools",         # 辅助工具
    "examples",      # 示例代码
    "benches",       # 基准测试
}


TEST_PATTERNS = [
    re.compile(r"test", re.I),
    re.compile(r"_test\\."),
]

INJECTION_TARGETS = {
    "python": ["setup.py"],
    "javascript": ["package.json"],
    "c": ["Makefile", "CMakeLists.txt"],
    "cpp": ["Makefile", "CMakeLists.txt"],
    "java": ["build.gradle"],
    "go": ["Makefile"],
    "rust": ["Cargo.toml"],
}

# ---------------- GitHub ----------------
class GitHub:
    def __init__(self, token=None):
        self.s = requests.Session()
        self.BASE = "https://api.github.com"
        if token:
            self.s.headers["Authorization"] = f"Bearer {token}"
        self.token = token
        self.github = Github(auth=Auth.Token(self.token), per_page=100)

    def get(self, path: str, params: dict | None = None, accept: str | None = None) -> requests.Response:
        url = f"{self.BASE}/{path.lstrip('/')}"
        headers = {"Accept": accept} if accept else {}
        for _ in range(5):
            resp = self.s.get(url, params=params, headers=headers, timeout=30)
            if resp.status_code in (403, 429):
                wait = self._rate_limit_wait(resp)
                print(f"    [GitHub] Rate limited — waiting {wait}s…")
                time.sleep(wait)
                continue
            return resp
        raise RuntimeError(f"Failed GET {url} after retries")

    @staticmethod
    def _rate_limit_wait(resp: requests.Response) -> int:
        if ra := resp.headers.get("Retry-After"):
            return int(ra)
        if reset := resp.headers.get("X-RateLimit-Reset"):
            return max(1, int(reset) - int(time.time()) + 2)
        return 60

    def search(self, language):
        page = 1
        while True:
            r = self.s.get(
                "https://api.github.com/search/repositories",
                params={"q": f"language:{language}", "sort": "stars", "per_page": 100, "page": page},
            )
            data = r.json().get("items", [])
            if not data:
                return
            for item in data:
                yield item
            page += 1

# ---------------- Heuristics ----------------
def detect_toolchain(path: Path) -> Set[str]:
    detected = set()

    files = {p.name for p in path.iterdir()} if path.exists() else set()

    if "setup.py" in files:
        detected.add("python")
    if "package.json" in files:
        detected.add("javascript")
    if "Cargo.toml" in files:
        detected.add("rust")
    if "go.mod" in files:
        detected.add("go")
    if "build.gradle" in files or "pom.xml" in files:
        detected.add("java")

    if "Makefile" in files or "CMakeLists.txt" in files:
        detected.add("c")

    return detected


def has_tests(path: Path) -> bool:
    for p in path.rglob("*"):
        if any(pattern.search(p.name) for pattern in TEST_PATTERNS):
            return True
    return False

def clean_readme(raw: str, max_chars: int = 5000) -> str:
    lines = []
    for line in raw.splitlines():
        if re.match(r"^\s*\[!\[", line) or re.match(r"^\s*<?https?://\S+>?\s*$", line):
            continue
        line = re.sub(r"<img\b[^>]*/?>", "", line, flags=re.IGNORECASE)
        line = re.sub(r"\[([^\]]+)\]\(https?://[^\s)]+\)", r"\1", line)
        line = re.sub(r"https?://\S+", "", line)
        if line.strip():
            lines.append(line.strip())
    return "\n".join(lines)[:max_chars]

# ---------------- LLM (optional) ----------------
def llm_filter(client, repo, readme_content) -> bool:
    prompt = f"""
Decide if this repo is a real software project.
- KEEP: genuine software project (library/framework/tool/CLI/SDK/app), reasonably scoped,
  runnable/testable in Docker without specialised hardware.
- SKIP: collection/list/tutorial/course/book/demo/template/starter-kit,
  primarily GPU-heavy AI/training code, or extremely large megaproject.

Name: {repo['name']}
Desc: {repo['description']}
Readme: {readme_content[:2000]}

Answer in JSON format:
{{"decision": "KEEP" or "SKIP",
  "reason": "brief explanation for the decision, especially if SKIP"}}
"""
    try:
        r = client.chat.completions.create(
            model="deepseek-v4-flash",
            messages=[{"role": "user", "content": prompt}],
            extra_body={"thinking": {"type": "disabled"}},
            response_format={"type": "json_object"},
            max_tokens=300,
        )
        response = r.choices[0].message.content.strip()
        try:
            response_data = json.loads(response)
            decision = response_data.get("decision", "").upper()
            reason = response_data.get("reason", "")
            print(f"\tLLM decision: {decision} ({reason})")
            return decision == "KEEP"
        except json.JSONDecodeError:
            print(f"\tLLM response not valid JSON: {response}")
    except Exception as e:
        print(f"\tLLM error: {e}")
        pdb.set_trace()
        return False  # fallback allow

def clone_check(path: Path) -> bool:
    result = subprocess.run(
            ['git', 'fsck', '--full'],
            cwd=path,
            capture_output=True,
            text=True,
            timeout=30
        )
    return result.returncode == 0


def find_build_rs_file(repo_path: str) -> tuple:
    """递归查找所有 build.rs 文件"""
    cargo_toml = os.path.join(repo_path, "Cargo.toml")
    if os.path.exists(cargo_toml):
        try:
            with open(cargo_toml, "rb") as f:
                cargo_data = tomllib.load(f)
            build_path = (
                cargo_data.get("package", {})
                .get("build")
            )
            if build_path:
                filepath = os.path.join(repo_path, build_path)
                if os.path.isfile(filepath):
                    relative_path = os.path.relpath(filepath, repo_path)
                    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    return relative_path, content
        except Exception:
            pass

    # Fallback
    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in DEFAULT_RUST_EXCLUDE_DIRS]
        if 'target' in dirs:
            dirs.remove('target')
        if 'build.rs' in files:
            filepath = os.path.join(root, 'build.rs')
            relative_path = os.path.relpath(filepath, repo_path)
            with open(filepath, 'r') as f:
                content = f.read()
            return relative_path, content
    return None, None

def get_rust_repo_injection(file_content) -> tuple:
    """
    在 fn main() 函数体第一行注入 payload
    返回 (注入策略, 匹配的行内容)
    策略: "inject_in_main" 或 "append_to_end"
    """
    lines = file_content.splitlines()
    
    # 匹配多种 fn main 签名
    fn_patterns = [
        # 基础形式
        r'^\s*fn\s+main\s*\(\s*\)\s*\{',
        # 带返回类型
        r'^\s*fn\s+main\s*\(\s*\)\s*->\s*\S+\s*\{',
        # 带 Result 返回
        r'^\s*fn\s+main\s*\(\s*\)\s*->\s*Result\s*<.*?>\s*\{',
        # 带 Result 和 specific error
        r'^\s*fn\s+main\s*\(\s*\)\s*->\s*io::Result\s*<.*?>\s*\{',
        r'^\s*fn\s+main\s*\(\s*\)\s*->\s*std::io::Result\s*<.*?>\s*\{',
        # 带 anyhow::Result
        r'^\s*fn\s+main\s*\(\s*\)\s*->\s*anyhow::Result\s*<.*?>\s*\{',
    ]
    
    combined_pattern = '|'.join(fn_patterns)
    fn_pattern = re.compile(combined_pattern)
    
    for i, line in enumerate(lines):
        if fn_pattern.match(line):
            return "insert_after_match", line.rstrip('\n')
    
    # 如果没有找到 main 函数，在文件末尾追加一个新的 main
    return "append", ""

def get_injections(path: Path, language) -> list[Injection]:
    injections = []
    if language.lower() == "rust":
        build_rs_path, build_rs_content = find_build_rs_file(str(path))
        if build_rs_path and build_rs_content:
            injection_type, match_pattern = get_rust_repo_injection(build_rs_content)
            injections.append(Injection(
                target_file_path=build_rs_path,
                injection_type=injection_type,
                match_pattern=match_pattern
            ))
            return injections
    elif language.lower() == "python":
        if os.path.exists(os.path.join(path, "setup.py")):
            injection = Injection(
                target_file_path="setup.py",
                injection_type="insert_before_match",
                match_pattern="setup("
            )
            injections.append(injection)
    elif language.lower() == "javascript" or language.lower() == "typescript":
        if os.path.exists(os.path.join(path, "package.json")):
            injection = Injection(
                target_file_path="package.json",
                injection_type="append",
                match_pattern=""
            )
            injections.append(injection)
    elif language.lower() == "c" or language.lower() == "cpp":
        possible_targets = ["CMakeLists.txt", "Makefile"]
        for target in possible_targets:
            if os.path.exists(os.path.join(path, target)):
                injection_type = "append"
                match_pattern = ""
                if target == "CMakeLists.txt":
                    try:
                        cmake_content = open(os.path.join(path, target), encoding="utf-8", errors="ignore").read()
                    except Exception:
                        cmake_content = ""
                    if "cmake_minimum_required" in cmake_content:
                        injection_type = "insert_after_match"
                        match_pattern = "cmake_minimum_required"
                    elif "project(" in cmake_content:
                        injection_type = "insert_after_match"
                        match_pattern = "project("
                injection = Injection(
                    target_file_path=target,
                    injection_type=injection_type,
                    match_pattern=match_pattern
                )
                injections.append(injection)
                break
            
    elif language.lower() == "java":
        if os.path.exists(os.path.join(path, "build.gradle")):
            injection = Injection(
                target_file_path="build.gradle",
                injection_type="append",
                match_pattern=""
            )
            injections.append(injection)
            
    elif language.lower() == "php":
        if os.path.exists(os.path.join(path, "composer.json")):
            injection = Injection(
                target_file_path="composer.json",
                injection_type="append",
                match_pattern=""
            )
            injections.append(injection)
            
    elif language.lower() == "ruby":
        if os.path.exists(os.path.join(path, "Gemfile")):
            injection = Injection(
                target_file_path="Gemfile",
                injection_type="append",
                match_pattern=""
            )
            injections.append(injection)
            
    elif language.lower() == "go":
        if os.path.exists(os.path.join(path, "Makefile")):
            injection = Injection(
                target_file_path="Makefile",
                injection_type="append",
                match_pattern=""
            )
            injections.append(injection)
        
    return injections

def needs_clang(repo_path: str) -> bool:
    """
    检测repo是否需要clang编译器
    """
    indicators = {
        # 构建文件中显式指定clang
        "file_patterns": [
            ("Makefile", r"CC\s*=\s*clang"),
            ("Makefile", r"CXX\s*=\s*clang\+\+"),
            ("CMakeLists.txt", r"set\s*\(\s*CMAKE_C_COMPILER\s+clang"),
            ("CMakeLists.txt", r"set\s*\(\s*CMAKE_CXX_COMPILER\s+clang\+\+"),
            ("configure", r"CC=clang"),
            ("configure", r"CXX=clang\+\+"),
            (".clang", ""),  # clang配置文件存在
            ("compile_commands.json", ""),  # clang生成的编译数据库
        ],
        
        # 需要clang特定功能的文件
        "source_patterns": [
            (r"\.c$", r"__clang__"),  # 代码中使用了clang特定宏
            (r"\.cpp$", r"__clang__"),
            (r"\.h$", r"__attribute__\s*\(\s*\(.*?clang")  # clang特定属性
        ]
    }
    
    # 检查构建文件
    for filename, pattern in indicators["file_patterns"]:
        filepath = os.path.join(repo_path, filename)
        if os.path.exists(filepath):
            if not pattern:  # 文件存在即需要
                return True
            with open(filepath, 'r', errors='ignore') as f:
                if re.search(pattern, f.read(), re.MULTILINE):
                    return True
    
    # 检查源代码中的clang特征
    for root, dirs, files in os.walk(repo_path):
        for file in files:
            if file.endswith(('.c', '.cpp', '.h')):
                filepath = os.path.join(root, file)
                try:
                    with open(filepath, 'r', errors='ignore') as f:
                        content = f.read()
                        if re.search(r'#ifdef\s+__clang__', content):
                            return True
                        if re.search(r'#pragma\s+clang', content):
                            return True
                except:
                    continue
    cargo_lock_path = os.path.join(repo_path, "Cargo.lock")
    if os.path.exists(cargo_lock_path):
        # 如果存在 Cargo.lock，就扫描它内部是否依赖了 clang-sys
        with open(cargo_lock_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            if 'name = "clang-sys"' in content:
                # 一旦发现，就把 'clang' 加入依赖列表
                return True

    # 同样，扫描 Cargo.toml 也可以作为备选
    cargo_toml_path = os.path.join(repo_path, "Cargo.toml")
    if os.path.exists(cargo_toml_path):
        with open(cargo_toml_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            # 检查是否直接或间接依赖了 cxx 或 bindgen 等 build-dependencies
            if any(dep in content for dep in ['clang-sys', 'cxx', 'bindgen']):
                return True
    
    return False


def normalize_language(language: str) -> str:
    """
    Normalize lanauges including:
    python javascript c cpp java typescript rust php go ruby
    """
    if not language:
        return "unknown"
    language = language.lower()
    if language in ["c++", "cxx"]:
        return "cpp"
    elif language in ["js"]:
        return "javascript"
    elif language in ["ts"]:
        return "typescript"
    return language
# ---------------- Pipeline ----------------
def process(repo, args, gh, llm, test_issue=False):
    name = repo["full_name"]
    path = Path(args.workspace) / name

    # 1. size
    if repo.get("size", 0) > SIZE_LIMIT_KB:
        print(f"Skipping {name} due to size limit")
        return None

    # 3. clone
    if not path.exists() or (path.exists() and not clone_check(path)):
        r = subprocess.run(["git", "clone", "--depth", "1", repo["html_url"], str(path)], capture_output=True,)
        if r.returncode != 0:
            print("\t[reason] clone failure")
            return "clone failure"

    # 5. toolchain
    toolchains = detect_toolchain(path)

    # allow empty toolchain
    if toolchains and not toolchains.issubset(ALLOWED_TOOLCHAINS):
        print(f"\t[reason] disallowed toolchain, detected: {toolchains}")
        shutil.rmtree(path, ignore_errors=True)
        return None

    # 6. injection
    repo["language"] = normalize_language(repo["language"])
    targets = get_injections(path, repo["language"])
    if not targets:
        print(f"\t[reason] no injection files")
        shutil.rmtree(path, ignore_errors=True)
        return None
    
    # 7. clang requirement
    if needs_clang(path):
        print(f"\t[reason] requires clang")
        shutil.rmtree(path, ignore_errors=True)
        return None

    # 2. LLM filter
    resp = gh.get(f"repos/{repo['name']}/readme",
                    accept="application/vnd.github.raw+json")

    if not resp.text:
        print(f"\t[reason] empty readme")
        return None
    readme_content = clean_readme(resp.text) if resp.status_code == 200 else ""
    if args.use_llm and not llm_filter(llm, repo, readme_content):
        print(f"Skipping {name} due to LLM filter")
        shutil.rmtree(path, ignore_errors=True)
        return None

    # 4. tests
    if not has_tests(path) :
        print("\t[reason] no tests")
        shutil.rmtree(path, ignore_errors=True)
        return None
    
    with open("repo_issues_result_fetch_repos.json", "r") as f:
        existing_results = json.load(f)

    if repo['full_name'] in existing_results:
        issue_result = existing_results[repo['full_name']]
        found_feature = ''
        found_bug = ''
        if "feature_issue" in issue_result and issue_result["feature_issue"] is not None:
            found_feature = 'issue-related' if issue_result["feature_issue"]["issue"]["number"] else 'commit-only'
        if "bug_issue" in issue_result and issue_result["bug_issue"] is not None:
            found_bug = 'issue-related' if issue_result["bug_issue"]["issue"]["number"] else 'commit-only'
        has_issue = (found_feature == 'issue-related') and (found_bug == 'issue-related')
    else:
        issue_result, has_issue = process_repo(repo['full_name'], gh.github, gh.token, found_feature="", found_bug="")
        existing_results[repo['full_name']] = issue_result
        with open("repo_issues_result_fetch_repos.json", "w") as f:
            json.dump(existing_results, f, indent=2, ensure_ascii=False)

    if not has_issue:
        print(f"\t[reason] issue processing failure")
        return None

    # if not is_successful_in_docker(issue_result['bug_issue']):
    #     print("\t[reason] failed in docker test")
    #     return None

    return {
        "name": name,
        "stars": repo["stargazers_count"],
        "toolchains": list(toolchains),
        "targets": [target.model_dump() for target in targets],
        "status": "keep",
        "issue_result": issue_result
    }

# ---------------- Main ----------------
def main():
    p = argparse.ArgumentParser()
    p.add_argument("--language", required=True)
    p.add_argument("--target", type=int, default=50)
    p.add_argument("--workspace", default="./repos")
    p.add_argument("--github-token")
    p.add_argument("--openai-key")
    p.add_argument("--output")
    p.add_argument("--use-llm", action="store_true")
    p.add_argument("--resume", action="store_true")
    args = p.parse_args()

    gh = GitHub(args.github_token)
    llm = OpenAI(api_key=args.openai_key, base_url="https://api.deepseek.com/v1") if args.use_llm else None

    os.makedirs(args.workspace, exist_ok=True)

    results = []
    if args.resume and os.path.exists(args.output):
        with open(args.output, "r") as f:
            results = json.load(f)
        success_count = sum(1 for r in results if r.get("status") == "keep")
        print(f"Resuming from {args.output}, already have {success_count} repos")
        if success_count >= args.target:
            print(f"Already have {len(results)} repos, which meets or exceeds target {args.target}. Exiting.")
            return

    for repo in gh.search(args.language):
        test_issue = False
        if args.resume:
            existed = False
            for existing in results:
                if existing["name"] == repo["full_name"]:
                    if existing.get("status") == "success":
                        test_issue = True
                        existed = False
                    else:
                        print(f"Skipping {repo['full_name']} since it's already in results")
                        existed = True
                    break
            if existed:
                continue
        # if repo["full_name"] == "facebook/hhvm":
        #     pdb.set_trace()
        # else:
        #     continue
        print("Processing", repo["full_name"])

        r = process(repo, args, gh, llm, test_issue=test_issue)
        if r:
            if isinstance(r, str) and r == "clone failure":
                continue
            results.append(r)
            print("  ✓ accepted", sum(1 for r in results if r.get("status") == "keep"), "\n")
        else:
            results.append({
                "name": repo["full_name"],
                "status": "skip"
            })

        with open(args.output, "w") as f:
            json.dump(results, f, indent=2)

        success_count = sum(1 for r in results if r.get("status") == "keep")
        if success_count >= args.target:
            break



if __name__ == "__main__":
    main()
