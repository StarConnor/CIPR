from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Protocol

from ..custom_types import Sample


@dataclass
class AttackAttempt:
    """Represents a single attack attempt to run through the solver."""
    sample: Optional[Sample]
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AttackFeedback:
    """Feedback from a failed attempt used to regenerate the next attempt."""
    status: str  # e.g., "success" or "error"
    messages: List[str] = field(default_factory=list)
    env: Dict[str, Any] = field(default_factory=dict)
    scorer: Dict[str, Any] = field(default_factory=dict)


class AttackSession(Protocol):
    """
    Abstract interface for iterative attacks.
    Implementations can be one-shot (return None on next_attempt) or regenerative.
    """

    def start(self, sample: Sample) -> AttackAttempt:
        ...

    def next_attempt(self, feedback: AttackFeedback) -> Optional[AttackAttempt]:
        ...


class RegenerativeSessionBase(AttackSession):
    """
    Helper base for attacks that regenerate based on feedback.
    Subclasses implement _build_attempt(feedback, attempt_idx).
    """

    def __init__(self, max_rounds: int = 3):
        self.max_rounds = max_rounds
        self.attempt_idx = 0
        self._last_feedback: Optional[AttackFeedback] = None

    def start(self, sample: Sample) -> AttackAttempt:
        self.attempt_idx = 0
        self._last_feedback = None
        return self._build_attempt(sample, feedback=None, attempt_idx=self.attempt_idx)

    def next_attempt(self, feedback: AttackFeedback) -> Optional[AttackAttempt]:
        self._last_feedback = feedback
        self.attempt_idx += 1
        if self.attempt_idx >= self.max_rounds:
            return None
        return self._build_attempt(None, feedback=feedback, attempt_idx=self.attempt_idx)

    def _build_attempt(
        self,
        sample: Optional[Sample],
        feedback: Optional[AttackFeedback],
        attempt_idx: int,
    ) -> AttackAttempt:
        raise NotImplementedError
