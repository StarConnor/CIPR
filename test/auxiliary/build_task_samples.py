import os
import subprocess
import json
import requests
import re
import pdb
import argparse

def filter_test_patch_from_diff(diff_text: str, modified_test_files: list) -> str:
    """Extract only the patch hunks belonging to test files from the full PR diff"""
    if not modified_test_files:
        return ""
    
    # Split the diff by file (diff --git a/...)
    file_diffs = re.split(r'(^diff --git a/)', diff_text, flags=re.MULTILINE)
    
    filtered_diff = ""
    for i in range(1, len(file_diffs), 2):
        header = file_diffs[i] # "diff --git a/"
        content = file_diffs[i+1]
        
        # Get the file name corresponding to the current diff block
        # The first line usually looks like: file.txt b/file.txt
        first_line = content.split('\n')[0]
        file_name = first_line.split(' b/')[0].strip()
        
        if file_name in modified_test_files:
            filtered_diff += header + content
            
    return filtered_diff

def get_language_configs(language: str, test_files: list) -> dict:
    """Generate dependency-install and test commands for the given language"""
    lang = language.lower()
    files_str = " ".join(test_files)
    
    # Default configuration
    config = {
        "setup":["echo 'No specific setup needed'"],
        "test": f"echo 'No test command for {lang}' > test_results.log",
        "log_file": "test_results.log"
    }

    if lang in['javascript', 'typescript']:
        # Auto-detect package manager and install dependencies
        config["setup"] =[
            "if [ -f pnpm-lock.yaml ]; then npm install -g pnpm && pnpm install; "
            "elif [ -f yarn.lock ]; then yarn install; "
            "else npm install; fi"
        ]
        # Most JS/TS projects use jest (e.g., MUI, React)
        config["test"] = f"npx jest {files_str} --json --outputFile=test_results.json || true"
        config["log_file"] = "test_results.json"
        
    elif lang == 'python':
        config["setup"] = [
            "if [ -f requirements.txt ]; then pip install -r requirements.txt; fi",
            "if [ -f setup.py ] ||[ -f pyproject.toml ]; then pip install -e .; fi"
        ]
        config["test"] = f"pytest {files_str} -v > test_results.log || true"
        config["log_file"] = "test_results.log"
        
    elif lang == 'java':
        # Java usually tests class names rather than file paths; keep it simple
        classes = ",".join([f.split('/')[-1].split('.')[0] for f in test_files])
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
        config["setup"] = ["if[ -f composer.json ]; then composer install; fi"]
        config["test"] = f"vendor/bin/phpunit {files_str} > test_results.log || true"
        
    elif lang == 'go':
        config["setup"] = ["go mod download || true"]
        config["test"] = f"go test {files_str} -v > test_results.log || true"
        
    elif lang == 'ruby':
        config["setup"] = ["if [ -f Gemfile ]; then bundle install; fi"]
        config["test"] = f"bundle exec rspec {files_str} --format json --out test_results.json || true"
        config["log_file"] = "test_results.json"
        
    return config

def build_json_config(record: dict, path: str, unique_id: str):
    config_dict = {
        'mode': "single_sample",
        'agent': {
            "software": "cc_cli",
            "model": {
                "model_name": "deepseek-v4-flash"
            }
        },
        'dataset_name': unique_id,
        'mode': "single_sample",
        'attack_method': "static_file",
        'defense': {
            'enabled': False,
            'file_modifications': []
        },
        'skills': {
            'enabled': False,
            'skills_names': []
        },
        'sample': {
            'id': f'{record['repo_full_name'].replace("/", "__")}_{record['issue']['number']}',
            #FIXME
            'workspace': record['repo_full_name'].replace("/", "__"),
            'env_setup_script': record['env_setup']['checkout_command'],
            'user_instruction': 'Please help me fix the issue:\n' + record['issue']['body'],
            'prompt_injections': [],
            'language': record['language'],
            'evaluation': {
                "task_success_check": [
                    record['evaluation']
                ]
            },
            'category': 'Benign',
        }
    }
    with open(path, 'w') as f:
        json.dump(config_dict, f, indent=2)

def test_record(record: dict) -> bool:
    config_name = f"{record['repo_full_name'].replace("/", "__")}_{record['issue']['number']}.json"
    build_json_config(record, os.path.join("/home/zfk/projects/demo/code-agent-redteam/test/temp_configs", config_name), config_name.split(".json")[0])
    arguments = [
        "--config", os.path.join("temp_configs", config_name),
        "--agent", "cc_cli",
        "--model", "deepseek-v4-flash",
    ]
    run_result = ""
    pdb.set_trace()
    try:
        run_result = subprocess.run(
            ['python', 'run_exp.py'] + arguments,
            text=True             # Return output as text (Python 3.7+)
        )
    except Exception as e:
        print(f"Error: {e}")
        print(f"Run result: {run_result}")

    
    exp_result_path = f"exp/single_sample/cc_cli/{config_name.split(".json")[0]}"
    # get the latest dir
    sub_dirs = [os.path.join(exp_result_path, d) for d in os.listdir(exp_result_path) if os.path.isdir(os.path.join(exp_result_path, d))]
    if not sub_dirs:
        print(f"No subdirectories found in {exp_result_path}")
        return False
    latest_dir = max(sub_dirs, key=os.path.getmtime)
    for filename in os.listdir(latest_dir):
        if filename.endswith(".log"):
            with open(os.path.join(exp_result_path, filename), 'r') as log_f:
                if "IDE interaction failed." in log_f:
                    return False
        elif filename.endswith(".json"):
            return True
    return False

def process_dataset(dataset: list) -> list:
    """Process the dataset, adding an evaluation field"""
    issue_dataset = []
    for entry in dataset:
        for issue_type in ['feature_issue', 'bug_issue']:
            if issue_type not in entry or not entry[issue_type]:
                continue
                
            issue_data = entry[issue_type]
            language = issue_data.get('language', 'Unknown')
            pr_diff_url = issue_data['env_setup']['apply_pr_diff_url']
            test_files = issue_data['tests']['modified_test_files']
            fail_to_pass = issue_data['tests']['fail_to_pass']
            
            # 1. Fetch the full PR diff
            print(f"Fetching diff for {issue_data['repo_full_name']} PR...")
            response = requests.get(pr_diff_url)
            full_diff = response.text if response.status_code == 200 else ""
            
            # 2. Extract the patch that only modifies test files
            test_patch = filter_test_patch_from_diff(full_diff, test_files)
            
            # 3. Get language-specific instructions
            lang_configs = get_language_configs(language, test_files)
            
            # 4. Build the evaluation field
            issue_data['evaluation'] = {
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
            issue_dataset.append(issue_data)
    return issue_dataset

# Usage example (assuming your data is in data.json):
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Build task samples from dataset.')
    parser.add_argument('--op', choices=['build', 'test'], required=True, help='Operation to perform: build or test')
    args = parser.parse_args()
    if args.op == 'build':
        with open("repo_issues_result.json", "r") as f:
            my_dataset = json.load(f)
        enriched_dataset = process_dataset([r for name, r in my_dataset.items() if name == 'nikic/PHP-Parser'])
        with open("task_samples_php-parser.json", "w") as f:
            json.dump(enriched_dataset, f, indent=2)
    elif args.op == 'test':
        with open("task_samples.json", "r") as f:
            enriched_dataset = json.load(f)
        for entry in enriched_dataset:
            test_record(entry)