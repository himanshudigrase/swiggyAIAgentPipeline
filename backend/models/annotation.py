"""
SQLAlchemy ORM model for human annotations.

Each row is a single annotator's label for a single conversation.
Multiple annotators can annotate the same conversation — agreement
is computed separately in feedback/agreement.py.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Float, DateTime, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from database import Base


class Annotation(Base):
    __tablename__ = "annotations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(String(255), nullable=False, index=True)
    annotator_id = Column(String(100), nullable=False, index=True)

    # What dimension is being annotated (e.g. "tool_accuracy", "helpfulness")
    annotation_type = Column(String(100), nullable=False)

    # The actual label (e.g. "correct", "incorrect", "helpful", "not_helpful")
    label = Column(String(100), nullable=False)

    # 0.0–1.0 confidence in the annotation
    confidence = Column(Float, default=1.0)

    # Free-text notes from the annotator
    notes = Column(Text, nullable=True)

    # Additional structured data (e.g. span highlights)
    extra = Column(JSONB, nullable=True)

    # Routing outcome: "auto_labeled", "human_review", "tiebreaker"
    routing_decision = Column(String(50), nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
