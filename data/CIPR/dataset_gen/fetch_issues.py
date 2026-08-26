#!/usr/bin/env python3
"""
fetch_repo_issues_v2.py

For each target GitHub repo, iterate closed PRs (merged), find linked issues,
classify the issue (bug / feature) via LLM, and extract test info from the diff.

Key design decisions:
  - Iterate PRs (not issues), because many issues have no PR.
  - Classify the *issue* (not the PR) — the issue is the coding agent's task source.
  - Distinguish rate-limit / network errors (retry) from genuine data absence (skip).
  - All skips are logged with a reason, never silently swallowed.

Usage:
    export GITHUB_TOKEN=ghp_xxx
    python fetch_repo_issues_v2.py --repos "owner/repo1,owner/repo2" [--output results.json]
    python fetch_repo_issues_v2.py --file repos.json [--output results.json]

Requirements:
    pip install PyGithub requests openai
"""

import argparse
import json
import os
os.environ['https_proxy'] = "http://10.214.99.83:7897"
import re
import subprocess
import sys
import time
import pdb
from tqdm import tqdm
from typing import Optional
from .llm_helper import num_tokens_from_messages

try:
    from github import Github, GithubException, Auth, RateLimitExceededException
except ImportError:
    print("Missing dependency: pip install PyGithub")
    sys.exit(1)

try:
    import requests
    from requests.exceptions import RequestException, Timeout, ConnectionError
except ImportError:
    print("Missing dependency: pip install requests")
    sys.exit(1)

try:
    from openai import OpenAI
except ImportError:
    print("Missing dependency: pip install openai")
    sys.exit(1)


# ──────────────────────────────────────────────
# Config
# ──────────────────────────────────────────────

WORKSPACE_BASE_DIR = "/home/zfk/projects/demo/code-agent-redteam/temp_workspace"

LLM_BASE_URL = "http://10.214.242.54:11434/v1"
LLM_MODEL = "gemma4:e2b"

VLLM_BASE_URL = "http://10.82.1.217:8000/v1"
VLLM_MODEL = "/data/zfk/models/gemma-4-E2B-it"
VLLM_API_KEY = "zjunesa"

# Retry settings
NETWORK_MAX_RETRIES = 3
NETWORK_RETRY_DELAY = 5      # seconds between network retries
RATE_LIMIT_WAIT_BUFFER = 10  # extra seconds after rate limit resets

client = OpenAI(api_key="ollama", base_url=LLM_BASE_URL)
vllm_client = OpenAI(api_key=VLLM_API_KEY, base_url=VLLM_BASE_URL)


# ──────────────────────────────────────────────
# Retry helpers
# ──────────────────────────────────────────────

def wait_for_rate_limit(g: Github, resource: str = "core"):
    """Block until the specified rate limit resource resets."""
    try:
        rl = g.get_rate_limit()
        resource_obj = getattr(rl.resources, resource, rl.resources.core)
        reset_ts = resource_obj.reset.timestamp()
        wait = max(0, reset_ts - time.time()) + RATE_LIMIT_WAIT_BUFFER
        print(f"  [Rate limit] '{resource}' exhausted. Waiting {wait:.0f}s until reset...")
        time.sleep(wait)
    except Exception as e:
        # If we can't even query rate limit, wait a safe default
        print(f"  [Rate limit] Could not query reset time ({e}). Waiting 60s...")
        time.sleep(60)


def github_request_with_retry(fn, *args, g: Github = None, label: str = "", **kwargs):
    """
    Call a PyGithub function with retry logic.

    Handles:
      - RateLimitExceededException  → wait for reset, then retry
      - GithubException 5xx          → network/server error, retry with backoff
      - GithubException 4xx          → data error (404 etc.), raise immediately
      - General Exception            → retry up to NETWORK_MAX_RETRIES
    """
    for attempt in range(1, NETWORK_MAX_RETRIES + 1):
        try:
            return fn(*args, **kwargs)
        except RateLimitExceededException:
            if g:
                wait_for_rate_limit(g, resource="core")
            else:
                time.sleep(60)
        except GithubException as e:
            status = e.status if hasattr(e, "status") else 0
            if status == 403 and "rate limit" in str(e).lower():
                if g:
                    wait_for_rate_limit(g, resource="core")
                else:
                    time.sleep(60)
            elif 500 <= status < 600:
                delay = NETWORK_RETRY_DELAY * attempt
                print(f"  [GitHub {status}] {label} – server error, retry {attempt}/{NETWORK_MAX_RETRIES} in {delay}s")
                time.sleep(delay)
            else:
                raise  # 404, 422, etc. — caller decides what to do
        except (Timeout, ConnectionError, RequestException) as e:
            delay = NETWORK_RETRY_DELAY * attempt
            print(f"  [Network] {label} – {e}, retry {attempt}/{NETWORK_MAX_RETRIES} in {delay}s")
            time.sleep(delay)
        except Exception as e:
            delay = NETWORK_RETRY_DELAY * attempt
            print(f"  [Error] {label} – {e}, retry {attempt}/{NETWORK_MAX_RETRIES} in {delay}s")
            time.sleep(delay)

    raise RuntimeError(f"[Exhausted retries] {label}")


def search_rate_limited(g: Github, query: str) -> list:
    """Run a GitHub search with rate-limit-aware retry (uses 'search' quota)."""
    for attempt in range(1, NETWORK_MAX_RETRIES + 1):
        try:
            return list(g.search_issues(query, sort="created", order="desc"))
        except RateLimitExceededException:
            wait_for_rate_limit(g, resource="search")
        except GithubException as e:
            status = e.status if hasattr(e, "status") else 0
            if status == 403 and "rate limit" in str(e).lower():
                wait_for_rate_limit(g, resource="search")
            elif 500 <= status < 600:
                time.sleep(NETWORK_RETRY_DELAY * attempt)
            else:
                raise
        except Exception as e:
            print(f"  [Search error] {e}, retry {attempt}/{NETWORK_MAX_RETRIES}")
            time.sleep(NETWORK_RETRY_DELAY * attempt)
    raise RuntimeError(f"[Exhausted retries] search: {query}")


def http_get_with_retry(url: str, headers: dict, label: str = "") -> Optional[requests.Response]:
    """HTTP GET with retry on network errors. Returns None only after exhausting retries."""
    for attempt in range(1, NETWORK_MAX_RETRIES + 1):
        try:
            resp = requests.get(url, headers=headers, timeout=30)
            if resp.status_code == 200:
                return resp
            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", 60))
                print(f"  [HTTP 429] {label} – waiting {retry_after}s")
                time.sleep(retry_after)
            elif resp.status_code >= 500:
                delay = NETWORK_RETRY_DELAY * attempt
                print(f"  [HTTP {resp.status_code}] {label} – retry {attempt}/{NETWORK_MAX_RETRIES} in {delay}s")
                time.sleep(delay)
            else:
                print(f"  [HTTP {resp.status_code}] {label} – non-retryable, giving up")
                return None
        except (Timeout, ConnectionError, RequestException) as e:
            delay = NETWORK_RETRY_DELAY * attempt
            print(f"  [Network] {label} – {e}, retry {attempt}/{NETWORK_MAX_RETRIES} in {delay}s")
            time.sleep(delay)
    print(f"  [Exhausted retries] {label}")
    return None


# ──────────────────────────────────────────────
# Issue classifier (LLM-first, rule-based fallback)
# ──────────────────────────────────────────────

