"""
Annotation routing module.

Decides how to handle an annotation based on annotator agreement and confidence.
Routes to: "auto_labeled" | "human_review" | "tiebreaker"
"""

from typing import List
from collections import Counter
from config import settings


def decide_routing(labels: List[str], confidences: List[float]) -> str:
    """
    Determine routing decision for a set of annotations.

    Rules:
    1. Single annotator + high confidence → auto_labeled
    2. Multiple annotators agree + high avg confidence → auto_labeled
    3. Multiple annotators disagree (kappa < threshold) → human_review
    4. Tie (equal votes) → tiebreaker
    """
    if not labels:
        return "human_review"

    if len(labels) == 1:
        return "auto_labeled" if confidences[0] >= settings.auto_label_confidence_threshold else "human_review"

    counts = Counter(labels)
    most_common_count = counts.most_common(1)[0][1]
    avg_confidence = sum(confidences) / len(confidences)

    # Check for tie
    top_two = counts.most_common(2)
    if len(top_two) >= 2 and top_two[0][1] == top_two[1][1]:
        return "tiebreaker"

    # Majority agrees
    agreement_pct = most_common_count / len(labels)
    if agreement_pct >= settings.annotator_agreement_threshold and avg_confidence >= settings.auto_label_confidence_threshold:
        return "auto_labeled"

    return "human_review"
