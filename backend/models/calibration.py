"""
SQLAlchemy ORM model for evaluator calibration.

Tracks agreement between LLM-as-Judge scores and human annotation labels
over time. This powers the Meta-Evaluation feature — the system that
improves the evaluators themselves.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Float, Boolean, DateTime
from sqlalchemy.dialects.postgresql import JSONB, UUID
from database import Base


class EvaluatorCalibration(Base):
    __tablename__ = "evaluator_calibration"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(String(255), nullable=False, index=True)
    evaluator_name = Column(String(100), nullable=False, index=True)

    # The metric being compared (e.g., "tool_accuracy", "response_quality")
    metric = Column(String(100), nullable=False)

    # LLM evaluator's score/label
    llm_score = Column(Float, nullable=True)
    llm_label = Column(String(100), nullable=True)

    # Human annotator's score/label (ground truth)
    human_score = Column(Float, nullable=True)
    human_label = Column(String(100), nullable=True)

    # Do they agree?
    agreement = Column(Boolean, nullable=True)
    agreement_delta = Column(Float, nullable=True)  # abs(llm_score - human_score)

    # Additional context
    extra = Column(JSONB, nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
