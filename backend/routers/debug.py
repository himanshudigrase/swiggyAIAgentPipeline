"""
Debug router — lightweight diagnostic endpoints.
Only exposes read-only info. Safe to ship.
"""

import logging
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
from models.conversation import Conversation
from models.evaluation import Evaluation

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/conversations", summary="List all conversations with their statuses")
def debug_conversations(db: Session = Depends(get_db)):
    """Shows every conversation + its status so we can diagnose if the worker is running."""
    rows = db.query(
        Conversation.conversation_id,
        Conversation.agent_version,
        Conversation.status,
        Conversation.created_at,
        Conversation.evaluated_at,
    ).order_by(Conversation.created_at.desc()).limit(50).all()

    eval_count = db.query(Evaluation).count()
    conv_count = db.query(Conversation).count()

    return {
        "total_conversations": conv_count,
        "total_evaluations": eval_count,
        "conversations": [
            {
                "conversation_id": r.conversation_id,
                "agent_version": r.agent_version,
                "status": r.status,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "evaluated_at": r.evaluated_at.isoformat() if r.evaluated_at else None,
            }
            for r in rows
        ],
    }
