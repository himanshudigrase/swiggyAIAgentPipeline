"""
Ingestion router.

POST /ingest       — ingest a single conversation
POST /ingest/batch — ingest up to 500 conversations

Both endpoints:
1. Validate the payload (Pydantic does this automatically)
2. Store the raw conversation in PostgreSQL
3. Run evaluation in the background (FastAPI BackgroundTasks — no Redis/Celery needed)
4. Return 202 Accepted immediately

Why BackgroundTasks instead of Celery?
FastAPI's BackgroundTasks runs the function in a thread pool after the HTTP response
is sent — zero extra infrastructure. For production scale, Celery can be re-enabled
by swapping _run_evaluation_bg back to evaluate_conversation_task.delay().
"""

import logging
from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlalchemy.orm import Session

from database import get_db, SessionLocal
from models.conversation import Conversation, ConversationStatus
from schemas.conversation import (
    ConversationIn, BatchConversationIn,
    IngestResponse, BatchIngestResponse,
)

router = APIRouter()
logger = logging.getLogger(__name__)


def _run_evaluation_bg(conversation_id: str):
    """
    Background task: runs all 4 evaluators and stores the result in PostgreSQL.
    Runs in a thread pool after the HTTP response is sent.
    """
    db = SessionLocal()
    try:
        from models.conversation import Conversation, ConversationStatus
        from evaluators.orchestrator import EvaluationOrchestrator
        from datetime import datetime, timezone

        convo = db.query(Conversation).filter(
            Conversation.conversation_id == conversation_id
        ).first()

        if not convo:
            logger.error(f"Background eval: conversation {conversation_id} not found")
            return

        convo.status = ConversationStatus.EVALUATING
        db.commit()

        orchestrator = EvaluationOrchestrator(db)
        orchestrator.evaluate(convo)

        convo.status = ConversationStatus.EVALUATED
        convo.evaluated_at = datetime.now(timezone.utc)
        db.commit()

        logger.info(f"Evaluation complete for {conversation_id}")

    except Exception as e:
        logger.exception(f"Evaluation failed for {conversation_id}: {e}")
        try:
            convo = db.query(Conversation).filter(
                Conversation.conversation_id == conversation_id
            ).first()
            if convo:
                convo.status = ConversationStatus.FAILED
                db.commit()
        except Exception:
            pass
    finally:
        db.close()


def _store_and_enqueue(
    conv_in: ConversationIn,
    db: Session,
    background_tasks: BackgroundTasks,
) -> IngestResponse:
    """Store one conversation in DB and schedule background evaluation."""
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

    # Schedule evaluation to run after HTTP response is sent
    background_tasks.add_task(_run_evaluation_bg, conv_in.conversation_id)

    return IngestResponse(
        conversation_id=conv_in.conversation_id,
        status="queued",
        message="Conversation ingested. Evaluation running in background.",
    )


@router.post(
    "",
    response_model=IngestResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Ingest a single conversation",
    description=(
        "Ingest a conversation log. The payload is stored immediately and evaluation "
        "runs in the background after the response. Returns 202 Accepted."
    ),
)
def ingest_single(
    conv_in: ConversationIn,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    return _store_and_enqueue(conv_in, db, background_tasks)


@router.post(
    "/batch",
    response_model=BatchIngestResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Ingest multiple conversations (batch)",
    description="Ingest up to 500 conversation logs in one request.",
)
def ingest_batch(
    batch: BatchConversationIn,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    results = [_store_and_enqueue(c, db, background_tasks) for c in batch.conversations]
    queued = sum(1 for r in results if r.status == "queued")
    duplicates = sum(1 for r in results if r.status == "duplicate")

    return BatchIngestResponse(
        total=len(results),
        queued=queued,
        duplicates=duplicates,
        results=results,
    )
