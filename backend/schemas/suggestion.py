"""Pydantic schemas for improvement suggestion endpoints."""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from datetime import datetime


class SuggestionOut(BaseModel):
    suggestion_id: str
    suggestion_type: str       # "prompt" or "tool"
    target: Optional[str]      # e.g. "flight_search", "date_format_instruction"
    suggestion_text: str
    rationale: Optional[str]
    expected_impact: Optional[str]
    confidence: float
    failure_pattern: Optional[Dict[str, Any]]
    status: str                # "pending", "applied", "dismissed"
    created_at: Optional[datetime]


class SuggestionListOut(BaseModel):
    total: int
    items: List[SuggestionOut]


class GenerateSuggestionsRequest(BaseModel):
    agent_version: Optional[str] = None   # Filter to specific version
    window: int = 100                     # How many recent evals to scan


class CalibrationMetric(BaseModel):
    evaluator_name: str
    metric: str
    total_comparisons: int
    agreement_pct: float
    avg_delta: Optional[float]


class CalibrationReport(BaseModel):
    total_calibration_points: int
    metrics: List[CalibrationMetric]
    generated_at: datetime
