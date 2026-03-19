"""
Inter-annotator agreement calculation.

Why this matters:
- Multiple human annotators may label the same conversation differently
- We need a way to measure how much they agree
- High agreement = we can trust the label
- Low agreement = we need a tiebreaker or more annotators

Metrics implemented:
- Percentage agreement: simple and easy to explain
- Cohen's Kappa: corrects for chance agreement (more reliable for binary labels)
"""

from typing import List, Dict, Optional
from collections import Counter


def percentage_agreement(labels: List[str]) -> float:
    """
    What fraction of annotators chose the most common label?
    Range: 0.0 (total disagreement) to 1.0 (perfect agreement)
    """
    if len(labels) <= 1:
        return 1.0
    most_common_count = Counter(labels).most_common(1)[0][1]
    return most_common_count / len(labels)


def cohen_kappa(labels: List[str]) -> Optional[float]:
    """
    Cohen's Kappa for exactly 2 annotators.
    Corrects for chance agreement.

    κ > 0.8 = almost perfect
    κ 0.6-0.8 = substantial agreement
    κ < 0.6 = moderate / low agreement (flag for review)

    Returns None if fewer than 2 labels.
    """
    if len(labels) < 2:
        return None

    # Simple pairwise for first 2 annotators
    l1, l2 = labels[0], labels[1]
    agree = 1.0 if l1 == l2 else 0.0

    # Expected agreement by chance (assuming uniform distribution)
    all_labels = [l1, l2]
    counts = Counter(all_labels)
    total = len(all_labels)
    p_expected = sum((c / total) ** 2 for c in counts.values())

    if p_expected == 1.0:
        return 1.0  # all same label, no chance variance

    kappa = (agree - p_expected) / (1.0 - p_expected)
    return round(kappa, 4)


def compute_agreement(labels: List[str], confidences: List[float]) -> Dict:
    """
    Compute all agreement metrics for a set of annotations.

    Returns a dict with:
    - agreement_pct: 0.0–1.0
    - cohen_kappa: float or None
    - majority_label: the most common label
    - weighted_label: label weighted by annotator confidence
    """
    if not labels:
        return {"agreement_pct": 1.0, "cohen_kappa": None, "majority_label": None, "weighted_label": None}

    pct = percentage_agreement(labels)
    kappa = cohen_kappa(labels)
    majority_label = Counter(labels).most_common(1)[0][0]

    # Weighted label: sum confidence per label, pick highest
    weight_map: Dict[str, float] = {}
    for label, conf in zip(labels, confidences):
        weight_map[label] = weight_map.get(label, 0.0) + conf
    weighted_label = max(weight_map, key=weight_map.get)

    return {
        "agreement_pct": round(pct, 4),
        "cohen_kappa": kappa,
        "majority_label": majority_label,
        "weighted_label": weighted_label,
    }
