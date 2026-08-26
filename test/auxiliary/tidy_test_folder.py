import os
import re
import shutil
from pathlib import Path

# Current directory
current_dir = Path("/home/zfk/projects/demo/code-agent-redteam/test/exp/dataset")

# Match pattern
pattern = re.compile(r'^(.+)-gemini-3-flash-(.+)-(\d+)$')

# Iterate over the current directory
for folder in current_dir.iterdir():
    if not folder.is_dir():
        continue
    
    match = pattern.match(folder.name)
    if not match:
        continue
    
    agent_name = match.group(1)
    dataset_name = match.group(2)
    llm_name = "gemini-3-flash" + "-" + match.group(3)
    
    # Build the target path
    target_dir = current_dir / agent_name / dataset_name 
    
    # Create the target directory
    target_dir.mkdir(parents=True, exist_ok=True)
    
    # Move the folder
    shutil.move(str(folder), str(target_dir))
    os.rename(target_dir / folder.name, target_dir / llm_name)
    
    print(f"Move complete: {folder.name} -> {target_dir}")

print("All folders processed!")