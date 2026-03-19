"""
Feedback / annotation router.

POST /feedback/annotate          — submit a human annotation
GET  /feedback/{conversation_id} — get all annotations + agreement report
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models.annotation import Annotation
from schemas.annotation import AnnotationIn, AnnotationOut, AgreementReport
from feedback.agreement import compute_agreement
from feedback.router import decide_routing
from models.calibration import EvaluatorCalibration
from models.evaluation import Evaluation

router = APIRouter()


@router.post(
    "/annotate",
    response_model=AnnotationOut,
    summary="Submit a human annotation",
    description=(
        "Submit an annotation for a conversation. If multiple annotations exist "
        "for the same conversation + type, inter-annotator agreement is computed "
        "and a routing decision (auto-label vs. human review) is made."
    ),
)
def annotate(ann_in: AnnotationIn, db: Session = Depends(get_db)):
    # Persist the annotation
    ann = Annotation(
        conversation_id=ann_in.conversation_id,
        annotator_id=ann_in.annotator_id,
        annotation_type=ann_in.annotation_type,
        label=ann_in.label,
        confidence=ann_in.confidence,
        notes=ann_in.notes,
    )

    # Fetch existing annotations for same conv + type to compute routing
    existing = db.query(Annotation).filter(
        Annotation.conversation_id == ann_in.conversation_id,
        Annotation.annotation_type == ann_in.annotation_type,
    ).all()

    all_labels = [e.label for e in existing] + [ann_in.label]
    all_confs = [e.confidence for e in existing] + [ann_in.confidence]

    routing = decide_routing(all_labels, all_confs)
    ann.routing_decision = routing

    db.add(ann)
    db.commit()
    db.refresh(ann)

    # Update calibration table if we have an automated evaluation to compare
    ev = db.query(Evaluation).filter(
        Evaluation.conversation_id == ann_in.conversation_id
    ).first()
    if ev and ann_in.annotation_type == "tool_accuracy":
        llm_score = ev.tool_accuracy
        human_label = ann_in.label
        human_score = 1.0 if human_label == "correct" else 0.0
        agreement = abs((llm_score or 0.0) - human_score) < 0.3

        calibration = EvaluatorCalibration(
            conversation_id=ann_in.conversation_id,
            evaluator_name="tool_call_evaluator",
            metric="tool_accuracy",
            llm_score=llm_score,
            llm_label=None,
            human_score=human_score,
            human_label=human_label,
            agreement=agreement,
            agreement_delta=abs((llm_score or 0.0) - human_score),
        )
        db.add(calibration)
        db.commit()

    return AnnotationOut(
        id=str(ann.id),
        conversation_id=ann.conversation_id,
        annotator_id=ann.annotator_id,
        annotation_type=ann.annotation_type,
        label=ann.label,
        confidence=ann.confidence,
        notes=ann.notes,
        routing_decision=ann.routing_decision,
        created_at=ann.created_at,
    )


@router.get(
    "/{conversation_id}",
    response_model=AgreementReport,
    summary="Get annotation agreement report for a conversation",
)
def get_agreement(conversation_id: str, annotation_type: str = "tool_accuracy", db: Session = Depends(get_db)):
    annotations = db.query(Annotation).filter(
        Annotation.conversation_id == conversation_id,
        Annotation.annotation_type == annotation_type,
    ).all()

    if not annotations:
        raise HTTPException(status_code=404, detail="No annotations found")

    labels = [a.label for a in annotations]
    confs = [a.confidence for a in annotations]
    report = compute_agreement(labels, confs)
    routing = decide_routing(labels, confs)

    return AgreementReport(
        conversation_id=conversation_id,
        annotation_type=annotation_type,
        num_annotators=len(annotations),
        agreement_pct=report["agreement_pct"],
        cohen_kappa=report.get("cohen_kappa"),
        routing_decision=routing,
        labels=labels,
    )
