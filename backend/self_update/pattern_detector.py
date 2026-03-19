"""
Failure pattern detector.

Scans recent evaluations to find recurring failure patterns.
These patterns feed into the prompt and tool suggesters.

A "pattern" is: a failure type that occurs in >= X% of recent evaluations
for a specific tool or agent behavior.
"""

from typing import Dict, List, Optional, Any
from collections import Counter, defaultdict
from sqlalchemy.orm import Session
from models.evaluation import Evaluation


def detect_patterns(
    db: Session,
    window: int = 100,
    agent_version: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Scan the last `window` evaluations for failure patterns.

    Returns a list of pattern dicts:
    {
        "pattern_type": "tool_parameter_error",
        "tool_name": "flight_search",
        "failure_rate": 0.23,
        "count": 23,
        "sample_descriptions": ["Parameter 'date_range' is null/empty", ...]
        "severity": "high" | "medium" | "low"
    }
    """
    q = db.query(Evaluation).order_by(Evaluation.created_at.desc())
    if agent_version:
        q = q.filter(Evaluation.agent_version == agent_version)
    evals = q.limit(window).all()

    if not evals:
        return []

    total = len(evals)
    issue_groups: Dict[str, List] = defaultdict(list)

    for ev in evals:
        if not ev.issues_detected:
            continue
        for issue in ev.issues_detected:
            issue_type = issue.get("type", "unknown")
            desc = issue.get("description", "")
            issue_groups[issue_type].append(desc)

    patterns = []
    for issue_type, descriptions in issue_groups.items():
        count = len(descriptions)
        failure_rate = count / total

        # Only report patterns that appear in >= 5% of evaluations
        if failure_rate < 0.05:
            continue

        severity = "high" if failure_rate >= 0.20 else ("medium" if failure_rate >= 0.10 else "low")

        # Extract unique sample descriptions (up to 5)
        unique_descs = list(dict.fromkeys(descriptions))[:5]

        # Try to extract tool name from descriptions
        tool_name = None
        for desc in descriptions[:3]:
            if "tool '" in desc.lower():
                try:
                    tool_name = desc.lower().split("tool '")[1].split("'")[0]
                    break
                except IndexError:
                    pass

        pattern = {
            "pattern_type": issue_type,
            "tool_name": tool_name,
            "failure_rate": round(failure_rate, 4),
            "count": count,
            "total_evaluated": total,
            "sample_descriptions": unique_descs,
            "severity": severity,
        }
        patterns.append(pattern)

    # Sort by severity (high first)
    severity_order = {"high": 0, "medium": 1, "low": 2}
    patterns.sort(key=lambda p: severity_order.get(p["severity"], 3))
    return patterns
