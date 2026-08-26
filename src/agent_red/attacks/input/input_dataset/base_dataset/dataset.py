from typing import Callable, List
from .....custom_types import Sample, MemoryDataset, PromptInjection, VerificationConfig
from pathlib import Path
import json
    
data_base_dir = Path(__file__).parent.parent.parent.parent.parent.parent / "data" / "base_dataset"


def get_dataset(filter_dict: dict, dataset_transform: Callable | None = None):
    data_path = data_base_dir / "dataset.json"
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
