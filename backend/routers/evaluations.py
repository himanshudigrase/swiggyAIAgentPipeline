"""
Evaluations router.

GET /evaluations                    — paginated list of all evaluations
GET /evaluations/{conversation_id}  — single evaluation by conversation ID
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db
from models.evaluation import Evaluation
from schemas.evaluation import EvaluationOut, EvaluationListOut, ToolEvaluation, Issue

router = APIRouter()


def _to_schema(ev: Evaluation) -> EvaluationOut:
    tool_ev = None
    if ev.tool_evaluation:
        tool_ev = ToolEvaluation(**ev.tool_evaluation)

    issues = []
    if ev.issues_detected:
        issues = [Issue(**i) for i in ev.issues_detected]

    return EvaluationOut(
        evaluation_id=ev.evaluation_id,
        conversation_id=ev.conversation_id,
        agent_version=ev.agent_version,
        scores={
            "overall": ev.overall_score,
            "response_quality": ev.response_quality,
            "tool_accuracy": ev.tool_accuracy,
            "coherence": ev.coherence,
        },
        tool_evaluation=tool_ev,
        heuristic_flags=ev.heuristic_flags,
        issues_detected=issues,
        created_at=ev.created_at,
    )


@router.get(
    "",
    response_model=EvaluationListOut,
    summary="List all evaluations",
    description="Returns a paginated list of evaluations. Filter by agent_version.",
)
def list_evaluations(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    agent_version: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    q = db.query(Evaluation)
    if agent_version:
        q = q.filter(Evaluation.agent_version == agent_version)
    total = q.count()
    items = q.order_by(Evaluation.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    return EvaluationListOut(
        total=total,
        page=page,
        page_size=page_size,
        items=[_to_schema(e) for e in items],
    )


@router.get(
    "/{conversation_id}",
    response_model=EvaluationOut,
    summary="Get evaluation for a specific conversation",
)
def get_evaluation(conversation_id: str, db: Session = Depends(get_db)):
    ev = db.query(Evaluation).filter(
        Evaluation.conversation_id == conversation_id
    ).first()
    if not ev:
        raise HTTPException(status_code=404, detail="Evaluation not found")
    return _to_schema(ev)
