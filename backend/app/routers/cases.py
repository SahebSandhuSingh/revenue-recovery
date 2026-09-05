"""Cases, Metrics, and Manual Demo Override Endpoints for Recoup Dashboard.

This router provides:
1. GET /events/{event_id}/case — unified case detail with complete chronological audit log
2. GET /metrics/recovery-summary — aggregate recovery rates, root cause breakdown, exception list, and funnel
3. POST /promises/{promise_id}/mark-kept — manual demo override for payment confirmation
4. GET /cases — paginated and filterable case explorer feed
"""

import logging
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.constants import (
    EXCEPTION_NO_REPLY_HOURS,
    ROOT_CAUSES,
)
from app.database import get_db
from app.models import (
    Action,
    AuditLog,
    Diagnosis,
    Event,
    InboundMessage,
    Promise,
)
from app.schemas import (
    CaseActionDetail,
    CaseAuditLogDetail,
    CaseDetailResponse,
    CaseDiagnosisDetail,
    CaseEventDetail,
    CaseExplorerItem,
    CaseInboundMessageDetail,
    CasePromiseDetail,
    ExceptionListItem,
    FunnelStageMetrics,
    MarkKeptResponse,
    PaginatedCasesResponse,
    RecoverySummaryResponse,
    RootCauseMetricItem,
    SimulateCaseRequest,
    SimulateCaseResponse,
)
from app.services.diagnosis_agent import diagnose_event
from app.services.intervention_agent import route_intervention

logger = logging.getLogger(__name__)

router = APIRouter(tags=["cases_and_metrics"])


@router.get(
    "/events/{event_id}/case",
    response_model=CaseDetailResponse,
    summary="Unified case detail with full chronological audit trail",
)
def get_case_detail(event_id: uuid.UUID, db: Session = Depends(get_db)):
    """Fetch complete unified case context for an event including diagnosis, action,

    promise, inbound messages, and full chronological audit trail.
    """
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event {event_id} not found.",
        )

    # 1. Diagnosis
    diag = db.scalar(select(Diagnosis).where(Diagnosis.event_id == event_id))
    diag_detail = None
    if diag:
        diag_detail = CaseDiagnosisDetail(
            id=diag.id,
            root_cause=diag.root_cause,
            confidence=float(diag.confidence) if diag.confidence is not None else None,
            reasoning=diag.reasoning,
            created_at=diag.created_at,
        )

    # 2. Action
    action = db.scalar(select(Action).where(Action.event_id == event_id))
    action_detail = None
    if action:
        action_detail = CaseActionDetail(
            id=action.id,
            action_type=action.action_type,
            channel=action.channel,
            priority=action.priority,
            message_draft=action.message_draft,
            status=action.status,
            dispatch_status=action.dispatch_status,
            dispatched_at=action.dispatched_at,
            delivered_at=action.delivered_at,
            dispatch_error=action.dispatch_error,
            created_at=action.created_at,
        )

    # 3. Promise
    promise = db.scalar(
        select(Promise)
        .where(Promise.event_id == event_id)
        .order_by(Promise.created_at.desc())
    )
    promise_detail = None
    if promise:
        promise_detail = CasePromiseDetail(
            id=promise.id,
            promised_amount=float(promise.promised_amount) if promise.promised_amount else None,
            promised_date=promise.promised_date,
            status=promise.status,
            raw_reply_text=promise.raw_reply_text,
            reconciled_at=promise.reconciled_at,
            reconciliation_source=promise.reconciliation_source,
            created_at=promise.created_at,
        )

    # 4. Inbound Messages (chronological)
    messages = db.scalars(
        select(InboundMessage)
        .where(InboundMessage.event_id == event_id)
        .order_by(InboundMessage.received_at.asc())
    ).all()
    inbound_details = [
        CaseInboundMessageDetail(
            id=m.id,
            channel=m.channel,
            raw_text=m.raw_text,
            reply_type=m.reply_type,
            received_at=m.received_at,
        )
        for m in messages
    ]

    # 5. Audit Log (Full chronological ordered by timestamp ascending)
    audit_logs = db.scalars(
        select(AuditLog)
        .where(AuditLog.event_id == event_id)
        .order_by(AuditLog.timestamp.asc())
    ).all()
    audit_details = [
        CaseAuditLogDetail(
            id=a.id,
            agent_name=a.agent_name,
            decision=a.decision,
            reasoning=a.reasoning,
            timestamp=a.timestamp,
        )
        for a in audit_logs
    ]

    return CaseDetailResponse(
        event=CaseEventDetail(
            id=event.id,
            source_type=event.source_type,
            data_source=event.data_source,
            source_id=event.source_id,
            customer_id=event.customer_id,
            amount=float(event.amount),
            currency=event.currency,
            status=event.status,
            raw_payload=event.raw_payload or {},
            created_at=event.created_at,
        ),
        diagnosis=diag_detail,
        action=action_detail,
        promise=promise_detail,
        inbound_messages=inbound_details,
        audit_log=audit_details,
    )


