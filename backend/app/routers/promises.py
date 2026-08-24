import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ComplianceLimit, Event, Promise
from app.schemas import (
    ComplianceStatusResponse,
    PaginatedComplianceResponse,
    PaginatedPromisesResponse,
    PromiseEvaluationSummary,
    PromiseResponse,
    ReplyProcessingBatchSummary,
)
from app.services.compliance_service import count_broken_promises_for_customer
from app.services.promise_agent import run_reply_processing_batch
from app.services.promise_evaluator import evaluate_promise_statuses

router = APIRouter(tags=["promises_and_compliance"])


@router.post(
    "/replies/process",
    response_model=ReplyProcessingBatchSummary,
    summary="Process and classify all unclassified inbound customer replies",
)
def process_replies_endpoint(
    require_real_agent: bool = Query(
        False,
        description="If True, raises error when OPENAI_API_KEY is not configured.",
    ),
    db: Session = Depends(get_db),
):
    """Classify pending inbound messages, extract promises, and update action/event state."""
    try:
        summary = run_reply_processing_batch(db=db, require_real_agent=require_real_agent)
        return summary
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Reply processing batch failed: {str(exc)}",
        )


@router.post(
    "/promises/evaluate",
    response_model=PromiseEvaluationSummary,
    summary="Evaluate pending promises and transition expired commitments to broken",
)
def evaluate_promises_endpoint(db: Session = Depends(get_db)):
    """Evaluate all pending promises against the current date."""
    summary = evaluate_promise_statuses(db)
    return summary


@router.get(
    "/promises",
    response_model=PaginatedPromisesResponse,
    summary="List promises with pagination and optional status filter",
)
def list_promises(
    status: Optional[str] = Query(
        None, description="Filter by promise status (pending, kept, broken)"
    ),
    limit: int = Query(50, ge=1, le=500, description="Items to return"),
    offset: int = Query(0, ge=0, description="Items to skip"),
    db: Session = Depends(get_db),
):
    """Retrieve paginated list of promises joined with parent event details."""
    base_query = (
        select(
            Promise,
            Event.source_type,
            Event.customer_id,
            Event.amount,
            Event.currency,
        )
        .join(Event, Promise.event_id == Event.id)
    )

    count_query = select(func.count(Promise.id))

    if status:
        base_query = base_query.where(Promise.status == status)
        count_query = count_query.where(Promise.status == status)

    total = db.scalar(count_query) or 0
    results = db.execute(
        base_query.order_by(Promise.created_at.desc()).offset(offset).limit(limit)
    ).all()

    items = []
    for prom, src_type, cust_id, amount, curr in results:
        items.append(
            PromiseResponse(
                id=prom.id,
                event_id=prom.event_id,
                promised_amount=prom.promised_amount,
                promised_date=prom.promised_date,
                status=prom.status,
                raw_reply_text=prom.raw_reply_text,
                created_at=prom.created_at,
                source_type=src_type,
                customer_id=cust_id,
                amount=amount,
                currency=curr,
            )
        )

    return PaginatedPromisesResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/compliance/{customer_id}",
    response_model=ComplianceStatusResponse,
    summary="Get compliance and escalation status for a customer",
)
def get_customer_compliance(customer_id: str, db: Session = Depends(get_db)):
    """Retrieve compliance record for a customer ID (404 if no record exists)."""
    record = db.scalar(
        select(ComplianceLimit).where(ComplianceLimit.customer_id == customer_id)
    )

    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No compliance record found for customer '{customer_id}'.",
        )

    broken_count = count_broken_promises_for_customer(customer_id, db)
    return ComplianceStatusResponse(
        id=record.id,
        customer_id=record.customer_id,
        contact_count=record.contact_count,
        last_contact_at=record.last_contact_at,
        escalation_flag=record.escalation_flag,
        broken_promises_count=broken_count,
        escalation_reason="Escalated due to contact limit or broken promises" if record.escalation_flag else None,
    )


@router.get(
    "/compliance",
    response_model=PaginatedComplianceResponse,
    summary="List compliance records with pagination and optional escalation_flag filter",
)
def list_compliance_records(
    escalation_flag: Optional[bool] = Query(
        None, description="Filter to only escalated/blocked customers (FIX 5)"
    ),
    limit: int = Query(50, ge=1, le=500, description="Items to return"),
    offset: int = Query(0, ge=0, description="Items to skip"),
    db: Session = Depends(get_db),
):
    """Retrieve paginated list of compliance records with optional escalation filtering."""
    base_query = select(ComplianceLimit)
    count_query = select(func.count(ComplianceLimit.id))

    if escalation_flag is not None:
        base_query = base_query.where(ComplianceLimit.escalation_flag == escalation_flag)
        count_query = count_query.where(ComplianceLimit.escalation_flag == escalation_flag)

    total = db.scalar(count_query) or 0
    records = db.scalars(
        base_query.order_by(ComplianceLimit.contact_count.desc()).offset(offset).limit(limit)
    ).all()

    items = []
    for rec in records:
        broken_count = count_broken_promises_for_customer(rec.customer_id, db)
        items.append(
            ComplianceStatusResponse(
                id=rec.id,
                customer_id=rec.customer_id,
                contact_count=rec.contact_count,
                last_contact_at=rec.last_contact_at,
                escalation_flag=rec.escalation_flag,
                broken_promises_count=broken_count,
                escalation_reason="Escalation threshold reached" if rec.escalation_flag else None,
            )
        )

    return PaginatedComplianceResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )
