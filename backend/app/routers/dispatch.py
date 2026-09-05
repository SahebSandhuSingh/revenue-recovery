import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import (
    DispatchActionResponse,
    DispatchBatchSummary,
    ReconcilePaymentResponse,
    ReconciliationBatchSummary,
)
import os
from app.services.dispatch_service import dispatch_action, run_dispatch_batch, run_silent_retries
from app.services.reconciliation_service import (
    reconcile_payment,
    simulate_payment_reconciliation,
)

router = APIRouter(tags=["dispatch_and_reconciliation"])


@router.post(
    "/dispatch/run",
    response_model=DispatchBatchSummary,
    summary="Dispatch all planned actions through channel stubs",
)
def dispatch_batch_endpoint(
    require_real_dispatch: bool = Query(
        False,
        description="If True, raises error when real dispatch credentials (Twilio/SMTP) are missing.",
    ),
    db: Session = Depends(get_db),
):
    """Execute simulated dispatch for all planned actions."""
    if require_real_dispatch:
        twilio_sid = os.getenv("TWILIO_ACCOUNT_SID")
        smtp_host = os.getenv("SMTP_HOST")
        if not (twilio_sid or smtp_host):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Real dispatch credentials (TWILIO_ACCOUNT_SID, SMTP_HOST) not configured.",
            )
    try:
        summary = run_dispatch_batch(db)
        return summary
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Dispatch batch failed: {str(exc)}",
        )


@router.post(
    "/retry/run",
    summary="Execute or re-evaluate silent retries with ~40/60 outcome weighting",
)
def retry_run_endpoint(db: Session = Depends(get_db)):
    """Execute silent retries with ~40/60 outcome weighting."""
    try:
        summary = run_silent_retries(db)
        return {
            "total_silent_retries": summary["total_silent_retries"],
            "simulated_successes": summary["sent_count"],
            "simulated_still_failing": summary["failed_count"],
            "by_dispatch_status": summary["by_status"],
            "by_status": summary["by_status"],
        }
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Silent retry execution failed: {str(exc)}",
        )


@router.post(
    "/dispatch/{action_id}",
    response_model=DispatchActionResponse,
    summary="Dispatch a single action by ID",
)
def dispatch_single_endpoint(action_id: uuid.UUID, db: Session = Depends(get_db)):
    """Execute simulated dispatch for a single planned action."""
    try:
        result = dispatch_action(action_id, db)
        return result
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(ve),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Dispatch failed: {str(exc)}",
        )


@router.post(
    "/reconcile/{promise_id}",
    response_model=ReconcilePaymentResponse,
    summary="Manually reconcile a single promise as kept",
)
def reconcile_single_endpoint(
    promise_id: uuid.UUID,
    source: str = Query("manual", description="Reconciliation source"),
    db: Session = Depends(get_db),
):
    """Mark a specific promise as 'kept' (payment confirmed)."""
    try:
        result = reconcile_payment(promise_id, db, source=source)
        return result
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(ve),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Reconciliation failed: {str(exc)}",
        )


@router.post(
    "/reconcile/simulate/batch",
    response_model=ReconciliationBatchSummary,
    summary="Simulate payment reconciliation for delivered actions' promises",
)
def simulate_reconciliation_endpoint(
    reconciliation_rate: float = Query(
        0.60,
        ge=0.0,
        le=1.0,
        description="Fraction of eligible promises to reconcile (0.0-1.0)",
    ),
    db: Session = Depends(get_db),
):
    """Simulate payment confirmations for pending promises linked to delivered actions."""
    try:
        summary = simulate_payment_reconciliation(db, reconciliation_rate=reconciliation_rate)
        return summary
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Simulated reconciliation failed: {str(exc)}",
        )
