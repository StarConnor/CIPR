import os
from pathlib import Path
import pdb
import logging

from src.environment_manager import EnvironmentManager

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def main():
    WORKSPACE_PATH = os.path.join(Path(__file__).parent.parent.parent, "temp_workspace")
    CONFIG_PATH = os.path.join(Path(__file__).parent.parent.parent, "configs/.config")
    EXTENSION_PATH = "/home/coder/.config/code-server/cline-3.35.0.vsix"

    # Create temporary directories
    workspace_path = WORKSPACE_PATH
    config_path = CONFIG_PATH
    
    logger.info(f"Using workspace path: {workspace_path}")
    logger.info(f"Using config path: {config_path}")
    
    
    # Create EnvironmentManager
    env_manager = EnvironmentManager(
        use_proxy=True,
        workspace_path=workspace_path,
        config_path=config_path,
        project_name="test"
    )

    env_manager.setup()
    # pdb.set_trace()

if __name__ == "__main__":
    main()