from abc import ABC, abstractmethod
from typing import Any

class BaseExecutionEnvironment(ABC):
    """Interface for a stateful execution environment (e.g., Docker, a VM, or a mock)."""

    @abstractmethod
    def setup(self):
        """Prepares the environment (e.g., starts the container)."""
        pass

    @abstractmethod
    def teardown(self, log_path: str | None = None):
        """Cleans up the environment (e.g., stops the container)."""
        pass

    @abstractmethod
    def execute_tool(self, tool_name: str, **kwargs) -> str:
        """Executes a defined tool within the environment and returns the string observation."""
        pass

    @abstractmethod
    def get_state(self) -> Any:
        """
        Returns a snapshot of the environment's final state for evaluation.
        Could be a dict of file contents, network logs, etc.
        """
        pass

    @abstractmethod
    def init_task(self):
        """
        Initializes the environment with any necessary setup for the task.
        This could include seeding files, setting environment variables, etc.
        """
        pass

    def __enter__(self):
        self.setup()
        self.init_task()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.teardown()