# debug_runner.py
import asyncio
import os
import logging
from pathlib import Path
import sys

# The main function to execute evaluations from the inspect-ai library
from inspect_ai import eval


# Configure logging to see detailed output from the framework
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def env_setting_cve_bench():
    def get_command():
        
        return "eval-solution"

    os.environ["CVEBENCH_TAG"] = "2.0.0"

    supported_versions = ("critical", "high-severity", "easy")
    
    # Set CVEBENCH_VERSION
    if "CVEBENCH_VERSION" not in os.environ:
        os.environ["CVEBENCH_VERSION"] = "critical"
    elif os.environ["CVEBENCH_VERSION"] not in supported_versions:
        print(f"Invalid version: {os.environ['CVEBENCH_VERSION']}. Valid versions are: {', '.join(supported_versions)}")
        sys.exit(1)
    
    cvebench_version = os.environ["CVEBENCH_VERSION"]
    
    # Set directory paths
    base_dir = Path(__file__).parent  # Adjust based on your script location
    src_dir = base_dir
    
    cvebench_version_dir = (src_dir / cvebench_version).resolve()
    os.environ["CVEBENCH_VERSION_DIR"] = str(cvebench_version_dir)
    
    # Set subdirectory paths
    os.environ["CVEBENCH_METADATA_DIR"] = str(cvebench_version_dir / "metadata")
    os.environ["CVEBENCH_CHALLENGE_DIR"] = str(cvebench_version_dir / "challenges")
    os.environ["CVEBENCH_NVD_DIR"] = str(cvebench_version_dir / "nvd")
    os.environ["CVEBENCH_VERSION_DOCKER_DIR"] = str(cvebench_version_dir / "docker")
    
    # Set common directory paths
    common_dir = src_dir / "common"
    os.environ["CVEBENCH_DOCKER_DIR"] = str(common_dir / "docker")
    os.environ["CVEBENCH_EVALUATIONS_DIR"] = str(common_dir / "evaluations")
    os.environ["CVEBENCH_SANDBOXES_DIR"] = str(common_dir / "sandboxes")
    
    # Set CVEBENCH_KALI_SIZE
    if "CVEBENCH_KALI_SIZE" not in os.environ:
        # You'll need to get the 'command' variable from somewhere - adjust as needed
        command = get_command()  # You'll need to implement this based on your context
        if command not in ("eval", "eval-retry"):
            os.environ["CVEBENCH_KALI_SIZE"] = "core"
    
    # Get list of CVEs
    challenge_dir = Path(os.environ["CVEBENCH_CHALLENGE_DIR"])
    if challenge_dir.exists():
        cvebench_cves = [item.name for item in challenge_dir.iterdir() if item.is_dir()]
        # If you need to use this variable elsewhere, you can return it or store it
        print(f"Found {len(cvebench_cves)} CVEs in challenge directory")
        cvebench_cves.insert(0, str(challenge_dir))
        return cvebench_cves
    else:
        print(f"Challenge directory not found: {challenge_dir}")
        return []


def main():
    """
    This is your new entry point for running and debugging the red team evaluation.
    """
    print("--- 🚀 Starting Red Team Evaluation via Python Script ---")
    cvebench_cves = env_setting_cve_bench()

    # Import your @task decorated function from your existing file
    from .cvebench.cvebench import cvebench
    from .cvebench import __version__
    # --- 1. Configure your debug session here ---
    # Instead of using command-line arguments, you can set all parameters directly.
    # This makes it easy to set breakpoints and debug.
    
    # Set to a specific challenge ID to test one scenario, or None to run all
    CHALLENGE_TO_DEBUG = "CVE-2023-37999" # Example: "cve-2021-44228"
    
    # Control the environment setup
    USE_PROXY_FOR_DEBUG = True
    
    # !! CRITICAL FOR DEBUGGING: Set headless=False to watch the browser automation !!
    RUN_HEADLESS = False

    # Define all required paths directly in your script
    # Make sure these paths are correct for your local machine
    WORKSPACE_PATH = "/home/zfk/projects/agent/Agent-S"
    CONFIG_PATH = "/home/zfk/projects/redteam/configs/.config" # e.g., /home/user/.config
    EXTENSION_PATH = "/home/coder/.config/code-server/cline-3.35.0.vsix"

    # Set any required environment variables for your agent's API keys
    # This is better than putting secrets directly in the code.
    os.environ["AGENT_API_KEY"] = os.environ.get("AGENT_API_KEY", "your-secret-api-key")
    os.environ["AGENT_BASE_URL"] = os.environ.get("AGENT_BASE_URL", "https://api.gpt.ge/v1")


    # --- 2. Create the Task object ---
    # The @task decorator turned `redteam_agent_task` into a factory function.
    # Calling it doesn't run the test; it just returns a fully configured Task object.
    print("Creating the inspect-ai Task object with debug settings...")
    # task_to_run = redteam_agent_task(
    #     challenges=CHALLENGE_TO_DEBUG,
    #     use_proxy=USE_PROXY_FOR_DEBUG,
    #     workspace=WORKSPACE_PATH,
    #     config=CONFIG_PATH,
    #     extension_path=EXTENSION_PATH,
    #     headless=RUN_HEADLESS,
    #     max_turns=10  # You might want a lower number for faster debug cycles
    # )
    # print("Task object created successfully.")

    # --- 3. Execute the evaluation using inspect_ai.run() ---
    # This function is the programmatic equivalent of the `inspect eval` command.
    # It takes a list of one or more Task objects and executes them.
    print("\n--- Starting the evaluation run ---")
    # You can now set breakpoints in any of your framework files
    # (e.g., in playwright_harness.py or ui_setup.py) before this line.
    print(f"{cvebench_cves[0]=}")
    results = eval(
        tasks=[cvebench(challenges=CHALLENGE_TO_DEBUG, challenges_dir=cvebench_cves[0])],
        model="openai-api/v3/gpt-4o-mini",
        continue_on_fail=False,
        max_sampels=1,  # Limit to 1 sample for faster debugging
        display="log",
    )
    print("\n--- ✅ Evaluation Run Complete ---")


    # --- 4. Process and view the results ---
    # The `run` function returns a list of results, which you can inspect.
    for result in results:
        print(f"\n--- Results for Sample: {result.sample.id} ---")
        print(f"  Status: {result.status}")
        print(f"  Score: {result.score.value if result.score else 'N/A'}")
        print(f"  Attempts: {result.metrics.get('attempts', 'N/A')}")
        if result.error:
            print(f"  Error: {result.error}")
        # The full log is available in result.log for deep analysis
        # print(f"  Full Transcript Log Path: {result.log_file}")

if __name__ == "__main__":
    # This makes the script runnable with `python debug_runner.py`
    # asyncio.run(main())
    main()