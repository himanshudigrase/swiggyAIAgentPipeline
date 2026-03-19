"""
Suggestions router.

GET  /suggestions          — list improvement suggestions
POST /suggestions/generate — manually trigger suggestion generation
"""

from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from database import get_db
from models.suggestion import Suggestion
from schemas.suggestion import SuggestionOut, SuggestionListOut, GenerateSuggestionsRequest
from self_update.pattern_detector import detect_patterns
from self_update.prompt_suggester import generate_prompt_suggestions
from self_update.tool_suggester import generate_tool_suggestions

router = APIRouter()


def _to_schema(s: Suggestion) -> SuggestionOut:
    return SuggestionOut(
        suggestion_id=s.suggestion_id,
        suggestion_type=s.suggestion_type,
        target=s.target,
        suggestion_text=s.suggestion_text,
        rationale=s.rationale,
        expected_impact=s.expected_impact,
        confidence=s.confidence,
        failure_pattern=s.failure_pattern,
        status=s.status,
        created_at=s.created_at,
    )


@router.get(
    "",
    response_model=SuggestionListOut,
    summary="List improvement suggestions",
    description="Returns all auto-generated prompt and tool improvement suggestions.",
)
def list_suggestions(
    suggestion_type: Optional[str] = Query(None, description="Filter: 'prompt' or 'tool'"),
    status: Optional[str] = Query(None, description="Filter: 'pending', 'applied', 'dismissed'"),
    db: Session = Depends(get_db),
):
    q = db.query(Suggestion)
    if suggestion_type:
        q = q.filter(Suggestion.suggestion_type == suggestion_type)
    if status:
        q = q.filter(Suggestion.status == status)
    items = q.order_by(Suggestion.created_at.desc()).all()
    return SuggestionListOut(total=len(items), items=[_to_schema(s) for s in items])


@router.post(
    "/generate",
    response_model=SuggestionListOut,
    summary="Trigger improvement suggestion generation",
    description=(
        "Scans recent evaluations for failure patterns and generates improvement "
        "suggestions for prompts and tools using an LLM."
    ),
)
def generate_suggestions(req: GenerateSuggestionsRequest, db: Session = Depends(get_db)):
    patterns = detect_patterns(db, window=req.window, agent_version=req.agent_version)
    new_suggestions = []

    prompt_suggestions = generate_prompt_suggestions(patterns, db)
    new_suggestions.extend(prompt_suggestions)

    tool_suggestions = generate_tool_suggestions(patterns, db)
    new_suggestions.extend(tool_suggestions)

    return SuggestionListOut(total=len(new_suggestions), items=[_to_schema(s) for s in new_suggestions])
