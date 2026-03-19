"""
Heuristic Evaluator — Rule-based, no LLM, instant.

Checks:
1. Latency threshold: total_latency_ms vs. configured limit
2. Required fields: all turns have role + content
3. Tool call results: tools that ran should have a result status
4. Mission completion: was the mission_completed flag set to True?

Why heuristics first?
- Fast (microseconds vs. seconds for LLM)
- Reliable (no hallucination risk)
- Run on 100% of traffic; LLM eval can sample
"""

from typing import Dict, List, Optional
from config import settings
from evaluators.base import BaseEvaluator, EvaluatorResult


class HeuristicEvaluator(BaseEvaluator):

    @property
    def name(self) -> str:
        return "heuristic_evaluator"

    def evaluate(self, turns: List[Dict], feedback: Optional[Dict], metadata: Optional[Dict]) -> EvaluatorResult:
        issues = []
        flags = {
            "latency_ok": True,
            "required_fields_ok": True,
            "tool_results_ok": True,
            "mission_completed": None,
        }

        # ── 1. Latency check ─────────────────────────────────────────────────
        latency_ms = (metadata or {}).get("total_latency_ms")
        if latency_ms is not None:
            if latency_ms > settings.latency_threshold_ms:
                flags["latency_ok"] = False
                issues.append({
                    "type": "latency",
                    "severity": "warning",
                    "description": (
                        f"Response latency {latency_ms:.0f}ms exceeds "
                        f"{settings.latency_threshold_ms}ms target"
                    ),
                })

        # ── 2. Required fields check ──────────────────────────────────────────
        for turn in turns:
            if not turn.get("role") or not turn.get("content"):
                flags["required_fields_ok"] = False
                issues.append({
                    "type": "missing_field",
                    "severity": "error",
                    "description": f"Turn {turn.get('turn_id', '?')} missing 'role' or 'content'",
                })
                break

        # ── 3. Tool result check ──────────────────────────────────────────────
        for turn in turns:
            for tc in turn.get("tool_calls") or []:
                result = tc.get("result") or {}
                if result.get("status") not in ("success", None):
                    flags["tool_results_ok"] = False
                    issues.append({
                        "type": "tool_failure",
                        "severity": "error",
                        "description": (
                            f"Tool '{tc.get('tool_name')}' returned status "
                            f"'{result.get('status')}'"
                        ),
                    })

        # ── 4. Mission completion ─────────────────────────────────────────────
        if metadata:
            flags["mission_completed"] = metadata.get("mission_completed")
            if flags["mission_completed"] is False:
                issues.append({
                    "type": "mission_incomplete",
                    "severity": "warning",
                    "description": "Mission was not completed",
                })

        # Score: fraction of passing checks
        check_values = [flags["latency_ok"], flags["required_fields_ok"], flags["tool_results_ok"]]
        if flags["mission_completed"] is not None:
            check_values.append(bool(flags["mission_completed"]))

        score = sum(check_values) / len(check_values)

        return EvaluatorResult(
            evaluator_name=self.name,
            score=round(score, 4),
            issues=issues,
            details={"flags": flags},
        )
