import json
import logging
import os
import re
import time
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional
from openai import OpenAI, OpenAIError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.constants import REPLY_TYPES
from app.models import Action, AuditLog, Event, InboundMessage, Promise
from app.services.diagnosis_agent import check_mock_mode_disabled, is_mock_mode

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are Recoup's Inbound Reply Classification & Promise Extraction Specialist, an expert AI agent dedicated to understanding customer responses to payment outreach, categorizing customer intent, and accurately extracting commitments.

Your task is to review the inbound customer text message, considering the associated debt context and transaction amount.

Reply Types:
1. 'promise_to_pay' — Customer agrees to pay and specifies or implies a commitment date (e.g., 'will pay by Friday', 'clearing by the 30th', 'transferring next week').
2. 'dispute' — Customer disputes the invoice or charge (e.g., missing shipment, damaged goods, incorrect pricing, billing dispute).
3. 'payment_made' — Customer claims payment has already been executed (e.g., 'already transferred yesterday', 'check UTR 12345').
4. 'other' — Unrelated responses, vague non-committal messages without dates, or unclear replies.

Extraction Rules for 'promise_to_pay':
- 'promised_date': MUST be formatted as 'YYYY-MM-DD'. If customer provides relative terms (e.g. 'in 5 days', 'tomorrow'), resolve the date relative to the message received date.
- 'promised_amount': Numeric amount customer pledged to pay. If customer states 'full amount' or doesn't name a specific number, return null/null-equivalent so the system defaults to the event's original amount.
- 'reasoning': 1-2 concise sentences explaining the classification.
"""

CLASSIFY_REPLY_TOOL = {
    "type": "function",
    "function": {
        "name": "classify_reply",
        "description": "Classify inbound customer reply and extract promise-to-pay details if present",
        "parameters": {
          "type": "object",
          "properties": {
            "reply_type": {
              "type": "string",
              "enum": REPLY_TYPES,
              "description": "Categorized intent of the customer's message.",
            },
            "promised_amount": {
              "type": ["number", "null"],
              "description": "Promised payment amount in INR (nullable if unstated).",
            },
            "promised_date": {
              "type": ["string", "null"],
              "description": "Promised payment date in YYYY-MM-DD format (nullable).",
            },
            "reasoning": {
              "type": "string",
              "description": "1-2 sentences justifying the classification and date extraction.",
            },
          },
          "required": ["reply_type", "reasoning"],
          "additionalProperties": False,
        },
    },
}


def _extract_mock_reply_intent(
    raw_text: str, default_amount: Decimal, reference_date: date
) -> Dict[str, Any]:
    """Deterministic mock extraction for customer reply text when OpenAI key is absent."""
    print("\n" + "=" * 60)
    print("⚠️  MOCK MODE ACTIVE — NO REAL GPT-4O CALL WAS MADE")
    print("=" * 60 + "\n")

    text_lower = raw_text.lower()

    # 1. Dispute detection
    if any(k in text_lower for k in ["contest", "dispute", "damaged", "pricing", "pod", "double billed", "discrepancy", "error"]):
        return {
            "reply_type": "dispute",
            "promised_amount": None,
            "promised_date": None,
            "reasoning": "[MOCK] Customer text indicates an active invoice or product delivery dispute.",
        }

    # 2. Payment Made detection
    if any(k in text_lower for k in ["already", "transferred", "deducted", "completed", "utr", "rtgs", "neft"]):
        return {
            "reply_type": "payment_made",
            "promised_amount": None,
            "promised_date": None,
            "reasoning": "[MOCK] Customer claims the payment transaction has already been completed.",
        }

    # 3. Promise To Pay detection
    if any(k in text_lower for k in ["promise", "will pay", "settle", "clearing", "transfer", "initiate"]):
        # Extract explicit ISO date if present (YYYY-MM-DD)
        date_match = re.search(r"(\d{4}-\d{2}-\d{2})", raw_text)
        if date_match:
            promised_date_str = date_match.group(1)
        else:
            # Default to +5 days from reference
            promised_date_str = (reference_date + timedelta(days=5)).isoformat()

        # Remove date string from text before searching for currency amounts to avoid matching year digits
        text_without_date = re.sub(r"\d{4}-\d{2}-\d{2}", "", raw_text)

        # Extract amount if present explicitly with currency symbol/keyword
        amount_match = re.search(r"(?:₹|rs\.?|inr)\s*([0-9,]+(?:\.[0-9]{2})?)", text_without_date, re.IGNORECASE)
        if amount_match:
            try:
                amt_str = amount_match.group(1).replace(",", "")
                extracted_amount = float(amt_str)
            except Exception:
                extracted_amount = None
        else:
            extracted_amount = None

        return {
            "reply_type": "promise_to_pay",
            "promised_amount": extracted_amount,  # Will trigger default to event.amount in caller if None
            "promised_date": promised_date_str,
            "reasoning": f"[MOCK] Customer committed to pay on {promised_date_str}.",
        }

    return {
        "reply_type": "other",
        "promised_amount": None,
        "promised_date": None,
        "reasoning": "[MOCK] Inbound text is non-committal or generic response.",
    }


def process_inbound_reply(
    message_id: uuid.UUID,
    db: Session,
    client: Optional[OpenAI] = None,
    require_real_agent: bool = False,
) -> Dict[str, Any]:
    """Classify inbound customer reply, extract payment commitments, and update downstream state.

    Args:
        message_id: InboundMessage UUID.
        db: Database session.
        client: Optional OpenAI client.
        require_real_agent: If True, raises error when OPENAI_API_KEY is not set.

    Returns:
        Dict[str, Any]: Classification result dictionary.
    """
    # FIX 1: Enforce mock-mode rigor across all agent calls
    if require_real_agent:
        check_mock_mode_disabled()

    msg = db.get(InboundMessage, message_id)
    if not msg:
        raise ValueError(f"Inbound message {message_id} not found.")

    event = db.get(Event, msg.event_id)
    if not event:
        raise ValueError(f"Event {msg.event_id} not found for inbound message {message_id}.")

    ref_date = msg.received_at.date() if msg.received_at else date.today()
    default_amount = event.amount

    # 1. Classify via GPT-4o or Mock Fallback
    if is_mock_mode():
        classification = _extract_mock_reply_intent(
            msg.raw_text, default_amount=default_amount, reference_date=ref_date
        )
    else:
        if client is None:
            client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

        model_name = os.getenv("OPENAI_MODEL", "gpt-4o")
        prompt_content = (
            f"Case Debt Amount: {event.currency} {event.amount:,.2f}\n"
            f"Message Received Date: {ref_date.isoformat()}\n"
            f"Inbound Customer Text:\n\"{msg.raw_text}\""
        )

        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt_content},
            ],
            tools=[CLASSIFY_REPLY_TOOL],
            tool_choice={"type": "function", "function": {"name": "classify_reply"}},
            temperature=0.1,
        )

        choice = response.choices[0]
        if not choice.message.tool_calls:
            raise RuntimeError(f"GPT-4o did not return tool_calls for message {message_id}")

        tool_call = choice.message.tool_calls[0]
        classification = json.loads(tool_call.function.arguments)

    reply_type = classification.get("reply_type")
    raw_amount = classification.get("promised_amount")
    raw_date_str = classification.get("promised_date")
    reasoning = classification.get("reasoning", "")

    # Validation and default handling
    parsed_date: Optional[date] = None
    parsed_amount: Optional[Decimal] = None

    if reply_type == "promise_to_pay":
        # FIX 6: Default promised_amount to parent event's amount if unstated or null
        if raw_amount is None or float(raw_amount) <= 0:
            parsed_amount = event.amount
        else:
            parsed_amount = Decimal(str(round(float(raw_amount), 2)))

        # Validate promised_date parses cleanly to a real date
        if raw_date_str:
            try:
                parsed_date = date.fromisoformat(raw_date_str)
            except Exception as e:
                logger.warning(
                    f"Failed to parse promised_date '{raw_date_str}' for message {message_id}: {e}. Falling back to 'other'."
                )
                reply_type = "other"
                parsed_date = None
                parsed_amount = None
        else:
            logger.warning(
                f"Missing promised_date on promise_to_pay for message {message_id}. Falling back to 'other'."
            )
            reply_type = "other"
            parsed_amount = None

    if reply_type not in REPLY_TYPES:
        reply_type = "other"

    # 2. Update inbound_messages table
    msg.reply_type = reply_type

    # 3. Create Promise record if promise_to_pay
    promise_id = None
    if reply_type == "promise_to_pay" and parsed_date and parsed_amount:
        promise = Promise(
            event_id=event.id,
            promised_amount=parsed_amount,
            promised_date=parsed_date,
            status="pending",
            raw_reply_text=msg.raw_text,
        )
        db.add(promise)
        db.flush()
        promise_id = str(promise.id)
        logger.info(
            f"Created Promise {promise.id} for event {event.id}: ₹{parsed_amount:,.2f} by {parsed_date}"
        )

    # 4. If dispute, update corresponding Action status
    if reply_type == "dispute":
        action = db.scalar(
            select(Action).where(Action.event_id == event.id)
        )
        if action:
            action.status = "disputed_followup_needed"
            logger.info(f"Updated Action {action.id} status to 'disputed_followup_needed'")

    # 5. Write audit log entry
    audit_entry = AuditLog(
        event_id=event.id,
        agent_name="promise_extraction_agent",
        decision=reply_type,
        reasoning=reasoning,
    )
    db.add(audit_entry)

    db.commit()
    db.refresh(msg)

    return {
        "message_id": str(msg.id),
        "event_id": str(msg.event_id),
        "reply_type": msg.reply_type,
        "promised_amount": float(parsed_amount) if parsed_amount is not None else None,
        "promised_date": parsed_date.isoformat() if parsed_date else None,
        "promise_id": promise_id,
        "reasoning": reasoning,
    }


def run_reply_processing_batch(
    db: Session,
    client: Optional[OpenAI] = None,
    require_real_agent: bool = False,
) -> Dict[str, Any]:
    """Process all unclassified inbound customer replies in batch.

    Args:
        db: Database session.
        client: Optional OpenAI client.
        require_real_agent: If True, raises error when OPENAI_API_KEY is missing.

    Returns:
        Dict[str, Any]: Batch summary with total_processed, by_reply_type, promises_created, and failures list.
    """
    if require_real_agent:
        check_mock_mode_disabled()

    pending_messages = db.scalars(
        select(InboundMessage)
        .where(InboundMessage.reply_type.is_(None))
        .order_by(InboundMessage.received_at.asc())
    ).all()

    total_pending = len(pending_messages)
    logger.info(f"Found {total_pending} unclassified customer replies to process.")

    processed_count = 0
    promises_created = 0
    by_reply_type: Dict[str, int] = {rt: 0 for rt in REPLY_TYPES}
    failures: List[Dict[str, Any]] = []

    # Capped at max 2 retries per message
    max_retries = 2

    for idx, msg in enumerate(pending_messages, start=1):
        success = False
        last_error = ""

        for attempt in range(max_retries + 1):
            try:
                res = process_inbound_reply(
                    msg.id,
                    db,
                    client=client,
                    require_real_agent=require_real_agent,
                )
                rt = res["reply_type"]
                by_reply_type[rt] = by_reply_type.get(rt, 0) + 1
                if res.get("promise_id"):
                    promises_created += 1
                processed_count += 1
                success = True
                logger.info(
                    f"[{idx}/{total_pending}] Processed reply {msg.id} -> {rt}"
                )
                break
            except OpenAIError as oe:
                last_error = f"OpenAI API error: {str(oe)}"
                logger.warning(
                    f"Attempt {attempt + 1} failed for reply {msg.id}: {last_error}"
                )
                if attempt < max_retries:
                    time.sleep(2 ** attempt)
            except Exception as exc:
                last_error = str(exc)
                logger.error(
                    f"Attempt {attempt + 1} failed for reply {msg.id}: {last_error}"
                )
                if attempt < max_retries:
                    time.sleep(1)

        if not success:
            failures.append(
                {
                    "message_id": str(msg.id),
                    "error": last_error,
                    "retry_count": max_retries,
                }
            )

    return {
        "total_processed": processed_count,
        "by_reply_type": by_reply_type,
        "promises_created": promises_created,
        "failures": failures,
    }