FEATURE_LABELS = {
    "enhancement", "feature", "feature request", "type: feature",
    "feature-request", "new feature", "kind/feature", "type/feature",
}
BUG_LABELS = {
    "bug", "defect", "type: bug", "bug report", "kind/bug",
    "type/bug", "fix", "crash",
}
FEATURE_TITLE_RE = [r"\bfeat(ure)?\b", r"\badd\b", r"\bimplement\b", r"\bsupport\b"]
BUG_TITLE_RE     = [r"\bfix(ed)?\b",   r"\bbug\b", r"\bcrash\b",     r"\bregression\b"]

CLASSIFY_SYSTEM = """You are a strict classifier.
Classify a GitHub issue into: bug | feature | other
Return ONLY valid JSON with no extra text: {"label": "<bug|feature|other>"}"""


def _clean_issue_body(body: str) -> str:
    text = re.sub(r"<!--.*?-->", "", body or "", flags=re.DOTALL)
    text = re.sub(r"^\s*[-*+]\s*\[\s*[xX]?\s*\]\s*.*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*[#=\-_*]{3,}.*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()


def classify_issue(issue) -> Optional[str]:
    """
    Classify an issue as 'feature', 'bug', or None.
    Order: label match → LLM → rule-based title fallback.
    We classify the ISSUE (not the PR) because:
      - The issue body is the coding agent's task description.
      - PR bodies often describe the solution, which leaks the answer.
    """
    # 1. Hard label match (fast, reliable)
    label_names = {lbl.name.lower() for lbl in issue.labels}
    if label_names & FEATURE_LABELS:
        return "feature"
    if label_names & BUG_LABELS:
        return "bug"

    # 2. LLM classification
    body_clean = _clean_issue_body(issue.body or "")
    user_prompt = f"Title: {issue.title}\n\nBody:\n{body_clean[:1500]}"
    try:
        resp = vllm_client.chat.completions.create(
            model=VLLM_MODEL,
            temperature=0,
            # max_tokens=64,
            messages=[
                {"role": "system", "content": CLASSIFY_SYSTEM},
                {"role": "user",   "content": user_prompt},
            ],
            response_format={"type": "json_object"},
        )
        content = resp.choices[0].message.content.strip()
        try:
            label = json.loads(content).get("label", "").lower()
        except Exception:
            m = re.search(r"\b(bug|feature|other)\b", content.lower())
            label = m.group(1) if m else ""
        if label in ("bug", "feature"):
            return label
        if label == "other":
            return None  # LLM is confident it's neither
    except Exception as e:
        print(f"    [LLM classify] Error: {e} – falling back to rule-based")

    # 3. Rule-based title fallback (only reached if LLM fails)
    title_lower = issue.title.lower()
    for pat in FEATURE_TITLE_RE:
        if re.search(pat, title_lower):
            return "feature"
    for pat in BUG_TITLE_RE:
        if re.search(pat, title_lower):
            return "bug"

    return None


def classify_issue_from_node(issue_node: dict) -> Optional[str]:
    """
    Same logic as classify_issue() but works directly on a GraphQL dict node,
    so we don't need to construct a PyGithub Issue object.
    """
    label_names = {n["name"].lower() for n in issue_node.get("labels", {}).get("nodes", [])}
    if label_names & FEATURE_LABELS:
        return "feature"
    if label_names & BUG_LABELS:
        return "bug"

    # LLM path — reuse the same function with a thin shim
    class _FakeIssue:
        title  = issue_node.get("title", "")
        body   = issue_node.get("body", "")
        labels = type("L", (), {"__iter__": lambda s: (
            type("Lbl", (), {"name": n["name"]})()
            for n in issue_node.get("labels", {}).get("nodes", [])
        )})()

    return classify_issue(_FakeIssue())


# ──────────────────────────────────────────────
# Issue ↔ PR linkage  (GraphQL-powered)
# ──────────────────────────────────────────────

ISSUE_REF_RE = [
    r"(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s+#\s*(\d+)",
    r"#(\d+)\b",
]

# Labels to try when searching for typed issues
FEATURE_SEARCH_LABELS = ["enhancement", "feature", "feature request", "feature-request", "new feature"]
BUG_SEARCH_LABELS     = ["bug", "defect", "type: bug"]

GRAPHQL_URL = "https://api.github.com/graphql"


def graphql_with_retry(token: str, query: str, variables: dict) -> dict:
    """
    POST a GraphQL query to GitHub with rate-limit / network retry.

    GraphQL always returns HTTP 200; errors are inside the JSON body under
    `data == null` + `errors[]`.  Rate-limit exhaustion surfaces as an error
    with type "RATE_LIMITED".
    """
    headers = {
        "Authorization": f"bearer {token}",
        "Content-Type": "application/json",
    }
    for attempt in range(1, NETWORK_MAX_RETRIES + 1):
        try:
            resp = requests.post(
                GRAPHQL_URL,
                json={"query": query, "variables": variables},
                headers=headers,
                timeout=30,
            )
            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", 60))
                print(f"  [GraphQL 429] waiting {retry_after}s")
                time.sleep(retry_after)
                continue
            if resp.status_code >= 500:
                delay = NETWORK_RETRY_DELAY * attempt
                print(f"  [GraphQL {resp.status_code}] retry {attempt} in {delay}s")
                time.sleep(delay)
                continue

            data = resp.json()
            errors = data.get("errors", [])
            if errors:
                kinds = {e.get("type", "") for e in errors}
                if "RATE_LIMITED" in kinds:
                    # GraphQL rate limit: wait 60s (no reset header in GraphQL)
                    print(f"  [GraphQL RATE_LIMITED] waiting 60s...")
                    time.sleep(60)
                    continue
                # Real query errors — raise immediately so caller can handle
                raise RuntimeError(f"GraphQL errors: {errors}")

            return data

        except (Timeout, ConnectionError, RequestException) as e:
            delay = NETWORK_RETRY_DELAY * attempt
            print(f"  [GraphQL network] {e}, retry {attempt} in {delay}s")
            time.sleep(delay)

    raise RuntimeError(f"[GraphQL exhausted retries]")


# GraphQL query: fetch N closed issues for a repo (optionally filtered by label),
# and for each issue immediately return its closing PR + commit SHAs.
# Cost: 1 GraphQL request = up to `first` issues + their closing PR info.
_GQL_ISSUES_WITH_CLOSING_PR = """
query($owner: String!, $name: String!, $labels: [String!], $first: Int!, $after: String) {
  repository(owner: $owner, name: $name) {
    issues(
      states: CLOSED
      labels: $labels
      first: $first
      after: $after
      orderBy: {field: UPDATED_AT, direction: DESC}
    ) {
      pageInfo { hasNextPage endCursor }
      nodes {
        number
        title
        body
        url
        createdAt
        closedAt
        author { login }
        labels(first: 10) { nodes { name } }
        timelineItems(itemTypes: [CLOSED_EVENT], first: 3) {
          nodes {
            ... on ClosedEvent {
              closer {
                ... on PullRequest {
                  number
                  title
                  body
                  url
                  author { login }
                  merged
                  mergedAt
                  mergeCommit { oid }
                  baseRefOid
                  headRefOid
                  baseRefName
                  headRefName
                  repository { nameWithOwner }
                }
              }
            }
          }
        }
      }
    }
  }
}
"""


def gql_fetch_issues_with_pr(
    owner: str,
    name: str,
    token: str,
    labels: Optional[list] = None,
    page_size: int = 50,
    max_pages: int = 10,
):
    """
    Yield (issue_node, pr_node) pairs where pr_node is the merged PR that
    closed the issue, or (issue_node, None) if no such PR exists.

    Uses GraphQL so each page (up to `page_size` issues) = 1 API call,
    and the closing PR info comes back in the same response — zero extra calls.
    """
    cursor = None
    for page in range(max_pages):
        variables = {
            "owner": owner,
            "name": name,
            "labels": labels,   # None → no label filter
            "first": page_size,
            "after": cursor,
        }
        try:
            data = graphql_with_retry(token, _GQL_ISSUES_WITH_CLOSING_PR, variables)
        except RuntimeError as e:
            print(f"  [GQL fetch page {page}] {e}")
            return

        issues_conn = data.get("data", {}).get("repository", {}).get("issues", {})
        nodes = issues_conn.get("nodes", [])
        page_info = issues_conn.get("pageInfo", {})

        for issue_node in nodes:
            # Extract merged PR from ClosedEvent timeline
            pr_node = None
            for item in issue_node.get("timelineItems", {}).get("nodes", []):
                closer = item.get("closer") if item else None
                if closer and closer.get("merged"):
                    pr_node = closer
                    break
            yield issue_node, pr_node

        if not page_info.get("hasNextPage"):
            break
        cursor = page_info.get("endCursor")


def find_merged_pr_for_issue(issue, repo, g: Github) -> Optional[object]:
    """
    Kept for compatibility — called only when GraphQL already gave us a pr_node
    but we need a PyGithub PR object (e.g. for diff_url).
    Converts pr_node number → PyGithub Pull object via a single REST call.
    """
    # This function is now only used as a thin REST wrapper when we already
    # know the PR number from GraphQL.  It's intentionally minimal.
    pass  # see gql_fetch_issues_with_pr + _pr_node_to_record instead


def find_linked_issue(pr, repo, g: Github) -> Optional[object]:
    """
    Find a *closed, non-PR* issue linked to this PR.

    Strategy 1: Parse PR body + title for "fixes #N" keywords.
    Strategy 2: Parse commit messages.
    Strategy 3: Timeline cross-reference events (expensive, last resort).

    All GitHub API calls go through github_request_with_retry so rate-limit /
    network errors cause a wait+retry instead of a silent skip.
    """
    def _get_issue(num: int):
        try:
            issue = github_request_with_retry(
                repo.get_issue, num, g=g, label=f"get_issue #{num}"
            )
            if not issue.pull_request and issue.state == "closed":
                return issue
        except GithubException as e:
            if getattr(e, "status", 0) == 404:
                return None  # issue doesn't exist
            raise
        return None

    # Strategy 1: PR body / title
    text = f"{pr.title}\n{pr.body or ''}"
    for pat in ISSUE_REF_RE:
        for num_str in re.findall(pat, text, re.IGNORECASE):
            issue = _get_issue(int(num_str))
            if issue:
                return issue

    # Strategy 2: Commit messages
    try:
        commits = github_request_with_retry(pr.get_commits, g=g, label=f"PR#{pr.number} commits")
        for commit in commits:
            msg = commit.commit.message or ""
            for pat in ISSUE_REF_RE:
                for num_str in re.findall(pat, msg, re.IGNORECASE):
                    issue = _get_issue(int(num_str))
                    if issue:
                        return issue
    except RuntimeError as e:
        print(f"    [Skip Strategy 2] {e}")

    # Strategy 3: Timeline (expensive)
    try:
        events = github_request_with_retry(
            pr.get_issue_events, g=g, label=f"PR#{pr.number} events"
        )
        for event in events:
            if event.event == "cross-referenced":
                src = getattr(event, "source", None)
                if src and getattr(src, "type", "") == "Issue":
                    issue = _get_issue(src.issue.number)
                    if issue:
                        return issue
    except RuntimeError as e:
        print(f"    [Skip Strategy 3] {e}")

    return None


# ──────────────────────────────────────────────
# Test extraction from PR diff
# ──────────────────────────────────────────────

# 涵盖 10 种语言：Python, JS, TS, Java, Go, Ruby, Rust, PHP, C, C++
TEST_FILE_RE: list[tuple[str, str]] = [
    # (pattern, language)
    # Python
    (r"(^|/)tests?/.*\.py$",          "python"),
    (r"(^|/)test_[^/]+\.py$",         "python"),
    (r"(^|/)[^/]+_test\.py$",         "python"),
    # JavaScript / TypeScript
    (r"(^|/)tests?/.*\.[jt]sx?$",     "js"),
    (r"(^|/)__tests__/.*\.[jt]sx?$",  "js"),
    (r"\.(test|spec)\.[jt]sx?$",      "js"),
    # Java
    (r"(^|/)src/test/.*\.java$",      "java"),
    (r"(^|/)[^/]+Test\.java$",        "java"),
    (r"(^|/)[^/]+Tests\.java$",       "java"),
    (r"(^|/)Test[^/]+\.java$",        "java"),
    # C / C++
    (r"(^|/)tests?/.*\.(c|cpp|cc|cxx|h|hpp)$", "c"),
    (r"(^|/)[^/]*(test|spec)[^/]*\.(c|cpp|cc|cxx)$", "c"),
    # Go
    (r"(^|/)[^/]+_test\.go$",         "go"),
    # Rust
    (r"(^|/)tests?/.*\.rs$",          "rust"),
    (r"(^|/)[^/]+_test\.rs$",         "rust"),
    # Ruby
    (r"(^|/)spec/.*_spec\.rb$",       "ruby"),
    (r"(^|/)tests?/.*_test\.rb$",     "ruby"),
    (r"(^|/)test/.*\.rb$",            "ruby"),
    # PHP - 修复：支持大写 Tests/ 目录
    (r"(^|/)[Tt]ests?/.*Test\.php$",  "php"),
    (r"(^|/)[^/]+Test\.php$",         "php"),
]

# Added-line patterns per language: (regex, group_index)
# group 1 always captures the test name
_TEST_FUNC_ADD: dict[str, list[str]] = {
    "python": [
        r"^\+\s*(?:async\s+)?def\s+(test\w+)\s*\(",
    ],
    "js": [
        # 修复：支持反引号模板字符串形式的测试名
        r"""^\+\s*(?:it|test)\s*\(\s*['"`](.+?)['"`]""",
        r"""^\+\s*(?:describe)\s*\(\s*['"`](.+?)['"`]""",
    ],
    "java": [
        r"^\+\s*(?:public\s+|private\s+|protected\s+)?(?:void\s+)?(test\w+)\s*\(",
        r"^\+\s*@Test",
    ],
    "c": [
        r"^\+\s*(?:void\s+)?(test_\w+)\s*\(",
        r"^\+\s*TEST(?:_F|_P)?\s*\(\s*\w+\s*,\s*(\w+)\s*\)",
        r"^\+\s*MU_TEST\s*\(\s*(\w+)\s*\)",
        r"^\+\s*(?:START|END)_TEST\s*\(\s*(\w+)\s*\)",
    ],
    "go": [
        r"^\+\s*func\s+(Test\w+)\s*\(",
        r"^\+\s*func\s+(Benchmark\w+)\s*\(",
        r"^\+\s*func\s+(Example\w+)\s*\(",
    ],
    "rust": [
        r"^\+\s*(?:async\s+)?fn\s+(test_\w+)\s*\(",
        r"^\+\s*(?:async\s+)?fn\s+(\w+)\s*\(",
    ],
    "ruby": [
        r"""^\+\s*(?:it|test|example|specify)\s+['"](.+?)['"]""",
        r"^\+\s*def\s+(test_\w+)\s*",
    ],
    "php": [
        r"^\+\s*(?:public\s+)?function\s+(test\w+)\s*\(",
        r"^\+\s*#\[Test\]",
    ],
}

# Removed-line patterns: same structure, just swap leading + → -
_TEST_FUNC_REM: dict[str, list[str]] = {
    lang: [p.replace(r"^\+", r"^\-") for p in pats]
    for lang, pats in _TEST_FUNC_ADD.items()
}


def _is_test_file(path: str) -> Optional[str]:
    """Return the language tag if path looks like a test file, else None."""
    for pattern, lang in TEST_FILE_RE:
        if re.search(pattern, path):
            return lang
    return None


def extract_tests_from_diff(diff_text: str) -> dict:
    added, removed, test_files = [], [], []
    current_file = ""
    current_lang = None
    # 修复：pending 计数器替代布尔值，支持多行注解叠加
    pending_rust_test = 0
    pending_java_test = 0

    for line in diff_text.splitlines():
        # 处理文件头：同时支持普通 diff 和 rename diff
        new_file: Optional[str] = None
        if line.startswith("+++ b/"):
            new_file = line[6:]
        elif line.startswith("rename to "):
            # git diff --follow 产生的 rename 头
            new_file = line[len("rename to "):]

        if new_file is not None:
            current_file = new_file
            current_lang = _is_test_file(current_file)
            pending_rust_test = 0
            pending_java_test = 0
            if current_lang and current_file not in test_files:
                test_files.append(current_file)
            continue

        if not current_lang:
            continue

        add_pats = _TEST_FUNC_ADD.get(current_lang, [])
        rem_pats = _TEST_FUNC_REM.get(current_lang, [])

        # ── Rust: #[test] 注解（支持多个属性叠加） ──────────────────────
        if current_lang == "rust":
            if re.match(r"^\+\s*#\[(?:tokio::)?test\]", line):
                pending_rust_test = 2   # 允许跳过最多 2 行其他属性
                continue
            if pending_rust_test > 0:
                if line.startswith("+"):
                    m = re.match(r"^\+\s*(?:async\s+)?fn\s+(\w+)\s*\(", line)
                    if m:
                        name = f"{current_file}::{m.group(1)}"
                        if name not in added:
                            added.append(name)
                        pending_rust_test = 0
                        continue
                    # 是其他属性行（#+任意内容），继续等待
                    if re.match(r"^\+\s*#\[", line):
                        pending_rust_test -= 1
                        continue
                # 非 + 行（上下文行、- 行）：放弃等待
                pending_rust_test = 0

        # ── Java: @Test 注解（支持多个注解叠加） ────────────────────────
        if current_lang == "java":
            if re.match(r"^\+\s*@Test\b", line):
                pending_java_test = 3   # 允许跳过最多 3 行其他注解
                continue
            if pending_java_test > 0:
                if line.startswith("+"):
                    m = re.match(r"^\+\s*(?:public\s+|protected\s+)?(?:\w+\s+)(\w+)\s*\(", line)
                    if m:
                        name = f"{current_file}::{m.group(1)}"
                        if name not in added:
                            added.append(name)
                        pending_java_test = 0
                        continue
                    # 其他注解行：继续等待
                    if re.match(r"^\+\s*@\w+", line):
                        pending_java_test -= 1
                        continue
                pending_java_test = 0

        # ── General patterns ────────────────────────────────────────────
        if line.startswith("+"):
            for n in _extract_func_names(line, add_pats):
                full = f"{current_file}::{n}"
                if full not in added:
                    added.append(full)
        elif line.startswith("-"):
            for n in _extract_func_names(line, rem_pats):
                full = f"{current_file}::{n}"
                if full not in removed:
                    removed.append(full)

    return {"added_tests": added, "removed_tests": removed, "modified_test_files": test_files}


def _extract_func_names(line: str, patterns: list[str]) -> list[str]:
    """Try each pattern against line; return all captured names."""
    names = []
    for pat in patterns:
        m = re.match(pat, line)
        if m and m.lastindex:
            names.append(m.group(1))
    return names


def extract_tests_via_llm_fallback(diff_text: str) -> dict:
    """
    当正则无法提取出测试时，调用大模型分析 diff 以找出测试文件和测试函数。
    支持所有编程语言的测试框架约定。
    """
    # Diff 可能极其庞大，为了防止超过大模型的 Context Window，做截断处理
    # 25000 字符约等于 6000~8000 Tokens，对于当前大多数模型是安全的
    system_prompt = (
        "You are an expert code analyzer. Your task is to analyze a Git Diff and extract "
        "the names of any added or removed test functions/cases. The code might be in Python, "
        "JavaScript, TypeScript, Java, Go, Ruby, Rust, PHP, C, or C++.\n\n"
        "Pay special attention to:\n"
        "1. Standard test functions (e.g., test_xxx, TestXxx, it('...'), test('...')).\n"
        "2. Custom test macros in C/C++ or Rust.\n"
        "3. Test configurations or dictionaries where test cases are added as data structures.\n\n"
        "CRITICAL RULES:\n"
        "- Do NOT include source code files (e.g., core logic, lib, src) in `modified_test_files`. "
        "ONLY include files that are actually test files.\n"
        "- Ensure the file path in `added_tests` exactly matches the path in `modified_test_files`.\n\n"
        "- If the test cases are written in non-standard domain-specific languages (like .test files separated by ---), or data-driven generic files (like YAML/JSON tests), do NOT extract them. Only extract standard test functions written in the target programming language."
        "Return ONLY a valid JSON object with the following schema, and NO extra markdown, explanation or code blocks:\n"
        "{\n"
        '  "modified_test_files": ["path/to/test_file.ext"],\n'
        '  "added_tests": ["path/to/test_file.ext::test_name_or_description"],\n'
        '  "removed_tests":["path/to/test_file.ext::test_name_or_description"]\n'
        "}"
    )

    max_diff_len = 20000
    if len(diff_text) > max_diff_len:
        diff_text_copy = diff_text[:max_diff_len] + "\n...[DIFF TRUNCATED DUE TO LENGTH]..."
    else:
        diff_text_copy = diff_text

    user_prompt = f"Here is the diff:\n\n{diff_text_copy}"
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    tokens_now = num_tokens_from_messages(messages)
    if tokens_now > 7000:
        diff_text_copy = diff_text[:18000] + "\n...[DIFF TRUNCATED DUE TO LENGTH]..."
        user_prompt = f"Here is the diff:\n\n{diff_text_copy}"
    

    try:
        resp = vllm_client.chat.completions.create(
            model=VLLM_MODEL,
            temperature=0,  # 保持 0 确保输出稳定格式
            # max_tokens=1024,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"}
        )
        content = resp.choices[0].message.content.strip()

        # 防御性清理：移除大模型可能擅自添加的 ```json ... ``` markdown 标记
        content = re.sub(r"^```(?:json)?|```$", "", content, flags=re.IGNORECASE | re.MULTILINE).strip()

        data = json.loads(content)

        # 1. 使用集合(set)来存储需要移除的文件名，查找速度更快 O(1)
        files_need_to_remove = set()
        valid_modified_test_files =[]
        
        # 遍历原数据，分离出有效和无效的 test_files
        for test in data.get('modified_test_files',[]):
            if _is_test_file(test):
                valid_modified_test_files.append(test)
            else:
                files_need_to_remove.add(test)

        # 定义一个辅助函数来判断 test 是否有效
        def is_valid_test(test):
            file_part = test.split("::")[0] if "::" in test else ""
            return file_part not in files_need_to_remove

        # 2. 使用列表推导式(List Comprehension)过滤数据，生成新的列表
        added_tests = [
            test for test in data.get('added_tests', []) 
            if is_valid_test(test)
        ]
        
        removed_tests =[
            test for test in data.get('removed_tests', []) 
            if is_valid_test(test)
        ]

        # 3. 返回全新的清洗后的列表
        return {
            "added_tests": added_tests,
            "removed_tests": removed_tests,
            "modified_test_files": valid_modified_test_files,
        }
    except Exception as e:
        pdb.set_trace()
        print(f"    [LLM Fallback] Error parsing or fetching LLM response: {e}")
        return {"added_tests":[], "removed_tests": [], "modified_test_files":[]}


def infer_pass_to_pass(diff_text: str, added_tests: list) -> list:
    """Existing tests in touched files that are not newly added → pass_to_pass."""
    all_context = []
    current_file = ""
    current_lang = None

    for line in diff_text.splitlines():
        if line.startswith("+++ b/"):
            current_file = line[6:]
            current_lang = _is_test_file(current_file)
            continue

        if not current_lang:
            continue

        # Context lines (unchanged) start with a space
        if not line.startswith(" "):
            continue

        # Use the add patterns but match against context lines (space prefix)
        ctx_line = "+" + line[1:]   # fake a '+' prefix so patterns match
        for n in _extract_func_names(ctx_line, _TEST_FUNC_ADD.get(current_lang, [])):
            full = f"{current_file}::{n}"
            if full not in all_context:
                all_context.append(full)

    return [t for t in all_context if t not in added_tests]


def get_pr_diff(pr, token: str) -> str:
    resp = http_get_with_retry(
        pr.diff_url,
        headers={
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3.diff",
        },
        label=f"diff PR#{pr.number}",
    )
    return resp.text if resp else ""


# ──────────────────────────────────────────────
# Repo cloning
# ──────────────────────────────────────────────

def is_shallow(repo_dir: str) -> bool:
    return os.path.exists(os.path.join(repo_dir, ".git", "shallow"))


def ensure_repo_cloned(repo_full_name: str) -> Optional[str]:
    """Clone repo if needed; return local path or None on failure."""
    repo_dir = os.path.join(WORKSPACE_BASE_DIR, repo_full_name.replace("/", "__"))

    if os.path.exists(repo_dir) and not is_shallow(repo_dir):
        print(f"  Repo already cloned: {repo_dir}")
        return repo_dir

    if os.path.exists(repo_dir):
        print(f"  Removing shallow clone: {repo_dir}")
        subprocess.run(["rm", "-rf", repo_dir], check=True)

    print(f"  Cloning {repo_full_name}...")
    env = {**os.environ, "https_proxy": "http://10.214.99.83:7897"}
    for attempt in range(1, NETWORK_MAX_RETRIES + 1):
        result = subprocess.run(
            ["git", "clone", f"https://github.com/{repo_full_name}.git", repo_dir],
            env=env,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            break
        print(f"  [Clone error] attempt {attempt}/{NETWORK_MAX_RETRIES}: {result.stderr.strip()}")
        if attempt < NETWORK_MAX_RETRIES:
            time.sleep(NETWORK_RETRY_DELAY * attempt)
    else:
        print(f"  [Clone failed] Could not clone {repo_full_name} after {NETWORK_MAX_RETRIES} attempts")
        return None

    # Create tarball snapshot
    tar_path = f"{repo_dir}.tar.gz"
    tar_result = subprocess.run(
        ["tar", "czf", tar_path, "-C", WORKSPACE_BASE_DIR, repo_full_name.replace("/", "__")],
        capture_output=True, text=True,
    )
    if tar_result.returncode != 0:
        print(f"  [Tar warning] {tar_result.stderr.strip()}")

    return repo_dir


# ──────────────────────────────────────────────
# Record builder
# ──────────────────────────────────────────────

def build_record_from_gql(issue_node: dict, pr_node: dict, repo_full_name: str,
                          language: Optional[str], test_info: dict, pass_to_pass: list, diff: str = "") -> dict:
    """Build a record from raw GraphQL nodes (no extra REST calls needed)."""
    base_commit  = pr_node["baseRefOid"]
    head_commit  = pr_node["headRefOid"]
    merge_commit = (pr_node.get("mergeCommit") or {}).get("oid", "")
    pr_url       = pr_node["url"]
    pr_repo      = pr_node.get("repository", {}).get("nameWithOwner", repo_full_name)
    return {
        "repo_full_name": repo_full_name,
        "language": language,
        "pr_diff": diff,
        "issue": {
            "number":     issue_node["number"],
            "title":      issue_node["title"],
            "url":        issue_node["url"],
            "body":       issue_node.get("body") or "",
            "labels":     [n["name"] for n in issue_node.get("labels", {}).get("nodes", [])],
            "created_at": issue_node.get("createdAt", ""),
            "closed_at":  issue_node.get("closedAt", ""),
            "author":     (issue_node.get("author") or {}).get("login", ""),
        },
        "pr": {
            "number":      pr_node["number"],
            "title":       pr_node["title"],
            "url":         pr_url,
            "body":        pr_node.get("body") or "",
            "author":      (pr_node.get("author") or {}).get("login", ""),
            "merged_at":   pr_node.get("mergedAt", ""),
            "base_branch": pr_node.get("baseRefName", ""),
            "head_branch": pr_node.get("headRefName", ""),
            "commits": {
                "base_commit":  base_commit,
                "head_commit":  head_commit,
                "merge_commit": merge_commit,
            },
        },
        "tests": {
            "fail_to_pass":        test_info["added_tests"],
            "pass_to_pass":        pass_to_pass,
            "removed_tests":       test_info["removed_tests"],
            "modified_test_files": test_info["modified_test_files"],
        },
        "env_setup": {
            "checkout_base_commit": base_commit,
            "apply_pr_diff_url":    f"{pr_url}.diff",
            "apply_pr_patch_url":   f"{pr_url}.patch",
            "clone_command":        f"git clone https://github.com/{pr_repo}.git",
            "checkout_command":     f"git checkout {base_commit}",
            "note": (
                "Before state: checkout base_commit.  "
                "After state: checkout merge_commit."
            ),
        },
    }


def get_pr_diff_by_url(pr_url: str, token: str, pr_number: int) -> str:
    """Fetch diff using the PR html_url (from GraphQL node, no PyGithub object needed)."""
    resp = http_get_with_retry(
        f"{pr_url}.diff",
        headers={
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3.diff",
        },
        label=f"diff PR#{pr_number}",
    )
    return resp.text if resp else ""


# ──────────────────────────────────────────────
# Git-local commit scanner (primary method)
# ──────────────────────────────────────────────

# git log format: <sha> <unix_timestamp> <subject>
_GIT_LOG_FMT = "%H\x1f%at\x1f%s\x1f%b"

# Patterns to find issue/PR numbers in commit messages
_COMMIT_REF_RE = re.compile(
    r"(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?|ref|see|re|gh-?|#)\s*#?(\d+)",
    re.IGNORECASE,
)
_BARE_NUM_RE = re.compile(r"#(\d+)")


def _git(repo_dir: str, *args) -> str:
    r = subprocess.run(
        ["git", "-C", repo_dir] + list(args),
        capture_output=True, text=False,
    )
    if r.returncode == 0:
        return r.stdout.decode('utf-8', errors='replace').strip()
    return ""



def _commits_touching_tests(repo_dir: str) -> list[dict]:
    """
    Return all commits that touched test files, sorted newest-first.
    Each entry: {sha, timestamp, subject, body, files}
    Pure local git — zero network.
    """
    # Ask git for every commit that changed a test-looking path
    raw = _git(
        repo_dir,
        "log", "--all",
        f"--format=%H\x1f%at\x1f%s\x1f%b\x1e",
        "--",
        # Python
        "tests/*", "test/*", "**/test_*.py", "**/*_test.py",
        # JS / TS
        "**/*.test.js", "**/*.test.ts", "**/*.test.jsx", "**/*.test.tsx",
        "**/*.spec.js", "**/*.spec.ts", "**/*.spec.jsx", "**/*.spec.tsx",
        "**/__tests__/*",
        # Java
        "src/test/**/*.java", "**/*Test.java", "**/*Tests.java",
        # C / C++
        "tests/**/*.c", "tests/**/*.cpp", "tests/**/*.cc",
        "**/test_*.c", "**/test_*.cpp",
        # Go
        "**/*_test.go",
        # Rust
        "tests/**/*.rs", "**/test_*.rs",
        # Ruby
        "spec/**/*_spec.rb", "test/**/*_test.rb",
        # PHP
        "tests/**/*Test.php", "**/*Test.php",
    )
    commits = []
    for record in raw.split("\x1e"):
        record = record.strip()
        if not record:
            continue
        parts = record.split("\x1f", 3)
        if len(parts) < 3:
            continue
        sha, ts_str, subject = parts[0], parts[1], parts[2]
        body = parts[3] if len(parts) == 4 else ""
        try:
            ts = int(ts_str)
        except ValueError:
            continue

        # Get the list of changed files for this commit
        files_raw = _git(repo_dir, "diff-tree", "--no-commit-id", "-r",
                         "--name-only", sha)
        files = [f for f in files_raw.splitlines() if _is_test_file(f)]
        if not files:
            continue

        commits.append({
            "sha": sha,
            "timestamp": ts,
            "subject": subject,
            "body": body,
            "test_files": files,
        })

    # Already newest-first from git log, but sort explicitly to be safe
    commits.sort(key=lambda c: c["timestamp"], reverse=True)
    return commits


def _extract_issue_numbers(subject: str, body: str) -> list[int]:
    """Pull all referenced issue/PR numbers from a commit message."""
    text = f"{subject}\n{body}"
    nums = []
    for m in _COMMIT_REF_RE.finditer(text):
        nums.append(int(m.group(1)))
    for m in _BARE_NUM_RE.finditer(text):
        n = int(m.group(1))
        if n not in nums:
            nums.append(n)
    return nums


def _diff_for_commit(repo_dir: str, sha: str) -> str:
    """Return the unified diff introduced by a single commit."""
    return _git(repo_dir, "diff", f"{sha}^", sha)


def _merge_commit_info(repo_dir: str, sha: str) -> dict:
    """
    For a commit, return the base (parent) SHA and the merge commit on the
    default branch that contains it (if any).
    base_commit  = sha^  (the state before this commit — dev starting point)
    merge_commit = the merge commit on main/master that brought this in,
                   or sha itself if it was committed directly.
    """
    parent = _git(repo_dir, "rev-parse", f"{sha}^")

    # Check if this sha is a merge commit itself
    parents_raw = _git(repo_dir, "log", "--pretty=%P", "-1", sha)
    parents = parents_raw.split()
    if len(parents) >= 2:
        # It IS a merge commit: base = first parent, head = second parent tip
        return {"base_commit": parents[0], "head_commit": parents[1], "merge_commit": sha}

    # Otherwise find the merge commit that pulled this commit into the default branch
    merge_sha = _git(
        repo_dir,
        "log", "--merges", "--ancestry-path",
        "--format=%H", "-1",
        f"{sha}..HEAD",
    )
    return {
        "base_commit": parent,
        "head_commit": sha,
        "merge_commit": merge_sha or sha,
    }


def scan_git_for_candidates(
    repo_dir: str,
    repo_full_name: str,
    language: Optional[str],
    token: str,
    g: Github,
    max_commits: int = 300,
) -> list[dict]:
    """
    Scan the local git history for commits that touch test files.
    For each such commit:
      - Extract diff → fail_to_pass / pass_to_pass
      - Try to find a referenced issue number in the commit message
      - If found, query GitHub (GraphQL) to get issue type + title
      - Build a partial record (same schema as build_record_from_gql)

    Returns a list of candidate records sorted newest-first, each with an
    extra '_kind' key ('feature'|'bug'|'unknown') for the caller to filter.
    Skip commits with no new test functions in the diff.
    """
    owner, name = repo_full_name.split("/", 1)
    commits = _commits_touching_tests(repo_dir)
    print(f"  [git] Found {len(commits)} commits touching test files")

    candidates = []

    for commit in commits[:max_commits]:
        sha = commit["sha"]
        diff = _diff_for_commit(repo_dir, sha)
        if not diff:
            continue

        test_info = extract_tests_from_diff(diff)
        # if not test_info["added_tests"]:
        #     print(f"    [Info] Regex found no tests for commit#{sha[:20]}, triggering LLM fallback...")
        #     test_info_llm = extract_tests_via_llm_fallback(diff)
            
        #     # 如果 LLM 找到了测试
        #     if test_info_llm["added_tests"]:
        #         print(f"    [Info] LLM successfully rescued {len(test_info_llm['added_tests'])} tests!")
        #         test_info = test_info_llm

        # 4. 如果 LLM 也觉得没有测试，那就真的抛弃这条数据
        if not test_info["added_tests"]:
            continue  # no new test functions — not useful

        pass_to_pass = infer_pass_to_pass(diff, test_info["added_tests"])
        commit_info  = _merge_commit_info(repo_dir, sha)

        # ── Try to resolve issue via commit message ──────────────────────
        issue_numbers = _extract_issue_numbers(commit["subject"], commit["body"])
        issue_node = None
        pr_node    = None
        kind       = "unknown"

        for num in issue_numbers:
            # Single GraphQL call: fetch this specific issue + its closing PR
            node = _gql_get_issue_with_pr(owner, name, num, token)
            if node is None:
                continue
            # Only accept actual issues (not PRs) that are closed
            if node.get("__typename") == "PullRequest":
                # It's a PR reference — use it as pr_node directly
                if node.get("merged"):
                    pr_node = node
                continue
            if node.get("state") != "CLOSED":
                continue
            issue_node = node
            kind = classify_issue_from_node(issue_node) or "unknown"
            # Also try to get the closing PR from this issue node
            if pr_node is None:
                for item in (issue_node.get("timelineItems") or {}).get("nodes", []):
                    closer = (item or {}).get("closer")
                    if closer and closer.get("merged"):
                        pr_node = closer
                        break
            break  # take the first valid issue

        # ── Build record ─────────────────────────────────────────────────
        if issue_node and pr_node:
            # Full record with issue + PR info from GraphQL
            record = build_record_from_gql(
                issue_node, pr_node, repo_full_name, language, test_info, pass_to_pass, diff
            )
        elif issue_node:
            # Have issue but no PR node — synthesise PR info from git
            record = _build_record_git_only(
                issue_node=issue_node,
                commit=commit,
                commit_info=commit_info,
                repo_full_name=repo_full_name,
                language=language,
                test_info=test_info,
                pass_to_pass=pass_to_pass,
                diff=diff,
            )
        else:
            # No issue found at all — use commit message as instruction
            record = _build_record_commit_only(
                commit=commit,
                commit_info=commit_info,
                repo_full_name=repo_full_name,
                language=language,
                test_info=test_info,
                pass_to_pass=pass_to_pass,
                diff=diff,
            )
            kind = _classify_commit(commit["subject"], commit["body"])

        record["_kind"] = kind
        record["_commit_sha"] = sha
        candidates.append(record)
        print(f"  [git] sha={sha[:10]} kind={kind} "
              f"f2p={len(test_info['added_tests'])} "
              f"issue={'#'+str(issue_node['number']) if issue_node else 'none'}")

    return candidates  # already newest-first


# ── Single-issue GraphQL fetch ────────────────────────────────────────────────

_GQL_SINGLE_ISSUE = """
query($owner: String!, $name: String!, $number: Int!) {
  repository(owner: $owner, name: $name) {
    issueOrPullRequest(number: $number) {
      __typename
      ... on Issue {
        number title body url state createdAt closedAt
        number
        title
        body
        url
        createdAt
        closedAt
        author { login }
        labels(first: 10) { nodes { name } }
        timelineItems(itemTypes: [CLOSED_EVENT], first: 3) {
          nodes {
            ... on ClosedEvent {
              closer {
                ... on PullRequest {
                  number title body url merged mergedAt
                  mergeCommit { oid }
                  baseRefOid headRefOid baseRefName headRefName
                  author { login }
                  repository { nameWithOwner }
                }
              }
            }
          }
        }
      }
      ... on PullRequest {
        number title body url merged mergedAt
        mergeCommit { oid }
        baseRefOid headRefOid baseRefName headRefName
        author { login }
        repository { nameWithOwner }
      }
    }
  }
}
"""


def _gql_get_issue_with_pr(owner: str, name: str, number: int, token: str) -> Optional[dict]:
    """Fetch a single issue-or-PR node by number. Returns the raw GQL node or None."""
    try:
        data = graphql_with_retry(
            token, _GQL_SINGLE_ISSUE,
            {"owner": owner, "name": name, "number": number},
        )
        return (data.get("data") or {}).get("repository", {}).get("issueOrPullRequest")
    except RuntimeError:
        return None


# ── Record builders for git-only / commit-only cases ─────────────────────────

def _build_record_git_only(issue_node, commit, commit_info, repo_full_name,
                            language, test_info, pass_to_pass, diff: str = "") -> dict:
    """Issue found but no closing PR — synthesise PR section from git commit."""
    sha = commit["sha"]
    return {
        "repo_full_name": repo_full_name,
        "language": language,
        "pr_diff": diff,
        "issue": {
            "number":     issue_node["number"],
            "title":      issue_node["title"],
            "url":        issue_node["url"],
            "body":       issue_node.get("body") or "",
            "labels":     [n["name"] for n in issue_node.get("labels", {}).get("nodes", [])],
            "created_at": issue_node.get("createdAt", ""),
            "closed_at":  issue_node.get("closedAt", ""),
            "author":     (issue_node.get("author") or {}).get("login", ""),
        },
        "pr": None,
        "tests": {
            "fail_to_pass":        test_info["added_tests"],
            "pass_to_pass":        pass_to_pass,
            "removed_tests":       test_info["removed_tests"],
            "modified_test_files": test_info["modified_test_files"],
        },
        "env_setup": {
            "checkout_base_commit": commit_info["base_commit"],
            "clone_command":  f"git clone https://github.com/{repo_full_name}.git",
            "checkout_command": f"git checkout {commit_info['base_commit']}",
            "commits": commit_info,
            "note": "No linked PR found; commit info derived from git history.",
        },
    }


def _build_record_commit_only(commit, commit_info, repo_full_name,
                               language, test_info, pass_to_pass, diff: str = "") -> dict:
    """No issue found — use commit message as the task description."""
    instruction = commit["subject"]
    if commit["body"]:
        instruction += "\n\n" + commit["body"]
    return {
        "repo_full_name": repo_full_name,
        "language": language,
        "pr_diff": diff,
        "issue": {
            "number":     None,
            "title":      commit["subject"],
            "url":        None,
            "body":       instruction,
            "labels":     [],
            "created_at": "",
            "closed_at":  "",
            "author":     "",
        },
        "pr": None,
        "tests": {
            "fail_to_pass":        test_info["added_tests"],
            "pass_to_pass":        pass_to_pass,
            "removed_tests":       test_info["removed_tests"],
            "modified_test_files": test_info["modified_test_files"],
        },
        "env_setup": {
            "checkout_base_commit": commit_info["base_commit"],
            "clone_command":  f"git clone https://github.com/{repo_full_name}.git",
            "checkout_command": f"git checkout {commit_info['base_commit']}",
            "commits": commit_info,
            "note": "No linked issue or PR found; derived entirely from commit.",
        },
    }


def _classify_commit(subject: str, body_str: str) -> str:
    """Classify a commit message as feature/bug/unknown using LLM."""
    class _FakeIssue:
        title  = subject
        body  = body_str
        labels = type("L", (), {"__iter__": staticmethod(lambda: iter([]))})()
    # Reuse classify_issue — it falls through to LLM then rule-based
    result = classify_issue(_FakeIssue())
    return result or "unknown"




def process_repo(repo_name: str, g: Github, token: str, found_feature: str, found_bug: str) -> tuple[dict, bool]:
    print(f"\n{'='*60}\nProcessing: {repo_name}\n{'='*60}")

    try:
        repo = github_request_with_retry(g.get_repo, repo_name, g=g, label=f"get_repo {repo_name}")
    except (GithubException, RuntimeError) as e:
        print(f"  [Fatal] Cannot access repo: {e}")
        return {"repo": repo_name, "error": str(e)}, False

    result = {
        "repo": repo_name,
        "full_name": repo.full_name,
        "default_branch": repo.default_branch,
        "feature_issue": None,
        "bug_issue": None,
    }

    # Clone repo locally
    repo_dir = ensure_repo_cloned(repo.full_name)
    if repo_dir is None:
        result["error"] = "Clone failed"
        return result, False

    owner, name = repo.full_name.split("/", 1)
    language    = repo.language
    found = {"feature": found_feature, "bug": found_bug}
    skip_counts = {"no_pr": 0, "no_tests": 0, "bad_classify": 0}

    # 需要将内部函数稍微改造一下，让它接收 kind 参数
    def _process_gql_page(issue_node, pr_node, target_kind: str) -> bool:
        # 注意：这里不再重复调用分类，而是假设调用方已经确认了分类是 target_kind
        pr_num = pr_node["number"]
        pr_url = pr_node["url"]
        print(f"  Issue#{issue_node['number']} ({target_kind}) → PR#{pr_num}")
        
        diff = get_pr_diff_by_url(pr_url, token, pr_num)
        if not diff:
            return False
            
        test_info = extract_tests_from_diff(diff)
        # if not test_info["added_tests"]:
        #     print(f"    [Info] Regex found no tests for PR#{pr_num}, triggering LLM fallback...")
        #     test_info_llm = extract_tests_via_llm_fallback(diff)
            
        #     # 如果 LLM 找到了测试
        #     if test_info_llm["added_tests"]:
        #         print(f"    [Info] LLM successfully rescued {len(test_info_llm['added_tests'])} tests!")
        #         test_info = test_info_llm

        # 4. 如果 LLM 也觉得没有测试，那就真的抛弃这条数据
        if not test_info["added_tests"]:
            skip_counts["no_tests"] += 1
            return False
            
        pass_to_pass = infer_pass_to_pass(diff, test_info["added_tests"])
        result[f"{target_kind}_issue"] = build_record_from_gql(
            issue_node, pr_node, repo.full_name, language, test_info, pass_to_pass
        )
        print(f"    ✓ Recorded [{target_kind}] (f2p={len(test_info['added_tests'])}, p2p={len(pass_to_pass)})")
        return True

    # ── 第一阶段：带标签的高效定向搜索 (只查精确匹配) ──────────────────────────────────────
    for kind, label_list in (("feature", FEATURE_SEARCH_LABELS), ("bug", BUG_SEARCH_LABELS)):
        if found[kind] == 'issue-related':
            continue
            
        print(f"\n[Primary] Searching {kind} issues via GraphQL (labeled)...")
        for label in label_list:
            if found[kind] == 'issue-related':
                break
            for issue_node, pr_node in gql_fetch_issues_with_pr(
                owner, name, token, labels=[label], page_size=50, max_pages=10
            ):
                if pr_node is None:
                    skip_counts["no_pr"] += 1
                    continue
                # 带标签的也需要过一次分类器确认（防止标签乱打）
                if classify_issue_from_node(issue_node) != kind:
                    skip_counts["bad_classify"] += 1
                    continue
                    
                if _process_gql_page(issue_node, pr_node, kind):
                    found[kind] = "issue-related"
                    break

    # ── 第二阶段：无标签的全局搜索 (只遍历一遍！) ──────────────────────────────────────
    # 只有当 feature 或 bug 还有至少一个没找到时，才进行全局扫街
    missing_kinds =[k for k in ("feature", "bug") if found[k] != 'issue-related']
    
    if missing_kinds:
        print(f"\n[Fallback] Searching remaining missing types ({', '.join(missing_kinds)}) via unlabelled pages...")
        for issue_node, pr_node in gql_fetch_issues_with_pr(
            owner, name, token, labels=None, page_size=50, max_pages=200
        ):
            # 如果都找到了，提前终止这庞大的遍历
            if all(found[k] == 'issue-related' for k in ("feature", "bug")):
                print("  ✓ All needed types found. Stopping fallback search.")
                break

            if pr_node is None:
                skip_counts["no_pr"] += 1
                continue

            # 对这个 Issue 进行 LLM 分类（最耗时的操作，每个 Issue 只做一次）
            confirmed_kind = classify_issue_from_node(issue_node)
            
            # 如果分类结果不是我们正在找的类型（比如只需要找bug，但鉴定出来是feature），就跳过
            if confirmed_kind not in missing_kinds or found[confirmed_kind] == 'issue-related':
                continue
                
            # 处理满足条件的 Issue
            if _process_gql_page(issue_node, pr_node, confirmed_kind):
                found[confirmed_kind] = "issue-related"
                # 再次更新 missing_kinds 以减少后续无用的比对
                missing_kinds =[k for k in ("feature", "bug") if found[k] != 'issue-related']

    # ── Fallback: scan local git history for any still-missing kind ────────
    if found["feature"] != 'issue-related' or found["bug"] != 'issue-related':
        print("\n[Fallback] Scanning local git history for missing issue types...")
        # Zero network cost for discovery; only 1 GraphQL call per referenced issue.
        # Candidates are already sorted newest-first.
        candidates = scan_git_for_candidates(
            repo_dir, repo.full_name, language, token, g
        )

        for record in candidates:
            git_kind = record.pop("_kind", "unknown")
            record.pop("_commit_sha", None)
            if git_kind not in ("feature", "bug") or found[git_kind] == 'issue-related':
                continue
            result[f"{git_kind}_issue"] = record
            found[git_kind] = 'issue-related' if record["issue"]["number"] else 'commit-only'
            print(f"  [git] ✓ {git_kind}: Issue#{(record['issue']['number'] or 'commit-only')}")

    print(f"\n  Skip summary: {skip_counts}")
    if not found["feature"]:
        print("  ⚠ No suitable feature issue found")
    if not found["bug"]:
        print("  ⚠ No suitable bug issue found")

    if found['feature'] == 'issue-related' and found['bug'] == 'issue-related':
        return result, True
    return result, False


# ──────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(
        description="Collect feature/bug issue+PR pairs with test info for coding-agent evaluation."
    )
    p.add_argument("--repos", help="Comma-separated owner/repo list")
    p.add_argument("--file",  help="JSON file with list of {workspace: 'owner__repo'} objects")
    p.add_argument("--output", default="repo_issues_result.json")
    p.add_argument("--token", default=os.environ.get("GITHUB_TOKEN", ""))
    return p.parse_args()


def main():
    args = parse_args()

    if not args.token:
        print("ERROR: GitHub token required. Set GITHUB_TOKEN or use --token.")
        sys.exit(1)

    g = Github(auth=Auth.Token(args.token), per_page=100)

    rl = g.get_rate_limit()
    print(f"Rate limit: {rl.resources.core.remaining}/{rl.resources.core.limit} core, "
          f"{rl.resources.search.remaining}/{rl.resources.search.limit} search, "
          f"{rl.resources.graphql.remaining}/{rl.resources.graphql.limit} graphql")
    if rl.resources.core.remaining < 100:
        print("WARNING: Low core rate limit — waits may occur frequently")

    # Resolve repo list
    if args.repos:
        repos = [r.strip() for r in args.repos.split(",") if r.strip()]
    elif args.file:
        with open(args.file, encoding="utf-8") as f:
            data = json.load(f)
            data = data.get("data", data) if isinstance(data, dict) else data
            repos = [item["workspace"].replace("__", "/") for item in data]
    else:
        print("ERROR: Provide --repos or --file.")
        sys.exit(1)
    
    # Load existing results (resume support)
    output_path = args.output
    if os.path.exists(output_path):
        with open(output_path, encoding="utf-8") as f:
            all_results = json.load(f)
        print(f"Loaded {len(all_results)} existing results from {output_path}")
    else:
        all_results = {}

    for repo_name in tqdm(repos, desc="Repos", unit="repo"):
        found_feature = ""
        found_bug = ""
        existing = all_results.get(repo_name, {})
        if repo_name in all_results:
            if "feature_issue" in existing and existing["feature_issue"] is not None:
                # 只有当 PR 存在且不为 None 时，才认为是完全成功的
                if existing["feature_issue"].get("pr") or existing["feature_issue"].get("pr_diff"):
                    found_feature = 'issue-related' if existing["feature_issue"]["issue"]["number"] else 'commit-only'
            if "bug_issue" in existing and existing["bug_issue"] is not None:
                # 只有当 PR 存在且不为 None 时，才认为是完全成功的
                if existing["bug_issue"].get("pr") or existing["bug_issue"].get("pr_diff"):
                    found_bug = 'issue-related' if existing["bug_issue"]["issue"]["number"] else 'commit-only'
            
            if found_feature == 'issue-related' and found_bug == 'issue-related':
                print(f"[Skip] {repo_name} already in results")
                continue

        result, _ = process_repo(repo_name, g, args.token, found_feature, found_bug)
        
        # 如果某些 issue 已经有效找到了，process_repo 直接保留之前的记录
        if found_feature:
            result["feature_issue"] = existing.get("feature_issue")
        if found_bug:
            result["bug_issue"] = existing.get("bug_issue")
            
        all_results[repo_name] = result

        # Save after every repo so progress is never lost
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(all_results, f, indent=2, ensure_ascii=False)
        print(f"  Saved → {output_path}")

    print(f"\n✅ Done. Results in: {output_path}")

    # Summary
    print("\n── Summary ──")
    for name, r in all_results.items():
        if "error" in r:
            print(f"{name}: ERROR – {r['error']}")
            continue
        for kind in ("feature", "bug"):
            rec = r.get(f"{kind}_issue")
            if rec:
                t = rec["tests"]
                print(f"  {name} [{kind}] Issue#{rec['issue']['number'] if rec['issue'] else 'N/A'} "
                      f"PR#{rec['pr']['number'] if rec['pr'] else 'N/A'} "
                      f"f2p={len(t['fail_to_pass'])} p2p={len(t['pass_to_pass'])}")
            else:
                print(f"  {name} [{kind}] not found")


if __name__ == "__main__":
    import os
    os.environ['https_proxy'] = "http://10.214.99.83:7897"
    main()