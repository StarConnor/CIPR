import json
import requests
import os
import tqdm

def fetch_and_save_diffs(input_json="repo_issues_result.json", output_json="repo_issues_result_w_diff.json"):
    if not os.path.exists(input_json):
        print(f"Input file {input_json} not found.")
        return

    with open(input_json, "r") as f:
        data = json.load(f)

    # 如果 output_json 存在，读取并合并已有结果，以避免重复请求
    if os.path.exists(output_json):
        try:
            with open(output_json, "r") as f:
                output_data = json.load(f)
                for repo_name, repo_info in output_data.items():
                    if repo_name in data and isinstance(repo_info, dict) and isinstance(data[repo_name], dict):
                        for issue_type in ['feature_issue', 'bug_issue']:
                            if issue_type in repo_info and repo_info[issue_type] and "pr_diff" in repo_info[issue_type]:
                                if issue_type in data[repo_name] and data[repo_name][issue_type]:
                                    data[repo_name][issue_type]["pr_diff"] = repo_info[issue_type]["pr_diff"]
        except Exception as e:
            print(f"Failed to load existing output json: {e}")

    # Process all keys
    for repo_name, repo_data in tqdm.tqdm(data.items(), desc="Fetching diffs"):
        if not isinstance(repo_data, dict):
            continue
        
        for issue_type in ['feature_issue', 'bug_issue']:
            if issue_type in repo_data and repo_data[issue_type]:
                issue_data = repo_data[issue_type]
                
                # Check if we already have it
                if "pr_diff" in issue_data and issue_data["pr_diff"]:
                    continue

                if "env_setup" in issue_data and "apply_pr_diff_url" in issue_data["env_setup"]:
                    diff_url = issue_data["env_setup"]["apply_pr_diff_url"]
                    if diff_url:
                        try:
                            response = requests.get(diff_url, timeout=10)
                            if response.status_code == 200:
                                issue_data["pr_diff"] = response.text
                            else:
                                issue_data["pr_diff"] = ""
                                print(f"Warning: Failed to fetch diff for {repo_name} {issue_type} (Status: {response.status_code})")
                        except Exception as e:
                            issue_data["pr_diff"] = ""
                            print(f"Error fetching diff for {repo_name} {issue_type}: {e}")

    with open(output_json, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Successfully saved to {output_json}")

if __name__ == "__main__":
    fetch_and_save_diffs()
