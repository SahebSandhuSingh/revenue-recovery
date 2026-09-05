import json
import logging
import os
import time
import uuid
from typing import Any, Dict, List, Optional
from openai import OpenAI, OpenAIError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.constants import ACTION_TYPES, CHANNELS, PRIORITIES
from app.models import Action, AuditLog, Diagnosis, Event
from app.services.compliance_service import is_customer_blocked, register_contact
from app.services.context_builder import build_case_context
from app.services.diagnosis_agent import (
    PACING_DELAY_SECONDS,
    check_mock_mode_disabled,
    is_mock_mode,
)

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are Recoup's Intervention Routing Specialist, an expert AI agent responsible for deciding WHAT recovery action to take for a diagnosed revenue-at-risk payment failure or overdue invoice, selecting the optimal communication channel, assigning an intervention priority, and drafting tailored customer-facing outreach copy.

Your task is to review the case context, historical customer reliability patterns, and the verified root-cause diagnosis to craft the optimal recovery plan.

Action Types & Intended Strategies:
1. 'silent_retry' — For transient technical glitches ('soft_decline'). Retry payment quietly in the background without contacting the customer. Channel MUST be 'none', and message_draft MUST be empty.
2. 'payment_method_update_request' — For permanent payment method invalidity ('hard_decline_or_expired', e.g. card expired, mandate revoked). Ask the customer to securely update their card or UPI mandate. Channels: 'email' or 'whatsapp'.
3. 'dispute_resolution_draft' — For contested charges or invoices ('dispute'). Draft a polite, professional response addressing the invoice dispute details, pricing, or goods verification. Channel: 'email'.
4. 'payment_plan_offer' — For genuine liquidity distress ('cash_flow_distress', 45+ days overdue, NSF). Propose a constructive, empathetic installment or deferred payment plan. Channels: 'whatsapp' or 'email'. Tone must be supportive and low-pressure.
5. 'friendly_nudge' — For isolated oversights ('forgetfulness', clean track record). Send a courteous, brief payment reminder. Channels: 'whatsapp' or 'sms'.

Channel Options:
- 'none' (ONLY valid for 'silent_retry')
- 'email'
- 'whatsapp'
- 'sms'
- 'voice' (For high-value B2B invoices with high priority, voice may be drafted as the designated channel)

Priority Options:
- 'low' (e.g. first-time reminders, minor soft declines)
- 'medium' (e.g. standard payment method updates, moderate overdue amounts)
- 'high' (e.g. severely overdue B2B invoices, high financial value at risk, complex disputes)

