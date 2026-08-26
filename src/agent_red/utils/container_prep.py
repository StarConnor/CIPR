import os
import pdb
import requests
import time
import tarfile
import shutil
import os
from urllib.parse import urlparse
from typing import List, Optional
import subprocess
from ..custom_types import PromptInjection, Sample, ExperimentConfig
from .others import docker_cp_to_container, docker_write_str_to_file
from .prepare_skills import prepare_skills, prepare_rules
import logging

logger = logging.getLogger(__name__)

PROJECT_DIR = "/home/devuser/project"


def baseline_project_git_state(container, commit_message: str = "Initial repository state"):
    """Make injected files part of the repo baseline.

    In the intended benchmark scenario, the agent receives/clones a repository
    that already contains the injected content. Therefore a normal `git diff`
    during the agent run should be clean and should not reveal the injection.

    The previous implementation ran plain `git add .`/`git commit` without
    checking errors or setting the working directory. Docker exec's default cwd
    is not guaranteed to be the project directory, so the commit could silently
    fail and leave injected files visible in `git diff`.
    """
    script = f"""
set -eu
cd {PROJECT_DIR}

if [ ! -d .git ]; then
  echo "[baseline] no .git directory under {PROJECT_DIR}; cannot hide injected changes from git diff" >&2
  exit 0
fi

git config --global --add safe.directory {PROJECT_DIR} || true
git config user.name 'Mike'
git config user.email 'mikejoe@gmail.com'

# Stage every change caused by env setup / prompt injection. This models the
# user receiving this exact repo state as the starting point.
git add -A

if ! git diff --cached --quiet; then
  git commit -m '{commit_message}'
else
  echo "[baseline] no staged changes to commit"
fi

# Refresh index and print any remaining dirty state. A non-empty status here
# means `git diff` may still expose injected content to the agent.
git update-index -q --refresh || true
git status --short
"""
    exit_code, output = container.exec_run(
        ["/bin/sh", "-lc", script],
        user="devuser",
        workdir=PROJECT_DIR,
    )
    decoded = output.decode(errors="replace")
    if exit_code != 0:
        logger.warning(f"Failed to baseline project git state: exit={exit_code}, output:\n{decoded}")
        raise RuntimeError(f"Failed to baseline project git state: exit={exit_code}, output:\n{decoded}")

    dirty_lines = [
        line for line in decoded.splitlines()
        if line and not line.startswith("[baseline]") and (
            line.startswith(" M ") or line.startswith("M ") or
            line.startswith("A ") or line.startswith(" A ") or
            line.startswith("D ") or line.startswith(" D ") or
            line.startswith("?? ")
        )
    ]
    if dirty_lines:
        logger.warning(
            "Project still has dirty git status after baseline commit; ordinary "
            f"`git diff` may reveal injected/setup changes:\n{decoded}"
        )

