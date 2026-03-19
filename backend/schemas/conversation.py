"""
Pydantic schemas for conversation ingestion.

These models validate the input payload and match the assignment's
sample conversation schema exactly.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime


# ── Inner models (nested inside turns) ───────────────────────────────────────

class ToolCall(BaseModel):
    tool_name: str
    parameters: Dict[str, Any] = {}
    result: Optional[Dict[str, Any]] = None
    latency_ms: Optional[float] = None


class Turn(BaseModel):
    turn_id: int
    role: str                         # "user" or "assistant"
    content: str
    tool_calls: Optional[List[ToolCall]] = None
    timestamp: Optional[datetime] = None


class OpsReview(BaseModel):
    quality: Optional[str] = None    # e.g. "good", "poor"
    notes: Optional[str] = None


class HumanAnnotation(BaseModel):
    type: str                        # e.g. "tool_accuracy", "helpfulness"
    label: str                       # e.g. "correct", "incorrect"
    annotator_id: str
    confidence: Optional[float] = 1.0
    notes: Optional[str] = None


class Feedback(BaseModel):
    user_rating: Optional[int] = Field(None, ge=1, le=5)
    ops_review: Optional[OpsReview] = None
    annotations: Optional[List[HumanAnnotation]] = []


class ConversationMetadata(BaseModel):
    total_latency_ms: Optional[float] = None
    mission_completed: Optional[bool] = None


# ── Top-level input schema ─────────────────────────────────────────────────

class ConversationIn(BaseModel):
    """Matches the assignment's sample conversation schema."""
    conversation_id: str
    agent_version: Optional[str] = None
    turns: List[Turn]
    feedback: Optional[Feedback] = None
    metadata: Optional[ConversationMetadata] = None

    class Config:
        json_schema_extra = {
            "example": {
                "conversation_id": "conv_abc123",
                "agent_version": "v2.3.1",
                "turns": [
                    {
                        "turn_id": 1,
                        "role": "user",
                        "content": "I need to book a flight to NYC next week",
                        "timestamp": "2024-01-15T10:30:00Z"
                    },
                    {
                        "turn_id": 2,
                        "role": "assistant",
                        "content": "I'd be happy to help you book a flight to NYC...",
                        "tool_calls": [
                            {
                                "tool_name": "flight_search",
                                "parameters": {"destination": "NYC", "date_range": "2024-01-22/2024-01-28"},
                                "result": {"status": "success", "flights": ["..."]},
                                "latency_ms": 450
                            }
                        ],
                        "timestamp": "2024-01-15T10:30:02Z"
                    }
                ],
                "feedback": {
                    "user_rating": 4,
                    "ops_review": {"quality": "good", "notes": "Correct tool usage"},
                    "annotations": [{"type": "tool_accuracy", "label": "correct", "annotator_id": "ann_001"}]
                },
                "metadata": {"total_latency_ms": 1200, "mission_completed": True}
            }
        }


class BatchConversationIn(BaseModel):
    """For batch ingestion of up to 500 conversations."""
    conversations: List[ConversationIn] = Field(..., max_length=500)


# ── Output schemas ─────────────────────────────────────────────────────────

class IngestResponse(BaseModel):
    conversation_id: str
    status: str       # "queued" or "duplicate"
    message: str


class BatchIngestResponse(BaseModel):
    total: int
    queued: int
    duplicates: int
    results: List[IngestResponse]
