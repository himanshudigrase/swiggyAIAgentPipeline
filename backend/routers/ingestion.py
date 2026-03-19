"""
Ingestion router.

POST /ingest       — ingest a single conversation
POST /ingest/batch — ingest up to 500 conversations

Both endpoints:
1. Validate the payload (Pydantic does this automatically)
2. Store the raw conversation in PostgreSQL
3. Enqueue an async Celery evaluation job
4. Return 202 Accepted immediately (evaluation happens in the background)
"""

import json
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from models.conversation import Conversation, ConversationStatus
from schemas.conversation import (
    ConversationIn, BatchConversationIn,
    IngestResponse, BatchIngestResponse,
)
from workers.tasks import evaluate_conversation_task

router = APIRouter()


def _store_and_enqueue(conv_in: ConversationIn, db: Session) -> IngestResponse:
    """Store one conversation in DB and enqueue evaluation. Handles duplicates."""
    existing = db.query(Conversation).filter(
        Conversation.conversation_id == conv_in.conversation_id
    ).first()

    if existing:
        return IngestResponse(
            conversation_id=conv_in.conversation_id,
            status="duplicate",
            message="Conversation already exists. Skipped.",
        )

    convo = Conversation(
        conversation_id=conv_in.conversation_id,
        agent_version=conv_in.agent_version,
        turns=[t.model_dump(mode="json") for t in conv_in.turns],
        feedback=conv_in.feedback.model_dump(mode="json") if conv_in.feedback else None,
        metadata_=conv_in.metadata.model_dump(mode="json") if conv_in.metadata else None,
        status=ConversationStatus.PENDING,
    )
    db.add(convo)
    db.commit()
    db.refresh(convo)

    # Enqueue async evaluation (non-blocking)
    evaluate_conversation_task.delay(conv_in.conversation_id)

    return IngestResponse(
        conversation_id=conv_in.conversation_id,
        status="queued",
        message="Conversation ingested. Evaluation queued.",
    )


@router.post(
    "",
    response_model=IngestResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Ingest a single conversation",
    description=(
        "Ingest a conversation log. The payload is stored immediately and an "
        "evaluation job is queued asynchronously. Returns 202 Accepted."
    ),
)
def ingest_single(conv_in: ConversationIn, db: Session = Depends(get_db)):
    return _store_and_enqueue(conv_in, db)


@router.post(
    "/batch",
    response_model=BatchIngestResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Ingest multiple conversations (batch)",
    description="Ingest up to 500 conversation logs in one request.",
)
def ingest_batch(batch: BatchConversationIn, db: Session = Depends(get_db)):
    results = [_store_and_enqueue(c, db) for c in batch.conversations]
    queued = sum(1 for r in results if r.status == "queued")
    duplicates = sum(1 for r in results if r.status == "duplicate")

    return BatchIngestResponse(
        total=len(results),
        queued=queued,
        duplicates=duplicates,
        results=results,
    )