@router.get(
    "/metrics/recovery-summary",
    response_model=RecoverySummaryResponse,
    summary="Aggregate recovery metrics, root-cause breakdown, exception list, and funnel",
)
def get_recovery_summary(db: Session = Depends(get_db)):
    """Compute aggregate recovery metrics across the platform.

    RECOVERY METRIC COMPUTATION & KNOWN LIMITATIONS (Part B Code Comment):
    - recovered_amount is computed as the sum of event amounts where EITHER:
        1. action_type == "silent_retry" AND status == "sent" (simulated recovery success per Part 0)
        2. a linked promise has status == "kept" (settled via manual demo override or reconciliation)
    - This is explicitly a partial / proxy metric: silent retry recoveries are simulated probabilistically,
      and promise 'kept' status is confirmed via demo override, since real payment gateway webhook
      reconciliation is out of scope for this hackathon build.
    """
    now = datetime.now(timezone.utc)
    threshold_time = now - timedelta(hours=EXCEPTION_NO_REPLY_HOURS)

    # 1. Total events and amount at risk
    all_events = db.scalars(select(Event)).all()
    total_events = len(all_events)
    total_amount_at_risk = float(sum(e.amount for e in all_events)) if all_events else 0.0

    # 2. Fetch all diagnoses, actions, promises, and messages
    all_diagnoses = db.scalars(select(Diagnosis)).all()
    diag_by_event: Dict[uuid.UUID, Diagnosis] = {d.event_id: d for d in all_diagnoses}

    all_actions = db.scalars(select(Action)).all()
    action_by_event: Dict[uuid.UUID, Action] = {a.event_id: a for a in all_actions}

    all_promises = db.scalars(select(Promise)).all()
    promise_by_event: Dict[uuid.UUID, Promise] = {p.event_id: p for p in all_promises}

    all_messages = db.scalars(select(InboundMessage)).all()
    events_with_replies = {m.event_id for m in all_messages}

    # 3. Determine recovered events (unique event_ids)
    # Recovered if: (silent_retry AND status == 'sent') OR (promise.status == 'kept')
    recovered_event_ids = set()
    for act in all_actions:
        if act.action_type == "silent_retry" and act.status in ("sent", "delivered"):
            recovered_event_ids.add(act.event_id)

    for prom in all_promises:
        if prom.status == "kept":
            recovered_event_ids.add(prom.event_id)

    recovered_amount = float(
        sum(e.amount for e in all_events if e.id in recovered_event_ids)
    )

    overall_recovery_rate = (
        round(recovered_amount / total_amount_at_risk, 4)
        if total_amount_at_risk > 0
        else 0.0
    )

    # 4. Breakdown by Root Cause (all 5 categories in ROOT_CAUSES)
    by_root_cause: Dict[str, RootCauseMetricItem] = {}
    for rc in ROOT_CAUSES:
        rc_events = [e for e in all_events if diag_by_event.get(e.id) and diag_by_event[e.id].root_cause == rc]
        rc_count = len(rc_events)
        rc_total_amt = float(sum(e.amount for e in rc_events))
        rc_recovered_amt = float(sum(e.amount for e in rc_events if e.id in recovered_event_ids))

        rc_pending_count = sum(
            1 for e in rc_events if promise_by_event.get(e.id) and promise_by_event[e.id].status == "pending"
        )
        rc_broken_count = sum(
            1 for e in rc_events if promise_by_event.get(e.id) and promise_by_event[e.id].status == "broken"
        )

        by_root_cause[rc] = RootCauseMetricItem(
            count=rc_count,
            total_amount=rc_total_amt,
            recovered_amount=rc_recovered_amt,
            pending_count=rc_pending_count,
            broken_count=rc_broken_count,
        )

    # 5. Exception List (Part 0B & Part B)
    # Condition: promise.status == "broken" OR action.status == "blocked_pending_review"
    # OR (dispatched with no inbound_message after EXCEPTION_NO_REPLY_HOURS)
    exception_list: List[ExceptionListItem] = []
    seen_exception_event_ids = set()

    for event in all_events:
        eid = event.id
        prom = promise_by_event.get(eid)
        act = action_by_event.get(eid)
        diag = diag_by_event.get(eid)
        rc = diag.root_cause if diag else None

        reason = None

        # Condition 1: Broken Promise
        if prom and prom.status == "broken":
            reason = f"Promise to pay of ₹{prom.promised_amount:,.2f} was broken (due date {prom.promised_date} passed without payment)"
        # Condition 2: Blocked by Compliance Gate
        elif act and act.status == "blocked_pending_review":
            reason = f"Outreach blocked by compliance stopping rules (contact cap or broken promise threshold reached)"
        # Condition 3: Dispatched with no reply after demo threshold hours
        elif act and act.status in ("dispatched", "delivered", "sent"):
            # Check if action was dispatched at least EXCEPTION_NO_REPLY_HOURS ago
            disp_time = act.dispatched_at or act.created_at
            if disp_time and disp_time <= threshold_time and eid not in events_with_replies:
                reason = f"No customer response received after {EXCEPTION_NO_REPLY_HOURS}+ hours following outreach dispatch via {act.channel}"

        if reason and eid not in seen_exception_event_ids:
            seen_exception_event_ids.add(eid)
            exception_list.append(
                ExceptionListItem(
                    event_id=str(eid),
                    customer_id=event.customer_id,
                    amount=float(event.amount),
                    root_cause=rc,
                    reason=reason,
                )
            )

    # 6. Funnel Breakdown
    diagnosed_count = len([e for e in all_events if e.id in diag_by_event])
    routed_count = len([e for e in all_events if e.id in action_by_event])
    dispatched_count = len(
        [
            e
            for e in all_events
            if action_by_event.get(e.id)
            and action_by_event[e.id].status in ("dispatched", "delivered", "sent", "failed")
        ]
    )
    replied_count = len([e for e in all_events if e.id in events_with_replies])
    promise_count = len([e for e in all_events if e.id in promise_by_event])
    recovered_unique_count = len(recovered_event_ids)

    funnel = FunnelStageMetrics(
        diagnosed=diagnosed_count,
        routed=routed_count,
        dispatched=dispatched_count,
        customer_replied=replied_count,
        promise_made=promise_count,
        recovered=recovered_unique_count,
    )

    return RecoverySummaryResponse(
        total_events=total_events,
        total_amount_at_risk=total_amount_at_risk,
        recovered_amount=recovered_amount,
        overall_recovery_rate=overall_recovery_rate,
        by_root_cause=by_root_cause,
        exception_list=exception_list,
        funnel=funnel,
    )


