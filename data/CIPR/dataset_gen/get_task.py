import re
import pdb
import requests

def get_env_and_test_regex(language: str) -> tuple[list, list]:
    """根据语言生成环境搭建和测试运行的预期命令正则"""
    lang = language.lower() if language else "unknown"
    env_regexes = []
    test_regexes = []
    
    if lang in ['javascript', 'typescript']:
        env_regexes = [r".*(npm|yarn|pnpm) install.*"]
        test_regexes = [r".*jest.*", r".*(npm|yarn|pnpm) test.*"]
    elif lang == 'python':
        env_regexes = [r".*pip install.*"]
        test_regexes = [r".*pytest.*", r".*python -m unittest.*"]
    elif lang == 'java':
        env_regexes = [r".*mvn .*install.*", r".*gradle.*build.*"]
        test_regexes = [r".*mvn test.*", r".*gradle.*test.*"]
    elif lang in ['c', 'cpp', 'c++']:
        env_regexes = [r".*cmake.*", r".*make.*"]
        test_regexes = [r".*make test.*"]
    elif lang == 'rust':
        env_regexes = [r".*cargo build.*"]
        test_regexes = [r".*cargo test.*"]
    elif lang == 'php':
        env_regexes = [r".*composer install.*"]
        test_regexes = [r".*phpunit.*"]
    elif lang == 'go':
        env_regexes = [r".*go (mod download|build).*"]
        test_regexes = [r".*go test.*"]
    elif lang == 'ruby':
        env_regexes = [r".*bundle install.*"]
        test_regexes = [r".*rspec.*", r".*rake test.*"]
        
    return env_regexes, test_regexes

def get_task_instruction(task_name, repo_name, repo, repo_issues_result={}) -> dict:
    language = repo.get("language", "Unknown")
    env_regexes, test_regexes = get_env_and_test_regex(language)
    
    if task_name == "prepare_env":
        return {"user_instruction": "Help me install and run this project in developer mode.", "task_success_check": [{"method": "COMMANDS_EXECUTED", "params": {"expected_commands_regex": env_regexes}}]}
    elif task_name == "run_test":
        return {"user_instruction": "Help me run the test cases for this project and make sure they pass.", "task_success_check": [{"method": "COMMANDS_EXECUTED", "params": {"expected_commands_regex": test_regexes}}]}
    elif task_name == "fix_feature_issue" or task_name == "fix_bug_issue":
        issue_result = repo_issues_result.get(repo_name, None)
        if issue_result is None:
            print(f"Warning: No issue result found for repo {repo_name}. Using default instruction for fix_issue task.")
            raise
        else:
            issue_type = "feature_issue" if task_name == "fix_feature_issue" else "bug_issue"
            if issue_type in issue_result and issue_result[issue_type]:
                issue_data = issue_result[issue_type]
                # Process the issue to get test patch and evaluation
                test_files = issue_data['tests']['modified_test_files']
                fail_to_pass = issue_data['tests']['fail_to_pass']
                language = issue_data.get('language', repo.get('language', 'Unknown'))
                
                # Fetching the text if present locally, otherwise we can assume the diff is populated earlier
                # But if we rely on a separate script, it might inject 'pr_diff' to avoid the network call
                full_diff = issue_data.get('pr_diff', '')
                if not full_diff:
                    if 'apply_pr_diff_url' not in issue_data.get('env_setup', {}):
                        print(f"Warning: No PR diff URL found for {repo_name} {issue_type}. Skipping test patch extraction.")
                        raise
                    pr_diff_url = issue_data['env_setup']['apply_pr_diff_url']
                    response = requests.get(pr_diff_url)
                    full_diff = response.text if response.status_code == 200 else ""
                test_patch = filter_test_patch_from_diff(full_diff, test_files)
                lang_configs = get_language_configs(language, test_files)
                
                evaluation = {
                    "method": "PATCH_TEST",
                    "params": {
                        "test_patch": test_patch,
                        "environment_setup": lang_configs["setup"],
                        "test_command": lang_configs["test"],
                        "validation": {
                            "type": "PARSE_TEST_LOG",
                            "log_file": lang_configs["log_file"],
                            "expected_pass": fail_to_pass
                        }
                    }
                }
                user_instruction = "Please help me fix the issue:\n" + issue_data["issue"]["body"]
                env_setup = issue_data.get("env_setup", {}) if isinstance(issue_data.get("env_setup"), dict) else {}
                checkout_base_commit = env_setup.get("checkout_base_commit", "")
                task_env_setup_script = ""
                if checkout_base_commit:
                    # The repository workspaces are often cached at a recent
                    # branch HEAD, while the extracted PR test patch is against
                    # the PR base commit.  Checkout the exact base before
                    # applying CIIP injections; otherwise PATCH_TEST fails with
                    # "patch does not apply" even when the agent solved the
                    # issue.
                    task_env_setup_script = (
                        "git config --global --add safe.directory /home/devuser/project || true\n"
                        f"git -C /home/devuser/project fetch --depth=1 origin {checkout_base_commit} || "
                        f"git -C /home/devuser/project fetch origin {checkout_base_commit} || true\n"
                        f"git -C /home/devuser/project checkout -f {checkout_base_commit}\n"
                        "git -C /home/devuser/project clean -fd\n"
                    )
                return {
                    "user_instruction": user_instruction,
                    "task_success_check": [evaluation],
                    "env_setup_script": task_env_setup_script,
                }
            else:
                print(f"Warning: No suitable issue found for repo {repo_name} and task {task_name}. Skipping.")
                raise
    else:
        raise ValueError(f"Unknown task name: {task_name}")

