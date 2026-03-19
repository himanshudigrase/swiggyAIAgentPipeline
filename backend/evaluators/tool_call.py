"""
Tool Call Evaluator — Logic-based, no LLM.

Measures tool usage quality across:
1. Selection accuracy: Was a relevant tool called given the user intent?
2. Parameter accuracy: Are required params present and non-empty?
3. Hallucination detection: Are param values grounded in the conversation?
4. Execution success: Did the tool return 'status: success'?

Why logic-based instead of LLM?
- Tool calls have structured schemas — we can check them programmatically
- Faster and cheaper than LLM-based analysis
- More reliable for deterministic checks (was status == 'success'?)
"""

from typing import Dict, List, Optional
from evaluators.base import BaseEvaluator, EvaluatorResult


# ── Intent → expected tool mapping ─────────────────────────────────────────
# Maps keywords in user messages to tools that should be called
INTENT_TOOL_MAP = {
    "flight": ["flight_search", "book_flight"],
    "book": ["book_flight", "hotel_search", "flight_search"],
    "hotel": ["hotel_search", "book_hotel"],
    "weather": ["weather_api"],
    "cancel": ["cancel_booking"],
    "refund": ["refund_request"],
    "payment": ["process_payment"],
    "restaurant": ["restaurant_search"],
    "food": ["food_search", "order_food"],
    "delivery": ["track_delivery"],
}


def _infer_expected_tools(turns: List[Dict]) -> List[str]:
    """Scan user turns for intent keywords and return expected tool names."""
    expected = set()
    for turn in turns:
        if turn.get("role") == "user":
            content = (turn.get("content") or "").lower()
            for keyword, tools in INTENT_TOOL_MAP.items():
                if keyword in content:
                    expected.update(tools)
    return list(expected)


def _extract_all_tool_calls(turns: List[Dict]) -> List[Dict]:
    """Flatten all tool calls from all turns."""
    calls = []
    for turn in turns:
        calls.extend(turn.get("tool_calls") or [])
    return calls


def _check_parameter_accuracy(tc: Dict, all_user_content: str) -> Dict:
    """
    Check if tool parameters are:
    a) Non-empty (no None/null parameters)
    b) Plausibly grounded in conversation (not hallucinated)
    """
    params = tc.get("parameters") or {}
    issues = []
    hallucination_flags = []

    for key, val in params.items():
        if val is None or val == "":
            issues.append(f"Parameter '{key}' is null/empty")

        # Simple grounding check: is the value (or part of it) in the conversation?
        if isinstance(val, str) and len(val) > 2:
            # Check if key terms from the value appear anywhere in user messages
            val_lower = val.lower()
            # Known hallucination patterns: dates in wrong format, cities not mentioned
            if not any(term in all_user_content.lower() for term in val_lower.split()[:2]):
                hallucination_flags.append(key)

    return {"empty_params": issues, "potential_hallucinations": hallucination_flags}


class ToolCallEvaluator(BaseEvaluator):

    @property
    def name(self) -> str:
        return "tool_call_evaluator"

    def evaluate(self, turns: List[Dict], feedback: Optional[Dict], metadata: Optional[Dict]) -> EvaluatorResult:
        tool_calls = _extract_all_tool_calls(turns)
        expected_tools = _infer_expected_tools(turns)
        issues = []

        # Collect all user message text for grounding checks
        all_user_content = " ".join(
            t.get("content", "") for t in turns if t.get("role") == "user"
        )

        # ── Selection accuracy ────────────────────────────────────────────────
        called_tool_names = [tc.get("tool_name") for tc in tool_calls]
        if expected_tools and called_tool_names:
            matched = [t for t in called_tool_names if t in expected_tools]
            selection_accuracy = len(matched) / len(expected_tools) if expected_tools else 1.0
        elif not expected_tools and not called_tool_names:
            selection_accuracy = 1.0  # No tools needed, none called — correct
        elif expected_tools and not called_tool_names:
            selection_accuracy = 0.0
            issues.append({
                "type": "missing_tool_call",
                "severity": "error",
                "description": f"Expected tool(s) {expected_tools} but none were called",
            })
        else:
            selection_accuracy = 0.8  # Unexpected tool call — deduct slightly

        # ── Parameter accuracy + hallucination detection ──────────────────────
        param_scores = []
        hallucination_detected = False

        for tc in tool_calls:
            check = _check_parameter_accuracy(tc, all_user_content)
            if check["empty_params"]:
                for msg in check["empty_params"]:
                    issues.append({
                        "type": "empty_parameter",
                        "severity": "warning",
                        "description": f"In tool '{tc.get('tool_name')}': {msg}",
                    })
                param_scores.append(0.5)
            else:
                param_scores.append(1.0)

            if check["potential_hallucinations"]:
                hallucination_detected = True
                issues.append({
                    "type": "potential_hallucination",
                    "severity": "warning",
                    "description": (
                        f"Tool '{tc.get('tool_name')}' param(s) "
                        f"{check['potential_hallucinations']} may be hallucinated"
                    ),
                })

        parameter_accuracy = (sum(param_scores) / len(param_scores)) if param_scores else 1.0

        # ── Execution success ─────────────────────────────────────────────────
        execution_results = [
            (tc.get("result") or {}).get("status") == "success"
            for tc in tool_calls if tc.get("result")
        ]
        execution_success = all(execution_results) if execution_results else True

        if not execution_success:
            issues.append({
                "type": "tool_execution_failure",
                "severity": "error",
                "description": "One or more tool calls did not return 'success' status",
            })

        # ── Aggregate score ───────────────────────────────────────────────────
        score = (selection_accuracy * 0.4 + parameter_accuracy * 0.4 + (1.0 if execution_success else 0.0) * 0.2)

        return EvaluatorResult(
            evaluator_name=self.name,
            score=round(score, 4),
            issues=issues,
            details={
                "selection_accuracy": round(selection_accuracy, 4),
                "parameter_accuracy": round(parameter_accuracy, 4),
                "execution_success": execution_success,
                "hallucination_detected": hallucination_detected,
                "expected_tools": expected_tools,
                "called_tools": called_tool_names,
            },
        )
