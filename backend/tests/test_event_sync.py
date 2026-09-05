import uuid
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select

from app.database import SessionLocal
from app.models import Event, Invoice
from app.services.event_sync import sync_invoices_to_events


def test_sync_invoices_to_events_is_idempotent():
    """FIX 1: Running sync_invoices_to_events() twice for the same invoice
    must not create a duplicate event -- exactly one event row should exist
    per invoice (matched on source_type='invoice' AND source_id=str(invoice.id))."""
    db = SessionLocal()
    invoice_id = None
    try:
        invoice = Invoice(
            customer_id="CUST-TEST-DEDUP-01",
            invoice_number=f"INV-TEST-DEDUP-{uuid.uuid4().hex[:8]}",
            gst_number="29AATEST0001Z",
            hsn_code="3401",
            amount=Decimal("10000.00"),
            due_date=date.today() - timedelta(days=10),
            credit_terms="net_30",
            status="overdue",
        )
        db.add(invoice)
        db.commit()
        db.refresh(invoice)
        invoice_id = invoice.id

        # First sync: should create exactly one event for this invoice.
        sync_invoices_to_events(db)
        events_after_first = db.scalars(
            select(Event).where(
                Event.source_type == "invoice",
                Event.source_id == str(invoice_id),
            )
        ).all()
        assert len(events_after_first) == 1

        # Second sync: dedup must kick in -- no new event created.
        sync_invoices_to_events(db)
        events_after_second = db.scalars(
            select(Event).where(
                Event.source_type == "invoice",
                Event.source_id == str(invoice_id),
            )
        ).all()
        assert len(events_after_second) == 1
        assert events_after_second[0].id == events_after_first[0].id
    finally:
        # Clean up test artifacts so this test leaves no residue behind.
        if invoice_id is not None:
            db.execute(
                Event.__table__.delete().where(
                    Event.source_type == "invoice",
                    Event.source_id == str(invoice_id),
                )
            )
            db.execute(Invoice.__table__.delete().where(Invoice.id == invoice_id))
            db.commit()
        db.close()
