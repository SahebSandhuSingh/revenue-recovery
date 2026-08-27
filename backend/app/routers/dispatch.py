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
from app.services.dispatch_service import dispatch_action, run_dispatch_batch
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
def dispatch_batch_endpoint(db: Session = Depends(get_db)):
    """Execute simulated dispatch for all planned actions."""
    try:
        summary = run_dispatch_batch(db)
        return summary
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Dispatch batch failed: {str(exc)}",
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