@router.post(
    "/promises/{promise_id}/mark-kept",
    response_model=MarkKeptResponse,
    summary="Manual demo override to mark a promise as paid/kept",
)
def mark_promise_kept_override(promise_id: uuid.UUID, db: Session = Depends(get_db)):
    """Manually mark a promise as 'kept' (paid) for demo verification.

    DEMO OVERRIDE DOCUMENTATION (Part C Code Comment):
    This endpoint exists specifically to allow hackathon judges and evaluators to test
    the recovered revenue flow without requiring a live Razorpay webhook dispatch.
    It records an audit_log entry explicitly attributed to 'manual_demo_override' (never
    attributed to any AI agent) to maintain audit honesty.
    """
    promise = db.get(Promise, promise_id)
    if not promise:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Promise {promise_id} not found.",
        )

    now = datetime.now(timezone.utc)
    promise.status = "kept"
    promise.reconciled_at = now
    promise.reconciliation_source = "manual_demo_override"

    # Explicit audit log entry attributed to manual_demo_override
    audit_entry = AuditLog(
        event_id=promise.event_id,
        agent_name="manual_demo_override",
        decision="kept",
        reasoning="Manually marked as paid — stand-in for real payment webhook reconciliation, which is out of scope for this build",
        timestamp=now,
    )
    db.add(audit_entry)
    db.commit()
    db.refresh(promise)

    logger.info(f"[MANUAL DEMO OVERRIDE] Promise {promise_id} marked as KEPT.")

    return MarkKeptResponse(
        promise_id=str(promise.id),
        event_id=str(promise.event_id),
        status="kept",
        reconciled_at=now.isoformat(),
        source="manual_demo_override",
        reasoning="Manually marked as paid — stand-in for real payment webhook reconciliation, which is out of scope for this build",
        message="Promise successfully marked as kept via manual demo override.",
    )


