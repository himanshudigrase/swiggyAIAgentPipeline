"""
Multi-turn Coherence Evaluator — LLM-assisted.

Detects context loss across long conversations. Key things to measure:
1. Are user preferences from early turns respected in later turns?
2. Are there contradictions between turns?
3. Are pronoun/reference resolutions correct?

Why LLM-assisted?
- These checks require semantic understanding, not just pattern matching
- "Forgets you're a vegetarian" can't be caught by keyword rules
- For short conversations (<= 2 turns), we skip LLM and return a high default score
"""

from typing import Dict, List, Optional
from evaluators.base import BaseEvaluator, EvaluatorResult
from evaluators.llm_client import get_llm_client


COHERENCE_PROMPT_TEMPLATE = """You are evaluating a multi-turn AI agent conversation for coherence and context maintenance.

Conversation:
{conversation_text}

Evaluate the following THREE dimensions and respond ONLY with a JSON object, no extra text:

{{
  "coherence_score": <float 0.0-1.0>,
  "context_maintained": <true/false>,
  "contradictions_found": <true/false>,
  "reference_resolution_ok": <true/false>,
  "issues": [
    {{"type": "context_loss", "severity": "error", "description": "..."}}
  ],
  "reasoning": "<brief explanation>"
}}

Rules:
- coherence_score = 1.0 means perfect context maintenance
- coherence_score < 0.7 means significant context loss
- context_maintained = false if agent ignores preferences/info from earlier turns
- contradictions_found = true if agent makes conflicting statements across turns
- reference_resolution_ok = false if agent misresolves pronouns or references
"""


def _format_conversation(turns: List[Dict]) -> str:
    """Format turns into a readable conversation string for the LLM."""
    lines = []
    for t in turns:
        role = t.get("role", "?").upper()
        content = t.get("content", "")
        tool_calls = t.get("tool_calls") or []
        tool_str = ""
        if tool_calls:
            tool_str = f" [Called: {', '.join(tc.get('tool_name', '?') for tc in tool_calls)}]"
        lines.append(f"Turn {t.get('turn_id', '?')} [{role}]{tool_str}: {content}")
    return "\n".join(lines)


class CoherenceEvaluator(BaseEvaluator):

    @property
    def name(self) -> str:
        return "coherence_evaluator"

    def evaluate(self, turns: List[Dict], feedback: Optional[Dict], metadata: Optional[Dict]) -> EvaluatorResult:
        # For short conversations, coherence is not a concern
        if len(turns) <= 2:
            return EvaluatorResult(
                evaluator_name=self.name,
                score=1.0,
                issues=[],
                details={"note": "Short conversation (<= 2 turns) — coherence not evaluated"},
            )

        conversation_text = _format_conversation(turns)
        prompt = COHERENCE_PROMPT_TEMPLATE.format(conversation_text=conversation_text)

        client = get_llm_client()
        result = client.evaluate(prompt, expect_json=True)

        if result.get("_mock"):
            # Mock mode — return realistic defaults
            return EvaluatorResult(
                evaluator_name=self.name,
                score=0.85,
                issues=[],
                details={"note": "Mock mode — real LLM evaluation disabled"},
            )

        score = result.get("coherence_score", 0.8)
        issues = result.get("issues") or []

        if not result.get("context_maintained", True):
            issues.append({
                "type": "context_loss",
                "severity": "error",
                "description": "Agent failed to maintain context from earlier turns",
            })
        if result.get("contradictions_found", False):
            issues.append({
                "type": "contradiction",
                "severity": "warning",
                "description": "Contradictory statements detected across turns",
            })

        return EvaluatorResult(
            evaluator_name=self.name,
            score=round(float(score), 4),
            issues=issues,
            details=result,
        )
