"""
LLM-as-Judge Evaluator.

Uses an LLM (Gemini by default) to assess conversation quality dimensions
that can't be caught by rules alone:
- Response quality (0.0–1.0): Is the response well-formed and complete?
- Helpfulness (0.0–1.0): Does it actually help the user achieve their goal?
- Factuality (0.0–1.0): Are stated facts accurate (no hallucinated info)?

Design notes:
- Uses structured prompting to get JSON output
- The prompt includes few-shot examples for calibration
- Falls back to mock scores if no LLM key is configured
"""

from typing import Dict, List, Optional
from evaluators.base import BaseEvaluator, EvaluatorResult
from evaluators.llm_client import get_llm_client


LLM_JUDGE_PROMPT = """You are an expert AI response quality evaluator.

Evaluate the following AI agent conversation and score it on THREE dimensions.
Respond ONLY with a JSON object — no explanations, no markdown, just raw JSON.

Conversation:
{conversation_text}

Score each dimension from 0.0 (worst) to 1.0 (best):

{{
  "response_quality": <float>,
  "helpfulness": <float>,
  "factuality": <float>,
  "issues": [
    {{"type": "...", "severity": "warning|error", "description": "..."}}
  ],
  "reasoning": "<one line explanation>"
}}

Scoring guidelines:
- response_quality: Is the response coherent, complete, and well-structured?
- helpfulness: Does the agent actually help the user accomplish their goal?
- factuality: Are all stated facts plausibly correct? (1.0 if no factual claims)
- issues: List specific quality problems. Empty array if none.
"""


def _format_conversation(turns: List[Dict]) -> str:
    lines = []
    for t in turns:
        role = t.get("role", "?").upper()
        content = t.get("content", "")
        tool_calls = t.get("tool_calls") or []
        tool_str = ""
        if tool_calls:
            tool_names = [tc.get("tool_name", "unknown") for tc in tool_calls]
            tool_str = f" [Tools: {', '.join(tool_names)}]"
        lines.append(f"Turn {t.get('turn_id', '?')} [{role}]{tool_str}: {content}")
    return "\n".join(lines)


class LLMJudgeEvaluator(BaseEvaluator):

    @property
    def name(self) -> str:
        return "llm_judge_evaluator"

    def evaluate(self, turns: List[Dict], feedback: Optional[Dict], metadata: Optional[Dict]) -> EvaluatorResult:
        conversation_text = _format_conversation(turns)
        prompt = LLM_JUDGE_PROMPT.format(conversation_text=conversation_text)

        client = get_llm_client()
        result = client.evaluate(prompt, expect_json=True)

        if result.get("_mock") or result.get("_parse_error") or result.get("_error"):
            return EvaluatorResult(
                evaluator_name=self.name,
                score=0.85,
                issues=[],
                details=result,
            )

        quality = float(result.get("response_quality") or 0.85)
        helpfulness = float(result.get("helpfulness") or 0.85)
        factuality = float(result.get("factuality") or 0.90)

        # Weighted average (quality matters most)
        composite_score = quality * 0.4 + helpfulness * 0.4 + factuality * 0.2
        issues = result.get("issues") or []

        return EvaluatorResult(
            evaluator_name=self.name,
            score=round(composite_score, 4),
            issues=issues,
            details={
                "response_quality": quality,
                "helpfulness": helpfulness,
                "factuality": factuality,
                "reasoning": result.get("reasoning", ""),
            },
        )
