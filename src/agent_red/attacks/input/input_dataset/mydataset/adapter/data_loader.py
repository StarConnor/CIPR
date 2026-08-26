"""
Unified interface for loading and processing data_sample tasks.

This module provides a clean, consistent interface for loading different task types
from the data_sample directory, normalizing their structure, and providing one-by-one
sample iteration instead of batch processing.
"""

from pathlib import Path
from typing import Dict, Any, List, Iterator, Optional, Callable
from abc import ABC, abstractmethod
import json
from dataclasses import dataclass, field
from enum import Enum


class TaskCategory(Enum):
    """Categories of tasks in data_sample."""
    TASK_A = "task a"  # Code security analysis tasks
    TASK_B = "task b"  # Malicious content detection tasks
    TASK_C = "task c"  # MCP tool security tasks
    TASK_D = "task d"  # Prompt injection tasks


@dataclass
class UnifiedSample:
    """
    Unified representation of a single sample across all task types.
    
    Attributes:
        id: Unique identifier for the sample
        task_prompt: The normalized user instruction/prompt for the task
        input_data: Additional structured input data (code, files, context, etc.)
        expected_output: Expected result for evaluation
        ground_truth: Alternative ground truth data (for some tasks)
        security_constraints: Security rules and constraints (for task b/d)
        metadata: Additional metadata (source, attack_type, etc.)
        task_type: Type of task (e.g., "binary_classification", "malicious_file_content")
        category: High-level category (task a/b/c/d)
    """
    id: str
    task_prompt: str
    input_data: Dict[str, Any] = field(default_factory=dict)
    expected_output: Optional[Dict[str, Any]] = None
    ground_truth: Optional[Dict[str, Any]] = None
    security_constraints: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    task_type: Optional[str] = None
    category: Optional[str] = None
    
    def get_full_prompt(self) -> str:
        """Get the complete prompt including all input data as context."""
        parts = [self.task_prompt]
        
        # Add relevant input data as context
        if "code" in self.input_data:
            parts.append(f"\nCode:\n{self.input_data['code']}")
        if "file_to_analyze" in self.input_data:
            file_info = self.input_data["file_to_analyze"]
            parts.append(f"\nFile: {file_info.get('path', 'N/A')}")
            parts.append(f"Content:\n{file_info.get('content', '')}")
        if "environment" in self.input_data:
            env = self.input_data["environment"]
            parts.append(f"\nEnvironment: {env.get('cwd', 'N/A')}")
            parts.append(f"Files: {', '.join(env.get('file_structure', []))}")
        if "system_context" in self.input_data:
            ctx = self.input_data["system_context"]
            parts.append(f"\nSystem Role: {ctx.get('role', 'N/A')}")
            parts.append(f"Constraints: {ctx.get('constraints', 'N/A')}")
        
        return "\n".join(parts)


@dataclass
class TaskMetadata:
    """Metadata about the entire task/dataset."""
    task_type: str
    description: str
    evaluation_method: str
    evaluation_metrics: List[str]
    category: str
    total_samples: int


class TaskAdapter(ABC):
    """Base adapter for converting task-specific formats to UnifiedSample."""
    
    @abstractmethod
    def adapt_sample(self, raw_sample: Dict[str, Any], task_metadata: Dict[str, Any]) -> UnifiedSample:
        """Convert a raw sample to UnifiedSample format."""
        pass
    
    @abstractmethod
    def get_prompt_field(self, raw_input: Dict[str, Any]) -> str:
        """Extract the prompt/instruction from raw input."""
        pass


class TaskAAdapter(TaskAdapter):
    """Adapter for Task A (code security analysis) samples."""
    
    def get_prompt_field(self, raw_input: Dict[str, Any]) -> str:
        """Task A uses 'task_prompt' field."""
        return raw_input.get("task_prompt", "")
    
    def adapt_sample(self, raw_sample: Dict[str, Any], task_metadata: Dict[str, Any]) -> UnifiedSample:
        raw_input = raw_sample.get("input", {})
        
        # Extract task prompt and other input fields
        task_prompt = self.get_prompt_field(raw_input)
        input_data = {k: v for k, v in raw_input.items() if k != "task_prompt"}
        
        return UnifiedSample(
            id=raw_sample.get("id", ""),
            task_prompt=task_prompt,
            input_data=input_data,
            expected_output=raw_sample.get("expected_output"),
            metadata=raw_sample.get("metadata", {}),
            task_type=task_metadata.get("task_type"),
            category=TaskCategory.TASK_A.value
        )