You MUST invoke the 'record_intervention' tool with:
- action_type: One of the 5 action taxonomy strings.
- channel: One of the 5 channels ('none', 'email', 'whatsapp', 'sms', 'voice').
- priority: 'low', 'medium', or 'high'.
- message_draft: Tailored customer outreach copy citing case specifics (e.g., retailer name, invoice number, amount in INR, days overdue, or failure reason). MUST be empty string if action_type is 'silent_retry'.
- reasoning: 1-3 sentences explaining why this specific action, channel, priority, and messaging fits the case.
"""

RECORD_INTERVENTION_TOOL = {
    "type": "function",
    "function": {
        "name": "record_intervention",
        "description": "Record the planned recovery intervention action for a diagnosed revenue-at-risk case",
        "parameters": {
            "type": "object",
            "properties": {
                "action_type": {
                    "type": "string",
                    "enum": ACTION_TYPES,
                    "description": "The planned recovery action category.",
                },
                "channel": {
                    "type": "string",
                    "enum": CHANNELS,
                    "description": "Communication channel for outreach ('none' only for silent_retry).",
                },
                "priority": {
                    "type": "string",
                    "enum": PRIORITIES,
                    "description": "Intervention urgency level.",
                },
                "message_draft": {
                    "type": "string",
                    "description": "Drafted customer-facing communication copy. Must be empty string if action_type is silent_retry.",
                },
                "reasoning": {
                    "type": "string",
                    "description": "1-3 sentences justifying the action type, channel, and priority.",
                },
            },
            "required": [
                "action_type",
                "channel",
                "priority",
                "message_draft",
                "reasoning",
            ],
            "additionalProperties": False,
        },
    },
}


def _generate_mock_intervention(
    combined_context: Dict[str, Any]
) -> Dict[str, Any]:
    """Generate deterministic mock intervention plan when Groq API key is unavailable."""
    print("\n" + "=" * 60)
    print("⚠️  MOCK MODE ACTIVE — NO REAL GROQ CALL WAS MADE")
    print("=" * 60 + "\n")

    root_cause = combined_context.get("diagnosis", {}).get("root_cause", "soft_decline")
    amount = combined_context.get("amount", 0.0)
    currency = combined_context.get("currency", "INR")
    source_type = combined_context.get("source_type", "checkout")
    raw_payload = combined_context.get("raw_payload", {})
    b2b = combined_context.get("b2b_context", {})
    invoice_num = raw_payload.get("invoice_number") or b2b.get("invoice_number", f"INV-{combined_context.get('source_id')}")

    if root_cause == "soft_decline":
        action_type = "silent_retry"
        channel = "none"
        priority = "low"
        message_draft = ""
        reasoning = "[MOCK] Soft decline diagnosed; scheduling background silent retry without customer outreach."
    elif root_cause == "hard_decline_or_expired":
        action_type = "payment_method_update_request"
        channel = "email" if source_type == "invoice" else "whatsapp"
        priority = "medium"
        message_draft = f"[MOCK] Dear Customer, your recent transaction of {currency} {amount:,.2f} could not be processed due to an expired/invalid payment method. Please update your details here: https://pay.recoup.dev/update"
        reasoning = f"[MOCK] Hard decline detected; requesting payment method update via {channel}."
    elif root_cause == "dispute":
        action_type = "dispute_resolution_draft"
        channel = "email"
        priority = "high"
        message_draft = f"[MOCK] Hello, Regarding invoice {invoice_num} ({currency} {amount:,.2f}), our operations team is reviewing your dispute details. We are committed to resolving any shipment/pricing discrepancies promptly."
        reasoning = f"[MOCK] Dispute filed for invoice {invoice_num}; drafted resolution response via email."
    elif root_cause == "cash_flow_distress":
        action_type = "payment_plan_offer"
        channel = "whatsapp" if amount < 50000 else "email"
        priority = "high" if amount >= 100000 else "medium"
        message_draft = f"[MOCK] Dear Partner, we understand cash flow fluctuations can arise. For pending invoice {invoice_num} of {currency} {amount:,.2f}, we would like to offer a flexible split payment plan. Let us know if this helps."
        reasoning = f"[MOCK] Cash flow distress diagnosed; proposing flexible payment plan for {currency} {amount:,.2f} via {channel}."
    else:  # forgetfulness
        action_type = "friendly_nudge"
        channel = "whatsapp"
        priority = "low"
        message_draft = f"[MOCK] Gentle reminder: Invoice {invoice_num} ({currency} {amount:,.2f}) is due. Please click here to settle at your convenience: https://pay.recoup.dev/pay"
        reasoning = f"[MOCK] Isolated delay on a reliable customer profile; sending friendly nudge via whatsapp."

    return {
        "action_type": action_type,
        "channel": channel,
        "priority": priority,
        "message_draft": message_draft,
        "reasoning": reasoning,
    }


def route_intervention(
    event_id: uuid.UUID,
    db: Session,
    client: Optional[OpenAI] = None,
    require_real_agent: bool = False,
) -> Dict[str, Any]:
    """Route and draft an intervention plan for a diagnosed event, gating via compliance limits.

    Args:
        event_id: Target event UUID.
        db: Database session.
        client: Optional Groq (OpenAI-compatible) client.
        require_real_agent: If True, raises RuntimeError when GROQ_API_KEY is unset.

    Returns:
        Dict[str, Any]: Action record dictionary.
    """
    if require_real_agent:
        check_mock_mode_disabled()

    # 1. Fetch existing diagnosis (must exist)
    diagnosis = db.scalar(
        select(Diagnosis).where(Diagnosis.event_id == event_id)
    )
    if not diagnosis:
        raise ValueError(
            f"No diagnosis found for event {event_id}. Event must be diagnosed before routing intervention."
        )

    # 2. Fetch parent event
    event = db.get(Event, event_id)
    if not event:
        raise ValueError(f"Event {event_id} not found.")

    # 3. Check if action already planned
    existing_action = db.scalar(
        select(Action).where(Action.event_id == event_id)
    )
    if existing_action:
        logger.info(f"Event {event_id} already has an action: {existing_action.action_type}")
        return {
            "id": str(existing_action.id),
            "event_id": str(existing_action.event_id),
            "action_type": existing_action.action_type,
            "channel": existing_action.channel,
            "priority": existing_action.priority,
            "message_draft": existing_action.message_draft,
            "status": existing_action.status,
            "created_at": existing_action.created_at.isoformat() if existing_action.created_at else None,
        }

    # 4. Assemble combined context
    case_context = build_case_context(event_id, db)
    combined_context = {
        **case_context,
        "diagnosis": {
            "root_cause": diagnosis.root_cause,
            "confidence": float(diagnosis.confidence) if diagnosis.confidence is not None else None,
            "reasoning": diagnosis.reasoning,
        },
    }

    # 5. Generate plan via Groq or Mock Fallback
    if is_mock_mode():
        action_output = _generate_mock_intervention(combined_context)
    else:
        if client is None:
            client = OpenAI(
                api_key=os.environ["GROQ_API_KEY"],
                base_url=os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1"),
            )

        model_name = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
        serialized_context = json.dumps(combined_context, indent=2, default=str)

        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"Please plan and draft the recovery intervention for this case:\n\n{serialized_context}",
                },
            ],
            tools=[RECORD_INTERVENTION_TOOL],
            tool_choice={"type": "function", "function": {"name": "record_intervention"}},
            temperature=0.1,
        )

        choice = response.choices[0]
        if not choice.message.tool_calls:
            raise RuntimeError(f"Groq did not return tool_calls for event {event_id}")

        tool_call = choice.message.tool_calls[0]
        action_output = json.loads(tool_call.function.arguments)

    action_type = action_output.get("action_type")
    channel = action_output.get("channel")
    priority = action_output.get("priority", "medium")
    message_draft = action_output.get("message_draft", "")
    reasoning = action_output.get("reasoning", "")

    # Validation & Invariant Clamping
    if action_type not in ACTION_TYPES:
        raise ValueError(f"Invalid action_type '{action_type}' returned by agent.")
    if channel not in CHANNELS:
        raise ValueError(f"Invalid channel '{channel}' returned by agent.")
    if priority not in PRIORITIES:
        priority = "medium"

    # Enforce channel 'none' solely for 'silent_retry'
    if action_type == "silent_retry":
        if channel != "none" or message_draft != "":
            logger.warning(
                f"Clamping silent_retry invariants for event {event_id}: setting channel='none' and empty message_draft."
            )
            channel = "none"
            message_draft = ""
    elif channel == "none":
        logger.warning(
            f"Action type '{action_type}' cannot have channel='none'; clamping to 'email'."
        )
        channel = "email"

    # 6. Compliance Gating Layer (Part F)
    # Check stopping rules before assigning action status
    action_status = "planned"
    customer_id = event.customer_id

    if channel != "none":
        if is_customer_blocked(customer_id, db):
            action_status = "blocked_pending_review"
            logger.warning(
                f"Compliance Gate: Customer {customer_id} is blocked. Marking action as 'blocked_pending_review'."
            )
            # Write compliance gate audit entry
            compliance_audit = AuditLog(
                event_id=event_id,
                agent_name="compliance_gate",
                decision="blocked",
                reasoning=f"Customer {customer_id} has reached escalation threshold, action held for human review",
            )
            db.add(compliance_audit)
        else:
            # Register contact attempt if customer is not blocked
            register_contact(customer_id, db)

    # 7. Persist action
    action = Action(
        event_id=event_id,
        action_type=action_type,
        channel=channel,
        priority=priority,
        message_draft=message_draft if message_draft else None,
        status=action_status,
    )
    db.add(action)

    # 8. Audit Trail Logging for Intervention Agent
    audit_entry = AuditLog(
        event_id=event_id,
        agent_name="intervention_router_agent",
        decision=action_type,
        reasoning=reasoning,
    )
    db.add(audit_entry)

    db.commit()
    db.refresh(action)

    return {
        "id": str(action.id),
        "event_id": str(action.event_id),
        "action_type": action.action_type,
        "channel": action.channel,
        "priority": action.priority,
        "message_draft": action.message_draft,
        "status": action.status,
        "created_at": action.created_at.isoformat() if action.created_at else None,
    }


def run_intervention_batch(
    db: Session,
    client: Optional[OpenAI] = None,
    require_real_agent: bool = False,
) -> Dict[str, Any]:
    """Plan interventions for all diagnosed events without an existing action.

    Args:
        db: Database session.
        client: Optional Groq (OpenAI-compatible) client.
        require_real_agent: If True, raises error when GROQ_API_KEY is missing.

    Returns:
        Dict[str, Any]: Batch summary with total_processed, distribution, and failures list.
    """
    if require_real_agent:
        check_mock_mode_disabled()

    # Find all events that have a diagnosis but no planned action
    diagnosed_subquery = select(Diagnosis.event_id)
    action_subquery = select(Action.event_id)

    pending_events = db.scalars(
        select(Event)
        .where(
            Event.id.in_(diagnosed_subquery),
            Event.id.not_in(action_subquery),
        )
        .order_by(Event.created_at.asc())
    ).all()

    total_pending = len(pending_events)
    logger.info(f"Found {total_pending} diagnosed events needing intervention routing.")

    processed_count = 0
    by_action_type: Dict[str, int] = {at: 0 for at in ACTION_TYPES}
    by_channel: Dict[str, int] = {ch: 0 for ch in CHANNELS}
    failures: List[Dict[str, Any]] = []

    # Capped at max 2 retries per event (total 3 attempts)
    max_retries = 2

    for idx, ev in enumerate(pending_events, start=1):
        success = False
        last_error = ""

        for attempt in range(max_retries + 1):
            try:
                res = route_intervention(
                    ev.id,
                    db,
                    client=client,
                    require_real_agent=require_real_agent,
                )
                at = res["action_type"]
                ch = res["channel"]
                by_action_type[at] = by_action_type.get(at, 0) + 1
                by_channel[ch] = by_channel.get(ch, 0) + 1
                processed_count += 1
                success = True
                logger.info(
                    f"[{idx}/{total_pending}] Routed event {ev.id} -> {at} via {ch} ({res['priority']}, status={res['status']})"
                )
                break
            except OpenAIError as oe:
                last_error = f"Groq API error: {str(oe)}"
                logger.warning(
                    f"Attempt {attempt + 1} failed for event {ev.id}: {last_error}"
                )
                if attempt < max_retries:
                    time.sleep(2 ** attempt)
            except Exception as exc:
                last_error = str(exc)
                logger.error(
                    f"Attempt {attempt + 1} failed for event {ev.id}: {last_error}"
                )
                if attempt < max_retries:
                    time.sleep(1)

        if not success:
            failures.append(
                {
                    "event_id": str(ev.id),
                    "error": last_error,
                    "retry_count": max_retries,
                }
            )

        # Pacing: space out real API calls to stay under Groq's TPM ceiling
        # during a burst, independent of the failure-only backoff above.
        if not is_mock_mode() and idx < total_pending:
            time.sleep(PACING_DELAY_SECONDS)

    return {
        "total_processed": processed_count,
        "by_action_type": by_action_type,
        "by_channel": by_channel,
        "failures": failures,
    }
