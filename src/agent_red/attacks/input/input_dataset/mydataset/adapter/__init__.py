"""
Unified data_sample interface.

This module provides a clean, unified interface for loading and evaluating
tasks from the data_sample dataset.

Quick start:
    >>> from src.utils import DataSampleLoader, evaluate_single_sample
    >>> 
    >>> loader = DataSampleLoader()
    >>> task = loader.load_task("task a", "a1", "binary_classification")
    >>> 
    >>> for sample in task:
    >>>     agent_output = run_agent(sample.task_prompt)
    >>>     result = evaluate_single_sample(sample, agent_output)
    >>>     print(result)
"""

from .data_loader import (
    DataSampleLoader,
    TaskDataset,
    UnifiedSample,
    TaskMetadata,
    TaskCategory,
    TaskAdapter,
    TaskAAdapter,
    TaskBAdapter,
    TaskCAdapter,
    TaskDAdapter,
)

from .evaluator import (
    EvaluatorFactory,
    BaseEvaluator,
    LegacyEvaluatorWrapper,
    SimpleEvaluator,
    SecurityEvaluator,
    EvaluationResult,
    BatchEvaluationResult,
    evaluate_single_sample,
)

__all__ = [
    # Data loading
    "DataSampleLoader",
    "TaskDataset",
    "UnifiedSample",
    "TaskMetadata",
    "TaskCategory",
    "TaskAdapter",
    "TaskAAdapter",
    "TaskBAdapter",
    "TaskCAdapter",
    "TaskDAdapter",
    
    # Evaluation
    "EvaluatorFactory",
    "BaseEvaluator",
    "LegacyEvaluatorWrapper",
    "SimpleEvaluator",
    "SecurityEvaluator",
    "EvaluationResult",
    "BatchEvaluationResult",
    "evaluate_single_sample",
]