def prep_prompt_injections(prompt_injections: List[PromptInjection], container, web_port: int, attacker_port: int, attacker_domain: str | None, attacker_endpoint: str = ""):
    """
    Prepares prompt injections by replacing placeholders with actual server addresses.
    """
    for injection in prompt_injections:
        if "{{ATTACKER_SERVER}}" in injection.payload_content:
            assert attacker_domain is not None
            injection.payload_content = injection.payload_content.replace("{{ATTACKER_SERVER}}", f"https://{attacker_domain}/{attacker_endpoint}")
        payload_content = injection.payload_content
        file_path = os.path.join("/home/devuser/project", injection.target_file_path)
        if injection.injection_script:
            docker_write_str_to_file(injection.injection_script, "/tmp/injection_script.sh", container=container, target_user="devuser")
            exit_code, output = container.exec_run("chmod +x /tmp/injection_script.sh", user="root")
            exit_code, output = container.exec_run(f"/tmp/injection_script.sh {file_path} '{payload_content}' '{injection.injection_type}' '{injection.match_pattern}'", user="root")
            if exit_code != 0:
                logger.warning(f"Injection script failed for file '{file_path}' with exit code {exit_code} and output: {output.decode()}")
                raise ValueError(f"Injection script failed for file '{file_path}' with exit code {exit_code} and output: {output.decode()}")
            exit_code, output = container.exec_run(f"chown -R devuser:devuser /home/devuser/project", user="root")
            continue
        exit_code, output = container.exec_run(f"cat {file_path}", user="devuser")
        if exit_code != 0:
            logger.warning(f"Failed to read target file '{injection.target_file_path}' with exit code {exit_code} and output: {output.decode()}")
            if injection.injection_type == 'append':
                container.exec_run(f"touch {file_path}", user="devuser")
                new_content = injection.payload_content
            else:
                raise ValueError(f"Failed to read target file '{injection.target_file_path}' with exit code {exit_code} and output: {output.decode()} and injection_type {injection.injection_type} not supported")
        else:
            try:
                original_content = output.decode()
            except:
                logger.warning(f"Failed to decode content of target file '{injection.target_file_path}'. It may contain binary data. Injection will be skipped. Output: {output}")
                raise ValueError(f"Failed to decode content of target file '{injection.target_file_path}'. It may contain binary data. Injection will be skipped. Output: {output}")
            if injection.injection_type == "append":
                new_content = original_content + "\n" + payload_content
            elif injection.injection_type == "insert_after_match":
                if injection.match_pattern in original_content:
                    new_content = original_content.replace(injection.match_pattern, injection.match_pattern + payload_content)
                else:
                    raise ValueError(f"Match pattern '{injection.match_pattern}' not found in target file '{injection.target_file_path}'. No injection performed.")
            elif injection.injection_type == "replace":
                new_content = original_content.replace(injection.match_pattern, payload_content)
            elif injection.injection_type == "insert_before_match":
                if injection.match_pattern in original_content:
                    new_content = original_content.replace(injection.match_pattern, payload_content + injection.match_pattern)
                else:
                    raise ValueError(f"Match pattern '{injection.match_pattern}' not found in target file '{injection.target_file_path}'. No injection performed.")
            else:
                raise ValueError(f"Unknown injection type: {injection.injection_type}")
        docker_write_str_to_file(new_content, file_path, container=container, target_user="devuser")

def check_tar_gz_validity(file_path: str) -> bool:
    if not os.path.exists(file_path):
        logger.warning(f"❌ File not found: {file_path}")
        return False
    
    # Check whether the file size is 0
    if os.path.getsize(file_path) == 0:
        logger.warning(f"❌ File is empty (0 bytes): {file_path}")
        return False
    
    # Try to open and validate the tar.gz file
    try:
        with tarfile.open(file_path, 'r:gz') as tar:
            # Get the file list; this raises if the archive is corrupted
            members = tar.getmembers()
            if not members:
                logger.warning(f"⚠️  tar.gz archive contains no files: {file_path}")
                return False
            
            # Validate the integrity of the first entry (optional; nothing is actually extracted)
            # For stricter checking, the first small file could be extracted to a temporary location,
            # but getmembers usually suffices for detecting corruption.
            
        logger.info(f"✅ Valid tar.gz archive: {file_path} ({len(members)} files)")
        return True
        
    except tarfile.ReadError as e:
        logger.warning(f"❌ Corrupted tar.gz archive (ReadError): {file_path} - {e}")
        return False
    except EOFError as e:
        logger.warning(f"❌ Incomplete tar.gz archive (EOFError): {file_path} - {e}")
        return False
    except Exception as e:
        logger.warning(f"❌ Unable to read tar.gz archive: {file_path} - {e}")
        return False

def git_clone_depth1(repo_name: str, target_dir: str, branch: Optional[str] = None) -> bool:
    try:
        # If the target directory already exists, remove it first
        if os.path.exists(target_dir):
            logger.info(f"📁 Directory already exists, removing: {target_dir}")
            shutil.rmtree(target_dir)
        
        # Build the git clone command
        cmd = ['git', 'clone', '--depth', '1']
        
        if branch:
            cmd.extend(['--branch', branch])
        
        repo_url = f"https://github.com/{repo_name}.git"
            
        cmd.extend([repo_url, target_dir])
        
        logger.info(f"🔄 Running git clone: {' '.join(cmd)}")
        
        # Run the clone
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False
        )
        
        if result.returncode == 0:
            logger.info(f"✅ Git clone succeeded: {target_dir}")
            return True
        else:
            logger.warning(f"❌ Git clone failed: {result.stderr}")
            return False
            
    except Exception as e:
        logger.warning(f"❌ Git clone raised an exception: {e}")
        return False

