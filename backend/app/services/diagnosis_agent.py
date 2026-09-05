import json
import logging
import os
import time
import uuid
from decimal import Decimal
from typing import Any, Dict, List, Optional
from openai import OpenAI, OpenAIError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.constants import ROOT_CAUSES
from app.models import Action, AuditLog, Diagnosis, Event
from app.services.context_builder import build_case_context
from app.services.event_sync import sync_invoices_to_events

logger = logging.getLogger(__name__)

# Groq free tier: 30 requests/min, 8,000 tokens/min. A pacing delay between
# real API calls in batch runs keeps bursts well under the TPM ceiling
# (the binding constraint here, not RPM) rather than relying solely on
# after-the-fact retry/backoff.
PACING_DELAY_SECONDS = 3

SYSTEM_PROMPT = """You are Recoup's Root-Cause Diagnosis Specialist, an expert AI agent dedicated to accurately diagnosing payment failures and revenue-at-risk events across B2B invoice cycles and consumer payment gateways.

Your task is to analyze the case context, historical customer reliability patterns, and raw payment payloads to determine the true underlying root cause.

You MUST choose exactly ONE root cause from this fixed taxonomy:
1. 'soft_decline' — Retryable technical or network glitches (e.g. gateway timeout, bank switch down, momentary NPCI failure, OTP delay).
2. 'hard_decline_or_expired' — Permanently invalid payment methods (e.g. expired card, revoked UPI mandate, closed/frozen bank account, permanently blocked card).
3. 'dispute' — Customer or retailer actively contesting the charge or invoice (e.g. damaged goods, pricing disagreement, delivery mismatch, invoice dispute status).
4. 'cash_flow_distress' — Repeated non-sufficient funds (NSF), severely overdue invoices (45+ days late), chronic delinquency, or persistent low balance across billing cycles.
5. 'forgetfulness' — Isolated oversight on an otherwise pristine payment record (e.g. first offense, >=90% on-time payment track record, single late cycle with standard overdue days).

You MUST invoke the 'record_diagnosis' tool with:
- root_cause: One of the 5 taxonomy strings above.
- confidence: A calibrated score between 0.0 and 1.0.
- reasoning: 1-3 sentences directly citing evidence from the case context (e.g., error codes, days overdue, historical payment percentages, or dispute flags).
"""

RECORD_DIAGNOSIS_TOOL = {
    "type": "function",
    "function": {
        "name": "record_diagnosis",
        "description": "Record the diagnosed root cause for a revenue-at-risk case",
        "parameters": {
            "type": "object",
            "properties": {
                "root_cause": {
                    "type": "string",
                    "enum": ROOT_CAUSES,
                    "description": "The diagnosed root cause category.",
                },
                "confidence": {
                    "type": "number",
                    "minimum": 0.0,
                    "maximum": 1.0,
                    "description": "Confidence score between 0.0 and 1.0.",
                },
                "reasoning": {
                    "type": "string",
                    "description": "1-3 sentences explaining the concrete evidence used from the case file.",
                },
            },
            "required": ["root_cause", "confidence", "reasoning"],
            "additionalProperties": False,
        },
    },
}


def is_mock_mode() -> bool:
    """Return True if GROQ_API_KEY is not configured."""
    return not os.getenv("GROQ_API_KEY") or os.getenv("GROQ_API_KEY", "").strip() == ""


def check_mock_mode_disabled() -> None:
    """Raise an exception if mock mode is active (FIX 1)."""
    if is_mock_mode():
        raise RuntimeError(
            "Mock mode is active because GROQ_API_KEY is not set. "
            "Batch execution was aborted due to require_real_agent=True."
        )