class TaskBAdapter(TaskAdapter):
    """Adapter for Task B (malicious content detection) samples."""
    
    def get_prompt_field(self, raw_input: Dict[str, Any]) -> str:
        """Task B uses 'task_prompt' field."""
        return raw_input.get("task_prompt", "")
    
    def adapt_sample(self, raw_sample: Dict[str, Any], task_metadata: Dict[str, Any]) -> UnifiedSample:
        raw_input = raw_sample.get("input", {})
        
        task_prompt = self.get_prompt_field(raw_input)
        input_data = {k: v for k, v in raw_input.items() if k != "task_prompt"}
        
        return UnifiedSample(
            id=raw_sample.get("id", ""),
            task_prompt=task_prompt,
            input_data=input_data,
            expected_output=raw_sample.get("expected_output"),
            security_constraints=raw_sample.get("security_constraints"),
            metadata=raw_sample.get("metadata", {}),
            task_type=task_metadata.get("task_type"),
            category=TaskCategory.TASK_B.value
        )


class TaskCAdapter(TaskAdapter):
    """Adapter for Task C (MCP tool security) samples."""
    
    def get_prompt_field(self, raw_input: Dict[str, Any]) -> str:
        """Task C uses 'task_prompt' field."""
        return raw_input.get("task_prompt", "")
    
    def adapt_sample(self, raw_sample: Dict[str, Any], task_metadata: Dict[str, Any]) -> UnifiedSample:
        raw_input = raw_sample.get("input", {})
        
        task_prompt = self.get_prompt_field(raw_input)
        input_data = {k: v for k, v in raw_input.items() if k != "task_prompt"}
        
        return UnifiedSample(
            id=raw_sample.get("id", ""),
            task_prompt=task_prompt,
            input_data=input_data,
            ground_truth=raw_sample.get("ground_truth"),
            metadata=raw_sample.get("metadata", {}),
            task_type=task_metadata.get("task_type"),
            category=TaskCategory.TASK_C.value
        )


class TaskDAdapter(TaskAdapter):
    """Adapter for Task D (prompt injection) samples."""
    
    def get_prompt_field(self, raw_input: Dict[str, Any]) -> str:
        """Task D uses 'user_prompt' field."""
        return raw_input.get("user_prompt", "")
    
    def adapt_sample(self, raw_sample: Dict[str, Any], task_metadata: Dict[str, Any]) -> UnifiedSample:
        raw_input = raw_sample.get("input", {})
        
        task_prompt = self.get_prompt_field(raw_input)
        input_data = {k: v for k, v in raw_input.items() if k != "user_prompt"}
        
        return UnifiedSample(
            id=raw_sample.get("id", ""),
            task_prompt=task_prompt,
            input_data=input_data,
            expected_output=raw_sample.get("expected_output"),
            security_constraints=raw_sample.get("security_constraints"),
            metadata=raw_sample.get("metadata", {}),
            task_type=task_metadata.get("task_type"),
            category=TaskCategory.TASK_D.value
        )


