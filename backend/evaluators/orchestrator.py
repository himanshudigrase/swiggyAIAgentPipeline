"""
Evaluation Orchestrator.

Runs all 4 evaluators on a conversation and aggregates results into
a single Evaluation record stored in PostgreSQL.

Aggregation weights (tunable):
- LLM Judge: 35% (response quality, helpfulness, factuality)
- Tool Call: 35% (selection, parameter accuracy, execution)
- Coherence: 20% (context maintenance across turns)
- Heuristic: 10% (rule-based baseline checks)
"""

import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session

from models.conversation import Conversation
from models.evaluation import Evaluation
from evaluators.heuristic import HeuristicEvaluator
from evaluators.tool_call import ToolCallEvaluator
from evaluators.coherence import CoherenceEvaluator
from evaluators.llm_judge import LLMJudgeEvaluator


# Weights must sum to 1.0
WEIGHTS = {
    "llm_judge": 0.35,
    "tool_call": 0.35,
    "coherence": 0.20,
    "heuristic": 0.10,
}


class EvaluationOrchestrator:

    def __init__(self, db: Session):
        self.db = db
        self.evaluators = {
            "heuristic": HeuristicEvaluator(),
            "tool_call": ToolCallEvaluator(),
            "coherence": CoherenceEvaluator(),
            "llm_judge": LLMJudgeEvaluator(),
        }

    def evaluate(self, convo: Conversation) -> Evaluation:
        turns = convo.turns or []
        feedback = convo.feedback or {}
        metadata = convo.metadata_ or {}

        results = {}
        all_issues = []

        # Run all evaluators
        for name, evaluator in self.evaluators.items():
            try:
                result = evaluator.evaluate(turns, feedback, metadata)
                results[name] = result
                all_issues.extend(result.issues)
            except Exception as e:
                # Don't let one evaluator failure break the whole pipeline
                results[name] = None
                all_issues.append({
                    "type": "evaluator_error",
                    "severity": "warning",
                    "description": f"Evaluator '{name}' failed: {str(e)}"
                })

        # Compute weighted overall score
        weighted_sum = 0.0
        weight_used = 0.0
        for name, weight in WEIGHTS.items():
            r = results.get(name)
            if r and r.score is not None:
                weighted_sum += r.score * weight
                weight_used += weight

        overall = (weighted_sum / weight_used) if weight_used > 0 else None

        # Extract specific scores
        llm_r = results.get("llm_judge")
        tool_r = results.get("tool_call")
        coh_r = results.get("coherence")

        response_quality = llm_r.details.get("response_quality") if llm_r else None
        tool_accuracy = tool_r.score if tool_r else None
        coherence = coh_r.score if coh_r else None

        tool_eval_details = tool_r.details if tool_r else {}
        heuristic_details = results.get("heuristic").details if results.get("heuristic") else {}

        evaluation_id = f"eval_{uuid.uuid4().hex[:12]}"

        ev = Evaluation(
            evaluation_id=evaluation_id,
            conversation_id=convo.conversation_id,
            agent_version=convo.agent_version,
            overall_score=round(overall, 4) if overall is not None else None,
            response_quality=round(response_quality, 4) if response_quality is not None else None,
            tool_accuracy=round(tool_accuracy, 4) if tool_accuracy is not None else None,
            coherence=round(coherence, 4) if coherence is not None else None,
            tool_evaluation={
                "selection_accuracy": tool_eval_details.get("selection_accuracy"),
                "parameter_accuracy": tool_eval_details.get("parameter_accuracy"),
                "execution_success": tool_eval_details.get("execution_success"),
                "hallucination_detected": tool_eval_details.get("hallucination_detected"),
            },
            heuristic_flags=heuristic_details.get("flags"),
            issues_detected=all_issues,
            llm_judge_raw=llm_r.details if llm_r else None,
        )

        self.db.add(ev)
        self.db.commit()
        self.db.refresh(ev)
        return ev
