__version__ = "2.0.0"

from .....custom_types import TaskState

from .cvebench import get_dataset

from .cvebench import check_exploit, check_target_server_for_exploit_success

import os
import sys
from pathlib import Path

def env_setting_cve_bench():
    def get_command():
        
        return "eval-solution"

    os.environ["CVEBENCH_TAG"] = __version__

    supported_versions = ("critical", "high-severity", "easy")
    
    # Set CVEBENCH_VERSION
    if "CVEBENCH_VERSION" not in os.environ:
        os.environ["CVEBENCH_VERSION"] = "critical"
    elif os.environ["CVEBENCH_VERSION"] not in supported_versions:
        print(f"Invalid version: {os.environ['CVEBENCH_VERSION']}. Valid versions are: {', '.join(supported_versions)}")
        sys.exit(1)
    
    cvebench_version = os.environ["CVEBENCH_VERSION"]
    
    # Set directory paths
    base_dir = Path(__file__).parent.parent.parent.parent.parent.parent  # Adjust based on your script location
    src_dir = base_dir / "data" / "cvebench"
    
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
        return cvebench_cves
    else:
        print(f"Challenge directory not found: {challenge_dir}")
        return []

env_setting_cve_bench()

current_dir = os.path.dirname(os.path.abspath(__file__))
CHALLENGES_DIR = os.environ.get('CVEBENCH_CHALLENGE_DIR', os.path.join(current_dir, "src", "critical", "challenges"))