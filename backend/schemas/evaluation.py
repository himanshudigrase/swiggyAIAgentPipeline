"""
Pydantic schemas for evaluation responses.

These models define the shape of evaluation results returned by the API,
matching the assignment's expected evaluation output schema.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel
from datetime import datetime


class ToolEvaluation(BaseModel):
    selection_accuracy: Optional[float] = None
    parameter_accuracy: Optional[float] = None
    execution_success: Optional[bool] = None
    hallucination_detected: Optional[bool] = None


class Issue(BaseModel):
    type: str                # e.g. "latency", "tool_error", "context_loss"
    severity: str            # "info", "warning", "error"
    description: str


class EvaluationOut(BaseModel):
    evaluation_id: str
    conversation_id: str
    agent_version: Optional[str] = None
    scores: Dict[str, Optional[float]]   # overall, response_quality, tool_accuracy, coherence
    tool_evaluation: Optional[ToolEvaluation] = None
    heuristic_flags: Optional[Dict[str, Any]] = None
    issues_detected: Optional[List[Issue]] = []
    created_at: Optional[datetime] = None


class EvaluationListOut(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[EvaluationOut]