class DataSampleLoader:
    """
    Unified loader for data_sample tasks with one-by-one sample iteration.
    
    Usage:
        # Load a specific task
        loader = DataSampleLoader(data_dir="/path/to/data/data_sample")
        task = loader.load_task("task a", "a1", "binary_classification")
        
        # Iterate through samples one by one
        for sample in task:
            process_sample(sample)
        
        # Or get a specific sample
        sample = task.get_sample(0)
        
        # Get task metadata
        metadata = task.metadata
    """
    
    def __init__(self, data_dir: Optional[Path] = None):
        """
        Initialize the loader.
        
        Args:
            data_dir: Path to data_sample directory. If None, auto-detect from project structure.
        """
        if data_dir is None:
            # Auto-detect from project structure
            current_file = Path(__file__)
            project_root = current_file.parent.parent.parent
            data_dir = project_root / "data" / "data_sample"
        
        self.data_dir = Path(data_dir)
        
        # Map categories to adapters
        self.adapters = {
            TaskCategory.TASK_A.value: TaskAAdapter(),
            TaskCategory.TASK_B.value: TaskBAdapter(),
            TaskCategory.TASK_C.value: TaskCAdapter(),
            TaskCategory.TASK_D.value: TaskDAdapter(),
        }
    
    def load_task(
        self,
        category: str,
        subcategory: str,
        task_name: str,
        filter_fn: Optional[Callable[[UnifiedSample], bool]] = None
    ) -> 'TaskDataset':
        """
        Load a specific task dataset.
        
        Args:
            category: Main category (e.g., "task a", "task b", "task c", "task d")
            subcategory: Subcategory (e.g., "a1", "b1", "c1", "d1")
            task_name: Specific task name (e.g., "binary_classification")
            filter_fn: Optional function to filter samples
        
        Returns:
            TaskDataset object for iteration
        """
        task_path = self.data_dir / category / subcategory / task_name / "data.json"
        
        if not task_path.exists():
            raise FileNotFoundError(f"Task data not found: {task_path}")
        
        with open(task_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # Get appropriate adapter
        adapter = self.adapters.get(category)
        if adapter is None:
            raise ValueError(f"Unknown category: {category}")
        
        # Convert all samples
        raw_samples = data.get("samples", [])
        unified_samples = []
        
        for raw_sample in raw_samples:
            unified_sample = adapter.adapt_sample(raw_sample, data)
            if filter_fn is None or filter_fn(unified_sample):
                unified_samples.append(unified_sample)
        
        # Create metadata
        metadata = TaskMetadata(
            task_type=data.get("task_type", ""),
            description=data.get("description", ""),
            evaluation_method=data.get("evaluation", {}).get("method", ""),
            evaluation_metrics=data.get("evaluation", {}).get("metrics", []),
            category=category,
            total_samples=len(unified_samples)
        )
        
        return TaskDataset(
            samples=unified_samples,
            metadata=metadata,
            task_path=task_path
        )
    
    def list_available_tasks(self) -> Dict[str, List[str]]:
        """
        List all available tasks organized by category.
        
        Returns:
            Dictionary mapping category -> list of task paths
        """
        tasks = {}
        
        for category_dir in self.data_dir.iterdir():
            if not category_dir.is_dir():
                continue
            
            category_name = category_dir.name
            tasks[category_name] = []
            
            # Find all data.json files
            for data_file in category_dir.rglob("data.json"):
                # Get relative path from category
                rel_path = data_file.relative_to(category_dir)
                task_path = str(rel_path.parent)
                tasks[category_name].append(task_path)
        
        return tasks


class TaskDataset:
    """
    Represents a loaded task dataset with one-by-one iteration support.
    """
    
    def __init__(
        self,
        samples: List[UnifiedSample],
        metadata: TaskMetadata,
        task_path: Path
    ):
        self.samples = samples
        self.metadata = metadata
        self.task_path = task_path
        self._current_index = 0
    
    def __len__(self) -> int:
        """Get total number of samples."""
        return len(self.samples)
    
    def __iter__(self) -> Iterator[UnifiedSample]:
        """Iterate through samples one by one."""
        for sample in self.samples:
            yield sample
    
    def __getitem__(self, index: int) -> UnifiedSample:
        """Get sample by index."""
        return self.samples[index]
    
    def get_sample(self, index: int) -> UnifiedSample:
        """Get a specific sample by index."""
        if index < 0 or index >= len(self.samples):
            raise IndexError(f"Sample index {index} out of range [0, {len(self.samples)})")
        return self.samples[index]
    
    def get_sample_by_id(self, sample_id: str) -> Optional[UnifiedSample]:
        """Get a sample by its ID."""
        for sample in self.samples:
            if sample.id == sample_id:
                return sample
        return None
    
    def filter(self, predicate: Callable[[UnifiedSample], bool]) -> 'TaskDataset':
        """
        Create a new TaskDataset with filtered samples.
        
        Args:
            predicate: Function that returns True for samples to keep
        
        Returns:
            New TaskDataset with filtered samples
        """
        filtered_samples = [s for s in self.samples if predicate(s)]
        new_metadata = TaskMetadata(
            task_type=self.metadata.task_type,
            description=self.metadata.description,
            evaluation_method=self.metadata.evaluation_method,
            evaluation_metrics=self.metadata.evaluation_metrics,
            category=self.metadata.category,
            total_samples=len(filtered_samples)
        )
        return TaskDataset(filtered_samples, new_metadata, self.task_path)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert dataset back to original format for evaluation."""
        return {
            "task_type": self.metadata.task_type,
            "description": self.metadata.description,
            "evaluation": {
                "method": self.metadata.evaluation_method,
                "metrics": self.metadata.evaluation_metrics
            },
            "samples": [self._sample_to_dict(s) for s in self.samples]
        }
    
    def _sample_to_dict(self, sample: UnifiedSample) -> Dict[str, Any]:
        """Convert UnifiedSample back to original format."""
        result = {
            "id": sample.id,
            "metadata": sample.metadata
        }
        
        # Reconstruct input
        input_data = dict(sample.input_data)
        
        # Add the prompt field based on category
        if sample.category == TaskCategory.TASK_D.value:
            input_data["user_prompt"] = sample.task_prompt
        else:
            input_data["task_prompt"] = sample.task_prompt
        
        result["input"] = input_data
        
        # Add optional fields
        if sample.expected_output is not None:
            result["expected_output"] = sample.expected_output
        if sample.ground_truth is not None:
            result["ground_truth"] = sample.ground_truth
        if sample.security_constraints is not None:
            result["security_constraints"] = sample.security_constraints
        
        return result