def _generate_mock_diagnosis(context: Dict[str, Any]) -> Dict[str, Any]:
    """Generate an unmistakable mock diagnosis when Groq API key is unavailable (FIX 1)."""
    print("\n" + "=" * 60)
    print("⚠️  MOCK MODE ACTIVE — NO REAL GROQ CALL WAS MADE")
    print("=" * 60 + "\n")

    source_type = context.get("source_type")
    raw_payload = context.get("raw_payload", {})

    # Heuristic mock categorization
    if source_type == "invoice":
        b2b = context.get("b2b_context", {})
        cust_hist = b2b.get("customer_history", {})
        status = context.get("status")
        days_overdue = b2b.get("days_overdue", 0)

        if status == "disputed":
            root_cause = "dispute"
            reasoning = f"[MOCK] Invoice {raw_payload.get('invoice_number')} is marked as disputed by retailer."
        elif days_overdue >= 45 or cust_hist.get("pct_paid_on_time", 0) < 50:
            root_cause = "cash_flow_distress"
            reasoning = f"[MOCK] Invoice is {days_overdue} days overdue with historical on-time rate of {cust_hist.get('pct_paid_on_time')}%, indicating liquidity distress."
        else:
            root_cause = "forgetfulness"
            reasoning = f"[MOCK] Retailer has {cust_hist.get('pct_paid_on_time')}% on-time track record; isolated delay of {days_overdue} days indicates oversight."
    else:
        err_reason = raw_payload.get("error_reason", "")
        err_code = raw_payload.get("error_code", "")
        mandate_status = raw_payload.get("mandate_status", "")

        if "expired" in err_reason or "revoked" in err_reason or mandate_status in ["revoked", "expired"] or "blocked" in err_reason:
            root_cause = "hard_decline_or_expired"
            reasoning = f"[MOCK] Hard decline detected from payload: error_reason='{err_reason}', mandate_status='{mandate_status}'."
        elif "insufficient" in err_reason or "NSF" in err_code or "LOW_BALANCE" in err_code:
            root_cause = "cash_flow_distress"
            reasoning = f"[MOCK] Consumer debit declined for non-sufficient funds ({err_code}) indicating liquidity shortfall."
        else:
            root_cause = "soft_decline"
            reasoning = f"[MOCK] Transient technical error identified from error_code='{err_code}' / reason='{err_reason}'."

    return {
        "root_cause": root_cause,
        "confidence": 0.0,  # FIX 1: Sentinel value 0.0 for mock output
        "reasoning": reasoning,
    }


