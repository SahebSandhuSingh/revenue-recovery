import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Diagnosis, Event
from app.schemas import (
    DiagnosisBatchSummary,
    DiagnosisResponse,
    PaginatedDiagnosesResponse,
    SyncResult,
)
from app.services.diagnosis_agent import run_diagnosis_batch
from app.services.event_sync import sync_invoices_to_events

router = APIRouter(tags=["diagnosis"])


@router.post(
    "/sync/invoices-to-events",
    response_model=SyncResult,
    summary="Synchronize overdue and disputed invoices to events table",
)
def sync_invoices_endpoint(db: Session = Depends(get_db)):
    """Find all overdue/disputed invoices lacking an event record and create event rows."""
    count = sync_invoices_to_events(db)
    return SyncResult(
        synced_count=count,
        message=f"Successfully synced {count} new invoice event(s).",
    )


@router.post(
    "/diagnose/run",
    response_model=DiagnosisBatchSummary,
    summary="Execute batch root-cause diagnosis for all undiagnosed events",
)
def run_batch_diagnosis_endpoint(
    require_real_agent: bool = Query(
        False,
        description="If True, raises error when GROQ_API_KEY is not configured instead of using mock fallback.",
    ),
    db: Session = Depends(get_db),
):
    """Sync invoices and run root-cause diagnosis on all undiagnosed events."""
    try:
        summary = run_diagnosis_batch(db=db, require_real_agent=require_real_agent)
        return summary
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Batch diagnosis failed: {str(exc)}",
        )


@router.get(
    "/diagnoses",
    response_model=PaginatedDiagnosesResponse,
    summary="List diagnoses with pagination and optional root_cause filter",
)
def list_diagnoses(
    root_cause: Optional[str] = Query(
        None,
        description="Filter by root cause: soft_decline, hard_decline_or_expired, dispute, cash_flow_distress, forgetfulness",
    ),
    limit: int = Query(50, ge=1, le=500, description="Items to return"),
    offset: int = Query(0, ge=0, description="Items to skip"),
    db: Session = Depends(get_db),
):
    """Retrieve paginated list of diagnoses joined with parent event details."""
    base_query = (
        select(
            Diagnosis,
            Event.source_type,
            Event.customer_id,
            Event.amount,
            Event.currency,
        )
        .join(Event, Diagnosis.event_id == Event.id)
    )

    count_query = select(func.count(Diagnosis.id))

    if root_cause:
        base_query = base_query.where(Diagnosis.root_cause == root_cause)
        count_query = count_query.where(Diagnosis.root_cause == root_cause)

    total = db.scalar(count_query) or 0
    results = db.execute(
        base_query.order_by(Diagnosis.created_at.desc()).offset(offset).limit(limit)
    ).all()

    items = []
    for diag, src_type, cust_id, amount, curr in results:
        items.append(
            DiagnosisResponse(
                id=diag.id,
                event_id=diag.event_id,
                root_cause=diag.root_cause,
                confidence=float(diag.confidence) if diag.confidence is not None else None,
                reasoning=diag.reasoning,
                created_at=diag.created_at,
                source_type=src_type,
                customer_id=cust_id,
                amount=amount,
                currency=curr,
            )
        )

    return PaginatedDiagnosesResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/events/{event_id}/diagnosis",
    response_model=DiagnosisResponse,
    summary="Get diagnosis for a specific event",
)
def get_event_diagnosis(event_id: uuid.UUID, db: Session = Depends(get_db)):
    """Retrieve diagnosis for a specific event ID."""
    row = db.execute(
        select(
            Diagnosis,
            Event.source_type,
            Event.customer_id,
            Event.amount,
            Event.currency,
        )
        .join(Event, Diagnosis.event_id == Event.id)
        .where(Diagnosis.event_id == event_id)
    ).first()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No diagnosis found for event ID {event_id}.",
        )

    diag, src_type, cust_id, amount, curr = row
    return DiagnosisResponse(
        id=diag.id,
        event_id=diag.event_id,
        root_cause=diag.root_cause,
        confidence=float(diag.confidence) if diag.confidence is not None else None,
        reasoning=diag.reasoning,
        created_at=diag.created_at,
        source_type=src_type,
        customer_id=cust_id,
        amount=amount,
        currency=curr,
    )