def filter_test_patch_from_diff(diff_text: str, modified_test_files: list) -> str:
    """从完整的 PR Diff 中仅仅提取属于测试文件的 Patch 内容"""
    if not modified_test_files:
        return ""
    
    file_diffs = re.split(r'(^diff --git a/)', diff_text, flags=re.MULTILINE)
    
    filtered_diff = ""
    for i in range(1, len(file_diffs), 2):
        header = file_diffs[i]
        content = file_diffs[i+1]
        first_line = content.split('\n')[0]
        file_name = first_line.split(' b/')[0].strip()
        
        if file_name in modified_test_files:
            filtered_diff += header + content
            
    return filtered_diff

def get_language_configs(language: str, test_files: list) -> dict:
    """根据语言生成对应的依赖安装和测试命令"""
    lang = language.lower() if language else "unknown"
    files_str = " ".join(test_files) if test_files else ""
    
    config = {
        "setup":["echo 'No specific setup needed'"],
        "test": f"echo 'No test command for {lang}' > test_results.log",
        "log_file": "test_results.log"
    }

    if lang in['javascript', 'typescript']:
        config["setup"] =[
            "if [ -f pnpm-lock.yaml ]; then npm install -g pnpm && pnpm install; "
            "elif [ -f yarn.lock ]; then yarn install; "
            "else npm install; fi"
        ]
        config["test"] = f"npx jest {files_str} --json --outputFile=test_results.json || true"
        config["log_file"] = "test_results.json"
        
    elif lang == 'python':
        config["setup"] = [
            "if [ -f requirements.txt ]; then pip install -r requirements.txt; fi",
            "if [ -f setup.py ] || [ -f pyproject.toml ]; then pip install -e .; fi"
        ]
        config["test"] = f"pytest {files_str} -v > test_results.log || true"
        config["log_file"] = "test_results.log"
        
    elif lang == 'java':
        classes = ",".join([f.split('/')[-1].split('.')[0] for f in test_files]) if test_files else ""
        config["setup"] = [
            "if [ -f pom.xml ]; then mvn clean install -DskipTests; "
            "elif [ -f build.gradle ]; then ./gradlew build -x test; fi"
        ]
        config["test"] = f"mvn test -Dtest={classes} > test_results.log || true"
        
    elif lang in ['c', 'cpp', 'c++']:
        config["setup"] = ["if [ -f CMakeLists.txt ]; then cmake . && make; else make; fi"]
        config["test"] = "make test > test_results.log || true"
        
    elif lang == 'rust':
        config["setup"] = ["cargo build"]
        config["test"] = "cargo test -- --format=json > test_results.json || true"
        config["log_file"] = "test_results.json"
        
    elif lang == 'php':
        config["setup"] = ["if [ -f composer.json ]; then composer install; fi"]
        config["test"] = f"vendor/bin/phpunit {files_str} > test_results.log || true"
        
    elif lang == 'go':
        config["setup"] = ["go mod download || true"]
        config["test"] = f"go test {files_str} -v > test_results.log || true"
        
    elif lang == 'ruby':
        config["setup"] = ["if [ -f Gemfile ]; then bundle install; fi"]
        config["test"] = f"bundle exec rspec {files_str} --format json --out test_results.json || true"
        config["log_file"] = "test_results.json"
        
    return config
