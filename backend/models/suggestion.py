"""
SQLAlchemy ORM model for improvement suggestions.

Stores LLM-generated suggestions for prompt and tool improvements.
Each suggestion is tied to a detected failure pattern.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Float, DateTime, Text, Enum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from database import Base
import enum


class SuggestionType(str, enum.Enum):
    PROMPT = "prompt"
    TOOL = "tool"


class SuggestionStatus(str, enum.Enum):
    PENDING = "pending"
    APPLIED = "applied"
    DISMISSED = "dismissed"


class Suggestion(Base):
    __tablename__ = "suggestions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    suggestion_id = Column(String(255), unique=True, nullable=False, index=True)

    # "prompt" or "tool"
    suggestion_type = Column(Enum(SuggestionType, native_enum=False), nullable=False, index=True)

    # Which prompt section or tool name this applies to
    target = Column(String(255), nullable=True)

    # Human-readable improvement suggestion
    suggestion_text = Column(Text, nullable=False)

    # Why this suggestion was generated
    rationale = Column(Text, nullable=True)

    # Expected impact (e.g., "Reduce date format errors by ~15%")
    expected_impact = Column(Text, nullable=True)

    # 0.0–1.0 confidence score
    confidence = Column(Float, default=0.5)

    # The failure pattern that triggered this suggestion
    failure_pattern = Column(JSONB, nullable=True)

    status = Column(Enum(SuggestionStatus, native_enum=False), default=SuggestionStatus.PENDING, index=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=True)
