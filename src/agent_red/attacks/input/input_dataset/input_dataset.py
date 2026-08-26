from typing import Callable, List
from pathlib import Path
import json

import docker
from ....custom_types import ScoreResult, Sample, MemoryDataset
from ....scorer import default_scorer
# from .cvebench import get_dataset as get_cvebench_dataset
# from .cvebench.cvebench import check_exploit as check_exploit_cvebench, check_target_server_for_exploit_success, STORE_KEY_ATTACK_SUCCESSFUL as STORE_KEY_ATTACK_SUCCESSFUL_CVEBENCH
from .redcode.dataset import get_dataset as get_redcode_dataset
from .redcode.scorer import get_evaluation as get_evaluation_redcode, STORE_KEY_ATTACK_SUCCESSFUL as STORE_KEY_ATTACK_SUCCESSFUL_REDCODE

from .swebench.dataset import get_dataset as get_swebench_dataset, get_container_preparation as get_swebench_container_preparation
from .swebench.scorer import get_evaluation as get_evaluation_swebench

from .mydataset.dataset import get_dataset as get_my_dataset_dataset
from .mydataset.scorer import get_evaluation as get_evaluation_mydataset

from .ipi_web_dataset.dataset import get_dataset as get_ipi_web_dataset, get_container_preparation as get_ipi_web_dataset_container_preparation
from .ipi_web_dataset.scorer import get_evaluation as get_evaluation_ipi_web_dataset

from .ipi_file_dataset.dataset import get_dataset as get_ipi_file_dataset

from .base_dataset.dataset import get_dataset as get_base_dataset
from functools import partial

get_dataset_mapping_dict = {
    # "cvebench": get_cvebench_dataset,
    "redcode": get_redcode_dataset,
    "swebench": get_swebench_dataset,
    "ipi_web_dataset": get_ipi_web_dataset,
    "ipi_file_dataset": get_ipi_file_dataset,
    "base_dataset": get_base_dataset
}

get_dataset_scorer_mapping_dict = {
    # "cvebench": check_exploit_cvebench(key=STORE_KEY_ATTACK_SUCCESSFUL_CVEBENCH, check_function=check_target_server_for_exploit_success),
    "redcode": get_evaluation_redcode(),
    "swebench": get_evaluation_swebench(),
    "ipi_web_dataset": get_evaluation_ipi_web_dataset(),
}

def get_dataset_mapping(dataset_name: str):
    if dataset_name in get_dataset_mapping_dict:
        return get_dataset_mapping_dict[dataset_name]
    else:
        if dataset_name.startswith("mydataset"):
            return partial(get_my_dataset_dataset, category="_".join(dataset_name.split("_")[1:]))
        else:
            return partial(get_dataset, dataset_name=dataset_name)
        raise ValueError(f"Dataset {dataset_name} not found")


def get_dataset_scorer(dataset_name: str) -> Callable[..., List[ScoreResult]]:
    if dataset_name in get_dataset_scorer_mapping_dict:
        return get_dataset_scorer_mapping_dict[dataset_name]
    else:
        if dataset_name.startswith("mydataset"):
            return get_evaluation_mydataset(category="_".join(dataset_name.split("_")[1:]))
        return default_scorer


data_base_dir = Path(__file__).parent.parent.parent.parent.parent / "data"
def get_dataset(filter_dict: dict, dataset_name: str, dataset_transform: Callable | None = None):
    data_path = data_base_dir / dataset_name / "dataset.json"
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
        )
        for sample in samples
    ])
