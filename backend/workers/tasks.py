"""
Celery worker configuration and task definitions.

The `evaluate_conversation_task` task picks up conversation IDs
from Redis queue and triggers all evaluators.

Why async? Ingestion should return immediately (202 Accepted).
Evaluation with LLM calls can take 2-10 seconds — unacceptable
for a synchronous HTTP response.

Result backend design note:
We intentionally set backend=None (disabled). Evaluation results are
stored directly in PostgreSQL by the orchestrator — we don't need
Celery's Redis pub/sub result tracking. Disabling it avoids connection
issues with hosted Redis services (Upstash, Railway Valkey, etc.)
that reject pub/sub subscriptions.
"""

from celery import Celery
from config import settings


def _build_celery_app() -> Celery:
    broker = settings.celery_broker_url

    app = Celery(
        "eval_pipeline",
        broker=broker,
        backend=None,   # Results stored in PostgreSQL — no Redis backend needed
    )

    # SSL support for Upstash (rediss://) and Railway Valkey
    broker_use_ssl = broker.startswith("rediss://")
    ssl_opts = {"ssl_cert_reqs": None} if broker_use_ssl else {}

    app.conf.update(
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        timezone="UTC",
        enable_utc=True,
        task_ignore_result=True,       # Don't try to store/retrieve task results
        task_track_started=False,      # No tracking via backend
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        broker_connection_retry_on_startup=True,
        broker_use_ssl=ssl_opts if broker_use_ssl else None,
    )

    return app


celery_app = _build_celery_app()


@celery_app.task(name="evaluate_conversation", bind=True, max_retries=3, ignore_result=True)
def evaluate_conversation_task(self, conversation_id: str):
    """
    Celery task: runs all evaluators on a conversation and stores results.

    Called asynchronously after ingestion. Uses the orchestrator to run
    all 4 evaluators (heuristic, tool_call, coherence, llm_judge) and
    write the result to the evaluations table in PostgreSQL.
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

            # Run all 4 evaluators via orchestrator
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