def container_preparation(exp_config: ExperimentConfig, sample: Sample, container, web_port: int, attacker_port: int, workspace_base_path: str):
    env_setup_script = sample.env_setup_script if sample.env_setup_script else ""
    if sample.workspace:
        while (not check_tar_gz_validity(os.path.join(workspace_base_path, f"{sample.workspace}.tar.gz"))):
            logger.warning(f"Tar.gz file for workspace '{sample.workspace}' is not valid yet. Retrying in 5 seconds...")
            repo_path = os.path.join(workspace_base_path, sample.workspace.replace("__", "/"))
            tar_name = os.path.join(workspace_base_path, f"{sample.workspace}.tar.gz")
            git_clone_depth1(sample.workspace.replace("__", "/"), repo_path)
            os.system(f"tar -czf {tar_name} -C {os.path.dirname(repo_path)} {os.path.basename(repo_path)}")
            time.sleep(5)

        docker_cp_to_container(os.path.join(workspace_base_path, f"{sample.workspace}.tar.gz"), "/home/devuser", container=container)
        exit_code, output = container.exec_run(
            f"tar -xzf /home/devuser/{sample.workspace}.tar.gz -C /home/devuser/project --strip-components=1",
            user="devuser"
        )
        exit_code, output = container.exec_run(
            f"rm -f /home/devuser/{sample.workspace}.tar.gz",
            user="root"
        )
    if env_setup_script:
        # Decode escape sequences like \n, \t, etc. from the YAML string
        env_setup_script = env_setup_script.encode().decode('unicode_escape')
        docker_write_str_to_file(env_setup_script, "/tmp/env_setup.sh", container=container, target_user="devuser")
        exit_code, output = container.exec_run("chmod +x /tmp/env_setup.sh", user="root")
        exit_code, output = container.exec_run("bash /tmp/env_setup.sh", user="root")
        # env_setup often runs as root because it may need apt/system packages.
        # Normalize ownership afterwards so the coding agent (devuser) can edit
        # the repo and package-manager state created during preparation.
        # docker-py's exec_run does not interpret shell redirections/operators
        # for plain string commands in all call paths. Run through a shell so
        # `2>/dev/null || true` is parsed instead of being passed to `chown` as
        # literal path arguments.
        chown_code, chown_output = container.exec_run(
            [
                "bash",
                "-lc",
                (
                    "mkdir -p /home/devuser/.cache /home/devuser/.npm /home/devuser/.pnpm-store "
                    "/home/devuser/.m2 /home/devuser/.gradle /home/devuser/.cargo /home/devuser/.rustup "
                    "/home/devuser/go /home/devuser/.gem /home/devuser/.bundle "
                    "/home/devuser/composer /home/devuser/.config && "
                    "chown -R devuser:devuser /home/devuser/project "
                    "/home/devuser/.cache /home/devuser/.npm /home/devuser/.pnpm-store "
                    "/home/devuser/.m2 /home/devuser/.gradle /home/devuser/.cargo /home/devuser/.rustup "
                    "/home/devuser/go /home/devuser/.gem /home/devuser/.bundle "
                    "/home/devuser/composer /home/devuser/.config"
                ),
            ],
            user="root",
        )
        if chown_code != 0:
            logger.warning(f"Failed to normalize devuser ownership after env_setup: {chown_output.decode(errors='replace')}")
        if exit_code != 0:
            logger.error(f"Environment setup script failed with exit code {exit_code} and output: {output.decode()}")
    
    script_to_fetch_from_attacker_server = sample.script_to_fetch_from_attacker_server
    # pdb.set_trace()
    if script_to_fetch_from_attacker_server:
        max_attempts = 5
        retry_delay = 3  # seconds
        attacker_endpoint = sample.attacker_endpoint
        for attempt in range(1, max_attempts + 1):
            try:
                res = requests.post(
                    url=f"http://localhost:{attacker_port}/set-custom",
                    timeout=10,  # Add timeout to prevent hanging
                    json={
                        "script": script_to_fetch_from_attacker_server,
                        "attacker_server": f"https://{sample.attacker_domain}" if sample.attacker_domain else f"http://{urlparse(exp_config.https_proxy).hostname}:{attacker_port}",
                        "endpoint": attacker_endpoint,
                        "test_id": sample.id
                    }
                )
                if res.status_code != 200:
                    raise ValueError(f"Failed to set default test case in attacker server for sample id {sample.id}, status: {res.status_code}, response: {res.text}, {attacker_endpoint=}")
                # Success, break out of retry loop
                break
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                if attempt < max_attempts:
                    logger.warning(f"⚠️  Attempt {attempt}/{max_attempts} failed: {e.__class__.__name__}. Retrying in {retry_delay}s...")
                    time.sleep(retry_delay)
                else:
                    logger.error(f"❌ All {max_attempts} attempts failed to connect to attacker server: http://localhost:{attacker_port}/set-default")
                    logger.error(f"   Error: {e}")
                    raise e
            except Exception as e:
                logger.error(f"❌ Unexpected error connecting to web server: {e}")
                raise e
        

    max_attempts = 5
    retry_delay = 3  # seconds
    if sample.custom_html_content:
        for attempt in range(1, max_attempts + 1):
            html_endpoint = sample.html_endpoint if sample.html_endpoint else "index.html"
            try:
                res = requests.post(
                    url=f"http://localhost:{web_port}/set-custom",
                    timeout=10,  # Add timeout to prevent hanging
                    json={
                        "html": sample.custom_html_content if sample.custom_html_content else "<h1>Default Test Page</h1>",
                        "attacker_server": f"https://{sample.attacker_domain}" if sample.attacker_domain else f"http://{urlparse(exp_config.https_proxy).hostname}:{attacker_port}",
                        "endpoint": html_endpoint,
                        "test_id": sample.id
                    }
                )
                if res.status_code != 200:
                    raise ValueError(f"Failed to set default test case in web server for sample id {sample.id}, status: {res.status_code}")
                # Success, break out of retry loop
                break
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                if attempt < max_attempts:
                    logger.warning(f"⚠️  Attempt {attempt}/{max_attempts} failed: {e.__class__.__name__}. Retrying in {retry_delay}s...")
                    time.sleep(retry_delay)
                else:
                    logger.error(f"❌ All {max_attempts} attempts failed to connect to web server: http://localhost:{web_port}/set-default")
                    logger.error(f"   Error: {e}")
                    raise e
            except Exception as e:
                logger.error(f"❌ Unexpected error connecting to web server: {e}")
                raise e
    if "{{ATTACKER_SERVER}}" in sample.user_instruction:
        assert sample.attacker_domain is not None
        sample.user_instruction = sample.user_instruction.replace("{{ATTACKER_SERVER}}", f"https://{sample.attacker_domain}/{sample.attacker_endpoint}")
    if "{{HTML_SERVER}}" in sample.user_instruction:
        assert sample.html_domain is not None
        sample.user_instruction = sample.user_instruction.replace("{{HTML_SERVER}}", f"https://{sample.html_domain}/{sample.html_endpoint}")

    if exp_config.defense.enabled:
        if exp_config.defense.file_modifications:
            prep_prompt_injections(exp_config.defense.file_modifications, container, web_port, attacker_port, sample.attacker_domain, sample.attacker_domain or "")
    
    # Prefer per-sample skill/rule metadata produced by dataset_gen.main.  Fall
    # back to the experiment-level SkillConfig for older datasets/configs.
    sample_skills_config = getattr(sample, "skills", None)
    if sample_skills_config:
        prepare_skills(sample_skills_config, container, exp_config.agent.software)
        prepare_rules(sample_skills_config, container, exp_config.agent.software)
    elif exp_config.skills.enabled:
        prepare_skills(exp_config.skills, container, exp_config.agent.software)

    # Some dataset versions also duplicate rule/defense metadata under
    # sample.defense.  Install it if present and not already covered above.
    sample_defense_config = getattr(sample, "defense", None)
    if sample_defense_config and not sample_skills_config:
        prepare_rules(sample_defense_config, container, exp_config.agent.software)
    prep_prompt_injections(sample.prompt_injections, container, web_port, attacker_port, sample.attacker_domain, sample.attacker_domain or "")

    baseline_project_git_state(container)
