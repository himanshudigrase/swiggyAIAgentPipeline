"""
Prompt Improvement Suggester.

Takes failure patterns detected from evaluations and generates specific,
actionable suggestions for improving the agent's prompt using an LLM.

Why LLM for suggestions?
- Suggestions need to be human-readable and actionable
- The LLM can relate failure patterns to prompt design issues
- We structure the prompt carefully to get specific, not generic suggestions
"""

import uuid
from typing import Any, Dict, List
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from models.suggestion import Suggestion, SuggestionType, SuggestionStatus
from evaluators.llm_client import get_llm_client


PROMPT_SUGGESTION_TEMPLATE = """You are a senior AI prompt engineer analyzing failure patterns in an AI agent's conversation logs.

Failure patterns detected (ordered by severity):
{patterns_text}

Based on these patterns, generate UP TO 3 specific, actionable prompt improvement suggestions.

Respond ONLY with a JSON array:
[
  {{
    "target": "<which part of the prompt to improve, e.g. 'date_format_instruction'>",
    "suggestion": "<specific change to make to the prompt>",
    "rationale": "<why this will fix the pattern>",
    "expected_impact": "<what metric improvement you expect, e.g. 'Reduce date format errors by ~15%'>",
    "confidence": <float 0.0-1.0>
  }}
]

Be SPECIFIC. Don't say "improve the prompt" — say exactly what instruction to add or change.
"""


def generate_prompt_suggestions(patterns: List[Dict[str, Any]], db: Session) -> List[Suggestion]:
    """
    Generate prompt improvement suggestions from failure patterns.
    Returns list of Suggestion ORM objects (already saved to DB).
    """
    # Filter to patterns relevant to prompt issues (not tool execution failures)
    prompt_relevant = [
        p for p in patterns
        if p["pattern_type"] in ("empty_parameter", "potential_hallucination", "context_loss", "missing_tool_call")
    ]

    if not prompt_relevant:
        return []

    patterns_text = "\n".join([
        f"- [{p['severity'].upper()}] {p['pattern_type']}: {p['failure_rate']*100:.1f}% of conversations "
        f"({p['count']}/{p['total_evaluated']}). Examples: {'; '.join(p['sample_descriptions'][:2])}"
        for p in prompt_relevant
    ])

    prompt = PROMPT_SUGGESTION_TEMPLATE.format(patterns_text=patterns_text)
    client = get_llm_client()
    result = client.evaluate(prompt, expect_json=True)

    # Handle mock result
    if isinstance(result, dict) and result.get("_mock"):
        suggestions_data = [
            {
                "target": "date_format_instruction",
                "suggestion": "Add explicit instruction: 'Always extract dates in ISO 8601 format (YYYY-MM-DD). If the user says next week, calculate the specific date range.'",
                "rationale": "Reduces ambiguous date parameter extraction errors",
                "expected_impact": "Reduce date format errors by ~15%",
                "confidence": 0.72,
            }
        ]
    elif isinstance(result, list):
        suggestions_data = result
    else:
        suggestions_data = []

    saved = []
    for item in suggestions_data[:3]:
        suggestion = Suggestion(
            suggestion_id=f"sug_{uuid.uuid4().hex[:10]}",
            suggestion_type=SuggestionType.PROMPT,
            target=item.get("target"),
            suggestion_text=item.get("suggestion", ""),
            rationale=item.get("rationale"),
            expected_impact=item.get("expected_impact"),
            confidence=float(item.get("confidence", 0.5)),
            failure_pattern={"patterns": [p["pattern_type"] for p in prompt_relevant]},
            status=SuggestionStatus.PENDING,
        )
        db.add(suggestion)
        saved.append(suggestion)

    if saved:
        db.commit()
        for s in saved:
            db.refresh(s)

    return saved
