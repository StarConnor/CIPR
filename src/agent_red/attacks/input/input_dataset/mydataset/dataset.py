import os
import pdb
from typing import Callable, List
from .....custom_types import Sample, MemoryDataset
from pathlib import Path
import json
from copy import deepcopy
    
data_base_dir = Path(__file__).parent.parent.parent.parent.parent.parent / "data" / "data_sample"
a_data_dir = data_base_dir / "task a"  # Adjust based on your script location
b_data_dir = data_base_dir / "task b"
c_data_dir = data_base_dir / "task c"
d_data_dir = data_base_dir / "task d"

binary_classificatoin_path = a_data_dir / "a1" / "binary_classification" / "data.json"
vulnerability_classification_path = a_data_dir / "a1" / "vulnerability_classification" / "data.json"
vulnerability_localization_path = a_data_dir / "a1" / "vulnerability_localization" / "data.json"
cross_file_repair_path = a_data_dir / "a2" / "cross_file_repair" / "data.json"
function_level_repair_path = a_data_dir / "a2" / "function_level_repair" / "data.json"
single_line_repair_path = a_data_dir / "a2" / "single_line_repair" / "data.json"
function_body_completion_path = a_data_dir / "a3" / "function_body_completion" / "data.json"
line_completion_path = a_data_dir / "a3" / "line_completion" / "data.json"
middle_code_completion_path = a_data_dir / "a3" / "middle_code_completion" / "data.json"

malicious_file_content_path = b_data_dir / "b1" / "malicious_file_content" / "data.json"
malicious_issue_path = b_data_dir / "b1" / "malicious_issue" / "data.json"
path_injection_path = b_data_dir / "b1" / "path_injection" / "data.json"
malicious_command_execution_path = b_data_dir / "b2" / "malicious_command_execution" / "data.json"
multiline_command_injection_path = b_data_dir / "b2" / "multiline_command_injection" / "data.json"
network_dependency_path = b_data_dir / "b3" / "network_dependency" / "data.json"
mcp_tool_path = c_data_dir / "mcp_tool" / "data.json"
direct_prompt_injection_path = d_data_dir / "d1" / "direct_prompt_injection" / "data.json"
indirect_prompt_injection_path = d_data_dir / "d1" / "indirect_prompt_injection" / "data.json"
malicious_generation_refusal_path = d_data_dir / "d2" / "malicious_generation_refusal" / "data.json"

category_mapping = {
    "binary_classification": binary_classificatoin_path,
    "vulnerability_classification": vulnerability_classification_path,
    "vulnerability_localization": vulnerability_localization_path,
    "cross_file_repair": cross_file_repair_path,
    "function_level_repair": function_level_repair_path,
    "single_line_repair": single_line_repair_path,
    "function_body_completion": function_body_completion_path,
    "line_completion": line_completion_path,
    "middle_code_completion": middle_code_completion_path,
    "malicious_file_content": malicious_file_content_path,
    "malicious_issue": malicious_issue_path,
    "path_injection": path_injection_path,
    "malicious_command_execution": malicious_command_execution_path,
    "multiline_command_injection": multiline_command_injection_path,
    "network_dependency": network_dependency_path,
    "mcp_tool": mcp_tool_path,
    "direct_prompt_injection": direct_prompt_injection_path,
    "indirect_prompt_injection": indirect_prompt_injection_path,
    "malicious_generation_refusal": malicious_generation_refusal_path,
}
def get_dataset(category: str, filter_dict: dict, dataset_transform: Callable | None = None):
    if category in category_mapping:
        def extract_input(sample):
            output = []
            for key, value in sample['input'].items():
                if key == 'task_prompt':
                    output.append(value)
                else:
                    output.append(f"{key}:{value}")
            return '\n'.join(output)
        data_path = category_mapping[category]
    else:
        raise ValueError(f"Unknown category: {category}")
    with open(data_path) as f:
        data = json.load(f)
    samples = data.pop("samples", [])
    return MemoryDataset([
        dataset_transform(sample) if dataset_transform else Sample(
            user_instruction=extract_input(sample),
            id=sample["id"],
            metadata = data | deepcopy(sample),
            category=sample.get("category", ""),
            subcategory=sample.get("subcategory", ""),
        )
        for sample in samples
    ])
    