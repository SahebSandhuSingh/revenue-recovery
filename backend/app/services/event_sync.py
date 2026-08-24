import logging
from datetime import date
from typing import List
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Event, Invoice

logger = logging.getLogger(__name__)


def sync_invoices_to_events(db: Session) -> int:
    """Sync all overdue and disputed B2B invoices into unified events.

    Idempotently checks if an event with source_type='invoice' and source_id=str(invoice.id)
    already exists. Creates and commits new Event rows for unsynced records.

    Returns:
        int: Number of new events created.
    """
    today = date.today()

    # 1. Fetch overdue and disputed invoices
    invoices = db.scalars(
        select(Invoice).where(Invoice.status.in_(["overdue", "disputed"]))
    ).all()

    if not invoices:
        logger.info("No overdue or disputed invoices found for event synchronization.")
        return 0

    # 2. Fetch existing invoice event source_ids to prevent duplicates
    existing_event_source_ids = set(
        db.scalars(
            select(Event.source_id).where(Event.source_type == "invoice")
        ).all()
    )

    new_events: List[Event] = []
    for inv in invoices:
        str_id = str(inv.id)
        if str_id in existing_event_source_ids:
            continue

        # Compute days overdue
        days_overdue = (today - inv.due_date).days if inv.due_date else 0

        raw_payload = {
            "invoice_number": inv.invoice_number,
            "gst_number": inv.gst_number,
            "hsn_code": inv.hsn_code,
            "due_date": inv.due_date.isoformat() if inv.due_date else None,
            "credit_terms": inv.credit_terms,
            "days_overdue": days_overdue,
            "original_invoice_status": inv.status,
        }

        event = Event(
            source_type="invoice",
            source_id=str_id,
            customer_id=inv.customer_id,
            amount=inv.amount,
            currency="INR",
            status=inv.status,
            raw_payload=raw_payload,
        )
        new_events.append(event)

    if new_events:
        db.add_all(new_events)
        db.commit()
        for ev in new_events:
            db.refresh(ev)
        logger.info(f"Synced {len(new_events)} invoice events to events table.")

    return len(new_events)
