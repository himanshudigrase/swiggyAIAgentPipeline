"""
Tool Schema Improvement Suggester.

Takes failure patterns related to tool calls and generates suggestions for:
- Better parameter descriptions in the tool schema
- Missing validation rules
- Required parameter additions
"""

import uuid
from typing import Any, Dict, List
from sqlalchemy.orm import Session

from models.suggestion import Suggestion, SuggestionType, SuggestionStatus
from evaluators.llm_client import get_llm_client


TOOL_SUGGESTION_TEMPLATE = """You are a senior AI systems engineer optimizing tool schemas for an AI agent.

Tool-related failure patterns detected:
{patterns_text}

Generate UP TO 3 specific improvements to the tool schema (parameter descriptions, validation rules, etc.).

Respond ONLY with a JSON array:
[
  {{
    "target": "<tool name, e.g. 'flight_search'>",
    "suggestion": "<specific change to the tool schema or parameter description>",
    "rationale": "<why this will reduce the failures>",
    "expected_impact": "<expected improvement>",
    "confidence": <float 0.0-1.0>
  }}
]
"""


def generate_tool_suggestions(patterns: List[Dict[str, Any]], db: Session) -> List[Suggestion]:
    """
    Generate tool schema improvement suggestions from failure patterns.
    Returns list of Suggestion ORM objects (already saved to DB).
    """
    tool_relevant = [
        p for p in patterns
        if p["pattern_type"] in ("empty_parameter", "tool_execution_failure", "potential_hallucination", "missing_tool_call")
        and p.get("tool_name")
    ]

    if not tool_relevant:
        return []

    patterns_text = "\n".join([
        f"- [{p['severity'].upper()}] Tool '{p['tool_name']}' — {p['pattern_type']}: "
        f"{p['failure_rate']*100:.1f}% failure rate. Examples: {'; '.join(p['sample_descriptions'][:2])}"
        for p in tool_relevant
    ])

    prompt = TOOL_SUGGESTION_TEMPLATE.format(patterns_text=patterns_text)
    client = get_llm_client()
    result = client.evaluate(prompt, expect_json=True)

    if isinstance(result, dict) and result.get("_mock"):
        suggestions_data = [
            {
                "target": tool_relevant[0]["tool_name"] if tool_relevant else "flight_search",
                "suggestion": "Add explicit parameter validation: mark 'date_range' as required with format YYYY-MM-DD/YYYY-MM-DD and add an example in the description.",
                "rationale": "Agent extracts dates in ambiguous formats because the schema doesn't enforce ISO 8601",
                "expected_impact": "Reduce parameter extraction errors by ~20%",
                "confidence": 0.68,
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
            suggestion_type=SuggestionType.TOOL,
            target=item.get("target"),
            suggestion_text=item.get("suggestion", ""),
            rationale=item.get("rationale"),
            expected_impact=item.get("expected_impact"),
            confidence=float(item.get("confidence", 0.5)),
            failure_pattern={"patterns": [p["pattern_type"] for p in tool_relevant]},
            status=SuggestionStatus.PENDING,
        )
        db.add(suggestion)
        saved.append(suggestion)

    if saved:
        db.commit()
        for s in saved:
            db.refresh(s)

    return saved
