import json
import os
from typing import Dict, Optional, Any, List
from ...custom_types import PromptInjection, Sample

class SampleRegistry:
    def __init__(self, registry_path: str = "generated_dataset_dynamic.json"):
        # The user mentioned "generated_dataset_dynamic.json" in the file list earlier, maybe that's what they meant?
        # But the request says "create a new registry, 'reuse'".
        # I'll use a new file for now, or maybe the one the user seemingly pointed to.
        # Actually, "generated_dataset_dynamic.json" exists in workspace root.
        # Let's default to that for now if it's convenient, or a dedicated registry file.
        # Given "generated_dataset_dynamic.json" is in the root, I should probably use an absolute path or relative to CWD.
        self.registry_path = registry_path
        self.registry: Dict[str, Dict[str, Any]] = self._load_registry()

    def _load_registry(self) -> Dict[str, Dict[str, Any]]:
        if os.path.exists(self.registry_path):
            try:
                with open(self.registry_path, 'r') as f:
                    data = json.load(f)
                    # If the file is a list (like a dataset), convert to dict by ID for easier lookup
                    if isinstance(data, list):
                        return {item.get('id'): item for item in data if isinstance(item, dict) and 'id' in item}
                    return data
            except Exception:
                return {}
        return {}

    def _save_registry(self):
        # We want to save it back. If it was a list, we should probably maintain that structure?
        # But for key-value access, a dict is better.
        # If the user wants to use this as a dataset later, a list of samples is standard.
        # Let's save as a list of values.
        
        data_to_save = list(self.registry.values())
        try:
            with open(self.registry_path, 'w') as f:
                json.dump(data_to_save, f, indent=2)
        except Exception as e:
            print(f"Failed to save registry: {e}")

    def save_sample(self, sample: Any):
        """
        Saves the complete sample to the registry, excluding metadata.
        """
        if hasattr(sample, 'model_dump'):
            data = sample.model_dump()
        elif hasattr(sample, 'dict'):
            data = sample.dict()
        else:
            # Assume it's a dict or similar
            try:
                data = dict(sample)
            except (TypeError, ValueError):
                # If we really can't convert, maybe it's just an object we can't handle easily without more info
                # But Sample is a Pydantic model usually.
                print(f"Warning: Could not convert sample {sample} to dict.")
                return

        # Ensure ID is present
        sample_id = data.get('id')
        if not sample_id:
            print("Warning: Sample has no ID, cannot save to registry.")
            return
        
        # Exclude metadata
        if 'metadata' in data:
            del data['metadata']
            
        self.registry[sample_id] = data
        self._save_registry()

    def get_sample(self, sample_id: str) -> Optional[Sample]:
        """
        Retrieves a Sample object from the registry.
        """
        data = self.registry.get(sample_id)
        if data:
            try:
                # The prompt_injections list of dicts will be automatically converted 
                # to PromptInjection objects by Pydantic validation if Sample defines them as such.
                return Sample(**data)
            except Exception as e:
                print(f"Warning: Failed to reconstruct Sample {sample_id} from registry: {e}")
                return None
        return None

    def get_sample_injections(self, sample_id: str) -> Optional[List[Dict[str, Any]]]:
        entry = self.registry.get(sample_id)
        if entry and 'prompt_injections' in entry:
            return entry['prompt_injections']
        return None

# Singleton instance
# using absolute path for safety to point to workspace root
REGISTRY_PATH = os.path.abspath("generated_dataset_dynamic.json")
REGISTRY = SampleRegistry(REGISTRY_PATH)