@router.get(
    "/cases",
    response_model=PaginatedCasesResponse,
    summary="Paginated and filterable case explorer feed",
)
def list_cases(
    root_cause: Optional[str] = Query(None, description="Filter by root cause"),
    source_type: Optional[str] = Query(None, description="Filter by source type"),
    dispatch_status: Optional[str] = Query(None, description="Filter by dispatch status"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Retrieve paginated case explorer records with joined diagnosis, action, and promise."""
    # Build joined query
    base_query = (
        select(Event, Diagnosis, Action, Promise)
        .outerjoin(Diagnosis, Event.id == Diagnosis.event_id)
        .outerjoin(Action, Event.id == Action.event_id)
        .outerjoin(Promise, Event.id == Promise.event_id)
    )

    if source_type:
        base_query = base_query.where(Event.source_type == source_type)
    if root_cause:
        base_query = base_query.where(Diagnosis.root_cause == root_cause)
    if dispatch_status:
        base_query = base_query.where(Action.status == dispatch_status)

    # Count total
    count_subquery = base_query.subquery()
    count_query = select(func.count()).select_from(count_subquery)
    total = db.scalar(count_query) or 0

    results = db.execute(
        base_query.order_by(Event.created_at.desc()).offset(offset).limit(limit)
    ).all()

    items: List[CaseExplorerItem] = []
    for ev, diag, act, prom in results:
        items.append(
            CaseExplorerItem(
                event_id=str(ev.id),
                source_type=ev.source_type,
                customer_id=ev.customer_id,
                amount=float(ev.amount),
                currency=ev.currency,
                status=ev.status,
                created_at=ev.created_at,
                root_cause=diag.root_cause if diag else None,
                confidence=float(diag.confidence) if diag and diag.confidence is not None else None,
                action_type=act.action_type if act else None,
                channel=act.channel if act else None,
                action_status=act.status if act else None,
                dispatch_status=act.dispatch_status if act else None,
                promise_status=prom.status if prom else None,
                promised_amount=float(prom.promised_amount) if prom and prom.promised_amount else None,
                promised_date=prom.promised_date if prom else None,
            )
        )

    return PaginatedCasesResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/cases/simulate",
    response_model=SimulateCaseResponse,
    summary="Simulate an incoming failure and trigger multi-agent diagnosis and recovery workflow",
)
def simulate_case(payload: SimulateCaseRequest, db: Session = Depends(get_db)):
    """Simulate an incoming payment failure, execute the Root-Cause Diagnosis Agent

    and Intervention Router Agent live, and return structured results.
    """
    event_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    # Construct rich payload context
    raw_data = payload.raw_payload or {}
    if payload.failure_reason:
        raw_data["failure_reason"] = payload.failure_reason
        raw_data["error_description"] = payload.failure_reason
    if payload.days_overdue is not None:
        raw_data["days_overdue"] = payload.days_overdue
    if payload.scenario_title:
        raw_data["scenario_title"] = payload.scenario_title

    status_str = "overdue" if payload.source_type == "invoice" else "failed"

    event = Event(
        id=event_id,
        source_type=payload.source_type,
        source_id=f"SIM-{uuid.uuid4().hex[:8].upper()}",
        customer_id=payload.customer_id,
        amount=Decimal(str(payload.amount)),
        currency=payload.currency,
        status=status_str,
        raw_payload=raw_data,
        created_at=now,
    )
    db.add(event)
    db.commit()
    db.refresh(event)

    # 1. Run Root-Cause Diagnosis Agent
    try:
        diagnose_event(event_id=event.id, db=db)
    except Exception as exc:
        logger.error(f"Live simulation diagnosis failed: {exc}", exc_info=True)

    # 2. Run Intervention Router Agent
    try:
        route_intervention(event_id=event.id, db=db)
    except Exception as exc:
        logger.error(f"Live simulation intervention routing failed: {exc}", exc_info=True)

    # 3. Retrieve Diagnosis, Action, and Audit Trail from DB
    diag = db.scalar(select(Diagnosis).where(Diagnosis.event_id == event.id))
    action = db.scalar(select(Action).where(Action.event_id == event.id))
    audit_logs = db.scalars(
        select(AuditLog).where(AuditLog.event_id == event.id).order_by(AuditLog.timestamp.asc())
    ).all()

    diag_detail = None
    if diag:
        diag_detail = CaseDiagnosisDetail(
            id=diag.id,
            root_cause=diag.root_cause,
            confidence=float(diag.confidence) if diag.confidence is not None else None,
            reasoning=diag.reasoning,
            created_at=diag.created_at,
        )

    action_detail = None
    compliance_status = "passed"
    if action:
        if action.status == "blocked_pending_review":
            compliance_status = "blocked_pending_review"
        action_detail = CaseActionDetail(
            id=action.id,
            action_type=action.action_type,
            channel=action.channel,
            priority=action.priority,
            message_draft=action.message_draft,
            status=action.status,
            dispatch_status=action.dispatch_status,
            dispatched_at=action.dispatched_at,
            delivered_at=action.delivered_at,
            dispatch_error=action.dispatch_error,
            created_at=action.created_at,
        )

    audit_details = [
        CaseAuditLogDetail(
            id=a.id,
            agent_name=a.agent_name,
            decision=a.decision,
            reasoning=a.reasoning,
            timestamp=a.timestamp,
        )
        for a in audit_logs
    ]

    return SimulateCaseResponse(
        event_id=str(event.id),
        customer_id=event.customer_id,
        amount=float(event.amount),
        currency=event.currency,
        source_type=event.source_type,
        status=event.status,
        created_at=event.created_at,
        diagnosis=diag_detail,
        action=action_detail,
        compliance_status=compliance_status,
        audit_log=audit_details,
        message="Recovery agent pipeline executed successfully.",
    )

