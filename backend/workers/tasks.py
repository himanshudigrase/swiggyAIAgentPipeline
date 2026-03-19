"""
Celery worker configuration and task definitions.

The `evaluate_conversation_task` task picks up conversation IDs
from Redis queue and triggers all evaluators.

Why async? Ingestion should return immediately (202 Accepted).
Evaluation with LLM calls can take 2-10 seconds — unacceptable
for a synchronous HTTP response.
"""

from celery import Celery
from config import settings

# Configure Celery to use Redis as both broker and backend
celery_app = Celery(
    "eval_pipeline",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    # Retry on failure up to 3 times with exponential backoff
    task_acks_late=True,
    task_reject_on_worker_lost=True,
)


@celery_app.task(name="evaluate_conversation", bind=True, max_retries=3)
def evaluate_conversation_task(self, conversation_id: str):
    """
    Celery task: runs all evaluators on a conversation and stores results.

    Called asynchronously after ingestion. Uses the orchestrator to run
    all 4 evaluators (heuristic, tool_call, coherence, llm_judge) and
    write the result to the evaluations table.
    """
    try:
        from database import SessionLocal
        from models.conversation import Conversation, ConversationStatus
        from evaluators.orchestrator import EvaluationOrchestrator

        db = SessionLocal()
        try:
            convo = db.query(Conversation).filter(
                Conversation.conversation_id == conversation_id
            ).first()

            if not convo:
                return {"error": f"Conversation {conversation_id} not found"}

            # Mark as evaluating
            convo.status = ConversationStatus.EVALUATING
            db.commit()

            # Run all evaluators
            orchestrator = EvaluationOrchestrator(db)
            orchestrator.evaluate(convo)

            # Mark as done
            from datetime import datetime, timezone
            convo.status = ConversationStatus.EVALUATED
            convo.evaluated_at = datetime.now(timezone.utc)
            db.commit()

            return {"status": "success", "conversation_id": conversation_id}

        except Exception as e:
            convo.status = ConversationStatus.FAILED
            db.commit()
            raise e
        finally:
            db.close()

    except Exception as exc:
        # Exponential backoff retry: 30s, 60s, 120s
        raise self.retry(exc=exc, countdown=30 * (2 ** self.request.retries))
