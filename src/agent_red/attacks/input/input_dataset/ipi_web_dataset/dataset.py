import os
import pdb
import requests
import time
from typing import Callable, List
from .....custom_types import Sample, MemoryDataset
from .....utils.others import docker_write_str_to_file
from pathlib import Path
import json
from copy import deepcopy
    
data_base_dir = Path(__file__).parent.parent.parent.parent.parent.parent / "data" / "ipi_web_dataset"


def get_dataset(filter_dict: dict, dataset_transform: Callable | None = None):
    data_path = data_base_dir / "dataset.json"
    with open(data_path) as f:
        data = json.load(f)
    
    samples = data.get("samples", [])

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
            
            # Check severity filter
            if "severity" in filter_dict:
                if isinstance(filter_dict["severity"], list):
                    if sample.get("severity") not in filter_dict["severity"]:
                        continue
                elif sample.get("severity") != filter_dict["severity"]:
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
            user_instruction=sample["user_instruction"],
            id=sample["id"],
            metadata = sample,
            category=sample.get("category", ""),
            subcategory=sample.get("subcategory", ""),
        )
        for sample in samples
    ])

def get_container_preparation():
    def container_preparation(sample: Sample, container, web_port: int = 8084, attacker_port: int = 8085):
        # Retry logic with delays to handle web server not being ready
        max_attempts = 5
        retry_delay = 2  # seconds
        
        for attempt in range(1, max_attempts + 1):
            try:
                res = requests.get(
                    url=f"http://localhost:{web_port}/set-default?test={sample.id}&attacker_server=http://192.168.244.1:{attacker_port}",
                    timeout=10  # Add timeout to prevent hanging
                )
                if res.status_code != 200:
                    raise ValueError(f"Failed to set default test case in web server for sample id {sample.id}, status: {res.status_code}")
                # Success, break out of retry loop
                break
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                if attempt < max_attempts:
                    print(f"⚠️  Attempt {attempt}/{max_attempts} failed: {e.__class__.__name__}. Retrying in {retry_delay}s...")
                    time.sleep(retry_delay)
                else:
                    print(f"❌ All {max_attempts} attempts failed to connect to web server: http://localhost:{web_port}/set-default")
                    print(f"   Error: {e}")
                    raise e
            except Exception as e:
                print(f"❌ Unexpected error connecting to web server: {e}")
                raise e
                
        sample.user_instruction = sample.user_instruction.replace("{{ATTACKER_SERVER}}", f"http://192.168.244.1:{web_port}")
        auxiliary_files_paths = sample.metadata.get("auxiliary_files", "")
        auxiliary_files = [
            file.split("/")[-1]
            for file in auxiliary_files_paths
        ]
        auxiliary_files_dir = data_base_dir / "auxiliary_resources" / "mock_files"
        for file, file_path in zip(auxiliary_files, auxiliary_files_paths):
            with open(auxiliary_files_dir / file, "r") as f:
                target_str = f.read()
                docker_write_str_to_file(target_str, file_path, container=container)
    return container_preparation