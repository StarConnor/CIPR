import os
import pdb
import json
import random
from typing import Callable, List, Dict, Any
from ..custom_types import MemoryDataset, Sample
from ..scorer import default_scorer

DEFAULT_ISSUE_TEMPLATE = """
Here is the issue description:
{issue_text}
Now help me fix it."""


def default_dataset_transform(sample_dict: Dict[str, Any]) -> Sample:
    if 'user_instruction' in sample_dict and sample_dict['user_instruction'] is None and 'raw_meta' in sample_dict and 'raw_issue_text' in sample_dict['raw_meta']:
        sample_dict['user_instruction'] = DEFAULT_ISSUE_TEMPLATE.format(issue_text=sample_dict['raw_meta']['raw_issue_text'])
    if 'id' not in sample_dict and 'base_id' in sample_dict:
        sample_dict['id'] = sample_dict['base_id']
    if 'category' not in sample_dict and not sample_dict['evaluation']['attack_success_check']:
        sample_dict['category'] = 'Benign'
        sample_dict['subcategory'] = 'Benign'
    if 'metadata' not in sample_dict and 'raw_meta' in sample_dict:
        sample_dict['metadata'] = sample_dict['raw_meta']
    return Sample(**sample_dict)


def load_dataset(dataset_name: str, dataset_base_path: str, filter_dict: Dict[str, Any] = {}, dataset_transform: Callable = default_dataset_transform, k_runs: int = 1, sample_n: int = -1) -> List[Sample]:
    data_path = os.path.join(dataset_base_path, dataset_name, "dataset.json")
    with open(data_path) as f:
        data = json.load(f)
    
    if "samples" in data:
        samples = data.get("samples", [])
    elif "data" in data:
        samples = data["data"]
    else:
        samples = data
    
    if sample_n > 0:
        random.seed(42)  # For reproducibility
        samples = random.sample(samples, min(sample_n, len(samples)))
    
    if k_runs > 1:
        expanded_samples = []
        for sample in samples:
            for i in range(k_runs):
                new_sample = sample.copy()
                new_sample['id'] = f"{sample['id']}_run_{i+1}"
                expanded_samples.append(new_sample)
        samples = expanded_samples
    
    memory_dataset = MemoryDataset([
        dataset_transform(sample) if dataset_transform else Sample(
            **sample
        )
        for sample in samples]
    )

    # Apply filters based on filter_dict
    if filter_dict:
        for key, value in filter_dict.items():
            memory_dataset = memory_dataset.filter(lambda sample: getattr(sample, key) in value if isinstance(value, list) else getattr(sample, key) == value)
    
    return memory_dataset.samples


# FIXME: this is a hack to load scorer, should be refactored later
def load_scorer(dataset_name: str, dataset_base_path: str, filter_dict: Dict[str, Any] = {}) -> Callable[..., List[Any]] | None:
    return default_scorer