def diagnose_event(
    event_id: uuid.UUID,
    db: Session,
    client: Optional[OpenAI] = None,
) -> Dict[str, Any]:
    """Diagnose a single event using Groq function calling or fallback mock mode.

    Args:
        event_id: Event UUID to diagnose.
        db: Database session.
        client: Optional Groq (OpenAI-compatible) client.

    Returns:
        Dict[str, Any]: Diagnosis record dictionary.
    """
    event = db.get(Event, event_id)
    if not event:
        raise ValueError(f"Event {event_id} not found.")

    # Check if existing diagnosis is present
    existing_diag = db.scalar(
        select(Diagnosis).where(Diagnosis.event_id == event_id)
    )
    if existing_diag:
        logger.info(f"Event {event_id} already has a diagnosis: {existing_diag.root_cause}")
        return {
            "id": str(existing_diag.id),
            "event_id": str(existing_diag.event_id),
            "root_cause": existing_diag.root_cause,
            "confidence": float(existing_diag.confidence) if existing_diag.confidence is not None else None,
            "reasoning": existing_diag.reasoning,
            "created_at": existing_diag.created_at.isoformat() if existing_diag.created_at else None,
        }

    # 1. Build rich case context
    context = build_case_context(event_id, db)

    # 2. Invoke Groq or Mock Fallback
    if is_mock_mode():
        diag_output = _generate_mock_diagnosis(context)
    else:
        if client is None:
            client = OpenAI(
                api_key=os.environ["GROQ_API_KEY"],
                base_url=os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1"),
            )

        model_name = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
        serialized_context = json.dumps(context, indent=2, default=str)

        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"Please diagnose the following revenue-at-risk case context:\n\n{serialized_context}",
                },
            ],
            tools=[RECORD_DIAGNOSIS_TOOL],
            tool_choice={"type": "function", "function": {"name": "record_diagnosis"}},
            temperature=0.1,
        )

        choice = response.choices[0]
        if not choice.message.tool_calls:
            raise RuntimeError(f"Groq did not return tool_calls for event {event_id}")

        tool_call = choice.message.tool_calls[0]
        diag_output = json.loads(tool_call.function.arguments)

    # FIX 2: Enforce confidence bounds (0.0 to 1.0) and validate root cause
    raw_confidence = float(diag_output.get("confidence", 0.0))
    if raw_confidence < 0.0 or raw_confidence > 1.0:
        logger.warning(
            f"Confidence {raw_confidence} out of bounds [0, 1] for event {event_id}; clamping."
        )
        clamped_confidence = max(0.0, min(1.0, raw_confidence))
    else:
        clamped_confidence = raw_confidence

    root_cause = diag_output.get("root_cause")
    if root_cause not in ROOT_CAUSES:
        raise ValueError(f"Invalid root cause '{root_cause}' returned by agent.")

    reasoning = diag_output.get("reasoning", "")

    # 3. Persist to diagnoses table
    diagnosis = Diagnosis(
        event_id=event.id,
        root_cause=root_cause,
        confidence=Decimal(str(round(clamped_confidence, 4))),
        reasoning=reasoning,
    )
    db.add(diagnosis)

    # 4. Write audit trail log
    audit_entry = AuditLog(
        event_id=event.id,
        agent_name="root_cause_diagnosis_agent",
        decision=root_cause,
        reasoning=reasoning,
    )
    db.add(audit_entry)

    db.commit()
    db.refresh(diagnosis)

    return {
        "id": str(diagnosis.id),
        "event_id": str(diagnosis.event_id),
        "root_cause": diagnosis.root_cause,
        "confidence": float(diagnosis.confidence) if diagnosis.confidence is not None else None,
        "reasoning": diagnosis.reasoning,
        "created_at": diagnosis.created_at.isoformat() if diagnosis.created_at else None,
    }


def run_diagnosis_batch(
    db: Session,
    client: Optional[OpenAI] = None,
    require_real_agent: bool = False,
) -> Dict[str, Any]:
    """Sync overdue/disputed invoices and diagnose all pending events.

    Args:
        db: Database session.
        client: Optional Groq (OpenAI-compatible) client.
        require_real_agent: If True, aborts immediately if GROQ_API_KEY is missing.

    Returns:
        Dict[str, Any]: Batch summary with total_processed, distribution, and failures list.
    """
    if require_real_agent:
        check_mock_mode_disabled()

    # 1. Sync invoices first
    synced_count = sync_invoices_to_events(db)
    logger.info(f"Pre-diagnosis sync created {synced_count} new invoice events.")

    # 2. Find all events without an existing diagnosis
    diagnosed_subquery = select(Diagnosis.event_id)
    pending_events = db.scalars(
        select(Event)
        .where(Event.id.not_in(diagnosed_subquery))
        .order_by(Event.created_at.asc())
    ).all()

    total_pending = len(pending_events)
    logger.info(f"Found {total_pending} undiagnosed events to process.")

    processed_count = 0
    by_root_cause: Dict[str, int] = {rc: 0 for rc in ROOT_CAUSES}
    failures: List[Dict[str, Any]] = []

    for idx, ev in enumerate(pending_events, start=1):
        success = False
        max_retries = 2
        last_error = ""

        for attempt in range(max_retries + 1):
            try:
                res = diagnose_event(ev.id, db, client=client)
                rc = res["root_cause"]
                by_root_cause[rc] = by_root_cause.get(rc, 0) + 1
                processed_count += 1
                success = True
                logger.info(
                    f"[{idx}/{total_pending}] Diagnosed event {ev.id} ({ev.source_type}) -> {rc}"
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
        "by_root_cause": by_root_cause,
        "failures": failures,
    }
