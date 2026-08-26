import os
import pdb
from typing import Callable, List
from pathlib import Path
from .....utils.file_process import jsonl_dataset
    

data_dir = Path(__file__).parent.parent.parent.parent.parent.parent  # Adjust based on your script location

def get_dataset(filter_dict: dict, dataset_transform: Callable | None = None):
    if filter_dict:
        ids = filter_dict.get("ids", [])
        category = filter_dict.get("category", [])
        language = filter_dict.get("language", [])
        return (jsonl_dataset(os.path.join(data_dir, "data/redcode/redcode_exec_inspect_ai_format.jsonl"), dataset_transform)
                .filter(lambda sample: sample.id.split("_")[0] in category)
                .filter(lambda sample: sample.id.split("_")[1] in ids)
                .filter(lambda sample: sample.id.split("_")[2] in language)
        )
    else:
        return jsonl_dataset(os.path.join(data_dir, "data/redcode/redcode_exec_inspect_ai_format.jsonl"), dataset_transform)
    