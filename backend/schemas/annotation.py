"""Pydantic schemas for annotation/feedback endpoints."""

from typing import Optional
from pydantic import BaseModel, Field
from datetime import datetime


class AnnotationIn(BaseModel):
    conversation_id: str
    annotator_id: str
    annotation_type: str       # e.g. "tool_accuracy", "helpfulness"
    label: str                 # e.g. "correct", "incorrect"
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    notes: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "conversation_id": "conv_abc123",
                "annotator_id": "ann_001",
                "annotation_type": "tool_accuracy",
                "label": "correct",
                "confidence": 0.9,
                "notes": "Tool selection was appropriate"
            }
        }


class AnnotationOut(BaseModel):
    id: str
    conversation_id: str
    annotator_id: str
    annotation_type: str
    label: str
    confidence: float
    notes: Optional[str]
    routing_decision: Optional[str]
    created_at: Optional[datetime]


class AgreementReport(BaseModel):
    conversation_id: str
    annotation_type: str
    num_annotators: int
    agreement_pct: float
    cohen_kappa: Optional[float]
    routing_decision: str     # "auto_labeled", "human_review", "tiebreaker"
    labels: list
