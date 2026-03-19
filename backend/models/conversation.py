"""
SQLAlchemy ORM model for conversations.

Stores the raw ingested conversation log exactly as received,
with JSONB columns for flexible nested data (turns, feedback, metadata).
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, Enum, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from database import Base
import enum


class ConversationStatus(str, enum.Enum):
    PENDING = "pending"
    EVALUATING = "evaluating"
    EVALUATED = "evaluated"
    FAILED = "failed"


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(String(255), unique=True, nullable=False, index=True)
    agent_version = Column(String(50), nullable=True, index=True)
    turns = Column(JSONB, nullable=False)             # Full turn-by-turn log
    feedback = Column(JSONB, nullable=True)           # User ratings, ops review, annotations
    metadata_ = Column("metadata", JSONB, nullable=True)  # latency, mission_completed, etc.
    status = Column(
        Enum(ConversationStatus, native_enum=False),
        default=ConversationStatus.PENDING,
        nullable=False,
        index=True,
    )
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    evaluated_at = Column(DateTime(timezone=True), nullable=True)
