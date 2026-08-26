import os
import pdb
import requests
from typing import Callable, List
from .....custom_types import Sample, MemoryDataset, PromptInjection, VerificationConfig
from .....config import BASE_WORKSPACE_PATH
from .....utils.others import docker_write_str_to_file
from pathlib import Path
import json
from copy import deepcopy
    
data_path = Path(__file__).parent.parent.parent.parent.parent.parent / "data" / "ipi_file_dataset" / "dataset.json"


def get_dataset(filter_dict: dict, dataset_transform: Callable | None = None, data_base_path: str = str(data_path)):
    with open(data_path) as f:
        data = json.load(f)
    
    if "samples" in data:
        samples = data.get("samples", [])
    else:
        samples = data

    # Apply filters based on filter_dict
    if filter_dict:
        filtered_samples = []
        for sample in samples:
            # Check category filter
            if "category" in filter_dict:
                if isinstance(filter_dict["category"], list):
                    if sample.get("category") not in filter_dict["category"]:
                        continue
                elif sample.get("category") != filter_dict["category"]:
                    continue
            
            # Check subcategory filter
            if "subcategory" in filter_dict:
                if isinstance(filter_dict["subcategory"], list):
                    if sample.get("subcategory") not in filter_dict["subcategory"]:
                        continue
                elif sample.get("subcategory") != filter_dict["subcategory"]:
                    continue
            
            # Check id filter (for specific test cases)
            if "id" in filter_dict:
                if isinstance(filter_dict["id"], list):
                    if sample.get("id") not in filter_dict["id"]:
                        continue
                elif sample.get("id") != filter_dict["id"]:
                    continue
            
            # If all filters pass, include the sample
            filtered_samples.append(sample)
        
        samples = filtered_samples

    return MemoryDataset([
        dataset_transform(sample) if dataset_transform else Sample(
            **sample
            # user_instruction=sample["user_instruction"],
            # id=sample["id"],
            # metadata = sample,
            # custom_html_content=sample.get("custom_html_content", None),
            # env_setup_script=sample.get("env_setup_script", ""),
            # workspace=sample.get("workspace", "itchat"),
            # script_to_fetch_from_attacker_server=sample.get("script_to_be_fetch_from_attacker_server", ""),
            # prompt_injections=sample.get("prompt_injections", []),
            # evaluation={
            #     "attack_success_check": [
            #         VerificationConfig(
            #             method=verif["method"],
            #             params=verif.get("params", {})
            #         ) for verif in sample.get("evaluation", {}).get("attack_success_check", [])
            #     ],
            #     "task_success_check": [
            #         VerificationConfig(
            #             method=verif["method"],
            #             params=verif.get("params", {})
            #         ) for verif in sample.get("evaluation", {}).get("task_success_check", [])
            #     ],
            # } if "evaluation" in sample else None,
            # category=sample.get('category', 'dl'),
            # subcategory=sample.get('subcategory', 'cl')
        )
        for sample in samples
    ])
