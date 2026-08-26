from pydantic import BaseModel
from typing import Optional

class Injection(BaseModel):
    target_file_path: str
    injection_type: str
    match_pattern: str
    payload_content: Optional[str] = ""
    injection_script: Optional[str] = ""
    craft_method: Optional[str] = ""
    raw_payload: Optional[str] = ""

REPO_SRC_BASE_PATH = "/home/zfk/projects/benchmark/code-agent-redteam-dataset/prepare_dataset/data/repos/workspaces"
