"""
SQLAlchemy ORM model for evaluation results.

Stores scores computed by all 4 evaluators for each conversation.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Float, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB, UUID
from database import Base


class Evaluation(Base):
    __tablename__ = "evaluations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    evaluation_id = Column(String(255), unique=True, nullable=False, index=True)
    conversation_id = Column(String(255), ForeignKey("conversations.conversation_id"), nullable=False, index=True)
    agent_version = Column(String(50), nullable=True, index=True)

    # ── Aggregate scores (0.0 – 1.0) ──────────────────────────────────────────
    overall_score = Column(Float, nullable=True)
    response_quality = Column(Float, nullable=True)   # LLM-as-Judge
    tool_accuracy = Column(Float, nullable=True)      # Tool Call Evaluator
    coherence = Column(Float, nullable=True)          # Multi-turn Coherence

    # ── Tool call details ──────────────────────────────────────────────────────
    tool_evaluation = Column(JSONB, nullable=True)
    # Shape: { selection_accuracy, parameter_accuracy, execution_success, hallucination_detected }

    # ── Heuristic flags ────────────────────────────────────────────────────────
    heuristic_flags = Column(JSONB, nullable=True)
    # Shape: { latency_ok, required_fields_ok, format_ok }

    # ── Issues + suggestions (written at eval time for quick lookup) ───────────
    issues_detected = Column(JSONB, nullable=True)
    # Shape: [ { type, severity, description } ]

    # ── LLM judge raw output ───────────────────────────────────────────────────
    llm_judge_raw = Column(JSONB, nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
