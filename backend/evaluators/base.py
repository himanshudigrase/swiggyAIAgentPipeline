"""
Abstract base class for all evaluators.

All evaluators must implement the `evaluate` method, which receives
the raw conversation data (turns, feedback, metadata) and returns
a standardized result dict.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class EvaluatorResult:
    """Standardized result from any evaluator."""

    def __init__(
        self,
        evaluator_name: str,
        score: Optional[float],
        issues: Optional[List[Dict]] = None,
        details: Optional[Dict] = None,
    ):
        self.evaluator_name = evaluator_name
        self.score = score           # 0.0–1.0, or None if not applicable
        self.issues = issues or []   # List of { type, severity, description }
        self.details = details or {} # Evaluator-specific output (for JSONB storage)


class BaseEvaluator(ABC):
    """All evaluators must inherit from this."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable evaluator name."""

    @abstractmethod
    def evaluate(self, turns: List[Dict], feedback: Optional[Dict], metadata: Optional[Dict]) -> EvaluatorResult:
        """
        Evaluate and return a result.

        Args:
            turns: The conversation turns (list of dicts from DB)
            feedback: Feedback dict (user_rating, ops_review, annotations)
            metadata: Metadata dict (total_latency_ms, mission_completed, etc.)

        Returns:
            EvaluatorResult with score, issues, and details.
        """
