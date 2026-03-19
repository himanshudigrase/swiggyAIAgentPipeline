"""
Meta-evaluation router.

GET /meta/calibration — LLM evaluator agreement with human annotations
GET /meta/coverage    — failure category coverage
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timezone
from typing import List

from database import get_db
from models.calibration import EvaluatorCalibration
from schemas.suggestion import CalibrationReport, CalibrationMetric

router = APIRouter()


@router.get(
    "/calibration",
    response_model=CalibrationReport,
    summary="LLM evaluator vs. human annotation agreement",
    description=(
        "Shows how well the automated LLM-based evaluators agree with human annotations. "
        "A high agreement_pct means the evaluator is well-calibrated. "
        "Low agreement = the evaluator needs recalibration."
    ),
)
def get_calibration(db: Session = Depends(get_db)):
    # Fetch all calibration rows and aggregate in Python (avoids dialect-specific CAST issues)
    all_rows = db.query(EvaluatorCalibration).all()

    # Group by (evaluator_name, metric)
    from collections import defaultdict
    groups: dict = defaultdict(list)
    for row in all_rows:
        key = (row.evaluator_name, row.metric)
        groups[key].append(row)

    metrics = []
    for (evaluator_name, metric), rows in groups.items():
        total = len(rows)
        agreed = sum(1 for r in rows if r.agreement is True)
        agreement_pct = agreed / total if total else 0.0
        deltas = [r.agreement_delta for r in rows if r.agreement_delta is not None]
        avg_delta = sum(deltas) / len(deltas) if deltas else 0.0
        metrics.append(CalibrationMetric(
            evaluator_name=evaluator_name,
            metric=metric,
            total_comparisons=total,
            agreement_pct=round(agreement_pct, 4),
            avg_delta=round(avg_delta, 4),
        ))

    total = db.query(func.count(EvaluatorCalibration.id)).scalar() or 0

    return CalibrationReport(
        total_calibration_points=total,
        metrics=metrics,
        generated_at=datetime.now(timezone.utc),
    )


@router.get(
    "/coverage",
    summary="Failure category coverage",
    description="Identifies which failure categories exist in recent evaluations and how many are flagged.",
)
def get_coverage(db: Session = Depends(get_db)):
    from models.evaluation import Evaluation
    evals = db.query(Evaluation).order_by(Evaluation.created_at.desc()).limit(100).all()

    coverage = {}
    for ev in evals:
        if ev.issues_detected:
            for issue in ev.issues_detected:
                t = issue.get("type", "unknown")
                coverage[t] = coverage.get(t, 0) + 1

    return {
        "scanned_evaluations": len(evals),
        "issue_categories": coverage,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
