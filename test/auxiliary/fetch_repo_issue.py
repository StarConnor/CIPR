#!/usr/bin/env python3
import sys
import os
import re
import json
import tarfile
import subprocess
import urllib.request
import traceback


def run(cmd, cwd=None, capture=False):
    if capture:
        return subprocess.check_output(cmd, cwd=cwd, text=True).strip()
    subprocess.run(cmd, cwd=cwd, check=True)


# usage:
# python fetch_repo.py <repo_url> <issue_number> <absolute_workspace>

repo = sys.argv[1]
issue_num = sys.argv[2]
workspace = "/home/zfk/projects/demo/code-agent-redteam/temp_workspace"

assert os.path.isabs(workspace), "workspace must be absolute path"

repo_url = f"https://github.com/{repo}.git"
repo_name = repo.replace("/", "__")
repo_dir = os.path.join(workspace, repo.split("/")[-1])
tar_path = os.path.join(workspace, f"{repo_name}_{issue_num}.tar.gz")

os.makedirs(workspace, exist_ok=True)

if os.path.exists(repo_dir):
    print(f"Directory {repo_dir} already exists. We will keep it.")
else:
    # shallow clone
    run(["git", "clone", "--depth", "1", repo_url, repo_dir])

# github owner/repo
m = re.search(r"github\.com[:/](.+?/.+?)(?:\.git)?$", repo_url)
owner_repo = m.group(1)

# issue created time
url = f"https://api.github.com/repos/{owner_repo}/issues/{issue_num}"
req = urllib.request.Request(url)
req.add_header("Authorization", f"Bearer {os.environ.get('GITHUB_TOKEN', "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")}")
req.add_header("Accept", "application/vnd.github+json")

try:
    issue = json.loads(urllib.request.urlopen(req).read().decode())
except Exception as e:
    traceback.print_exception(e) 
    print(f"failed: url={url}, headers={req.header_items()}")
    raise
created_at = issue["created_at"]

# fetch some history then locate commit before issue creation
run(["git", "fetch", "--deepen", "200"], cwd=repo_dir)
commit = run(
    ["git", "rev-list", "-1", f"--before={created_at}", "HEAD"],
    cwd=repo_dir,
    capture=True,
)

run(["git", "checkout", commit], cwd=repo_dir)

# tar repo
with tarfile.open(tar_path, "w:gz") as tar:
    tar.add(repo_dir, arcname=repo.split("/")[-1])

print("issue time :", created_at)
print("commit     :", commit)
print("tar file   :", tar_path)