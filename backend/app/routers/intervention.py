import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Action, Event
from app.schemas import (
    ActionBatchSummary,
    ActionResponse,
    PaginatedActionsResponse,
)
from app.services.intervention_agent import run_intervention_batch

router = APIRouter(tags=["intervention"])


@router.post(
    "/route/run",
    response_model=ActionBatchSummary,
    summary="Execute batch intervention routing for all diagnosed events without planned actions",
)
def run_batch_intervention_endpoint(
    require_real_agent: bool = Query(
        False,
        description="If True, raises an error when GROQ_API_KEY is not configured instead of using mock fallback.",
    ),
    db: Session = Depends(get_db),
):
    """Route and draft recovery interventions for all diagnosed events needing actions."""
    try:
        summary = run_intervention_batch(db=db, require_real_agent=require_real_agent)
        return summary
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Batch intervention routing failed: {str(exc)}",
        )


@router.get(
    "/actions",
    response_model=PaginatedActionsResponse,
    summary="List planned recovery actions with pagination and optional filters",
)
def list_actions(
    action_type: Optional[str] = Query(
        None,
        description="Filter by action type (silent_retry, payment_method_update_request, dispute_resolution_draft, payment_plan_offer, friendly_nudge)",
    ),
    channel: Optional[str] = Query(
        None,
        description="Filter by channel (none, email, whatsapp, sms, voice)",
    ),
    limit: int = Query(50, ge=1, le=500, description="Items to return"),
    offset: int = Query(0, ge=0, description="Items to skip"),
    db: Session = Depends(get_db),
):
    """Retrieve paginated list of actions joined with parent event details."""
    base_query = (
        select(
            Action,
            Event.source_type,
            Event.customer_id,
            Event.amount,
            Event.currency,
        )
        .join(Event, Action.event_id == Event.id)
    )

    count_query = select(func.count(Action.id))

    if action_type:
        base_query = base_query.where(Action.action_type == action_type)
        count_query = count_query.where(Action.action_type == action_type)

    if channel:
        base_query = base_query.where(Action.channel == channel)
        count_query = count_query.where(Action.channel == channel)

    total = db.scalar(count_query) or 0
    results = db.execute(
        base_query.order_by(Action.created_at.desc()).offset(offset).limit(limit)
    ).all()

    items = []
    for act, src_type, cust_id, amount, curr in results:
        items.append(
            ActionResponse(
                id=act.id,
                event_id=act.event_id,
                action_type=act.action_type,
                channel=act.channel,
                priority=act.priority,
                message_draft=act.message_draft,
                status=act.status,
                created_at=act.created_at,
                source_type=src_type,
                customer_id=cust_id,
                amount=amount,
                currency=curr,
            )
        )

    return PaginatedActionsResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/events/{event_id}/action",
    response_model=ActionResponse,
    summary="Get planned action for a specific event",
)
def get_event_action(event_id: uuid.UUID, db: Session = Depends(get_db)):
    """Retrieve planned intervention action for a specific event ID (404 if none)."""
    row = db.execute(
        select(
            Action,
            Event.source_type,
            Event.customer_id,
            Event.amount,
            Event.currency,
        )
        .join(Event, Action.event_id == Event.id)
        .where(Action.event_id == event_id)
    ).first()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No planned action found for event ID {event_id}.",
        )

    act, src_type, cust_id, amount, curr = row
    return ActionResponse(
        id=act.id,
        event_id=act.event_id,
        action_type=act.action_type,
        channel=act.channel,
        priority=act.priority,
        message_draft=act.message_draft,
        status=act.status,
        created_at=act.created_at,
        source_type=src_type,
        customer_id=cust_id,
        amount=amount,
        currency=curr,
    )
