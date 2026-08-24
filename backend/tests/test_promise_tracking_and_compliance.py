import os
import uuid
from datetime import date, timedelta
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.constants import (
    MAX_BROKEN_PROMISES_BEFORE_ESCALATION,
    MAX_CONTACTS_BEFORE_ESCALATION,
    PROMISE_STATUSES,
    REPLY_TYPES,
)
from app.database import SessionLocal
from app.main import app
from app.models import (
    Action,
    AuditLog,
    ComplianceLimit,
    Diagnosis,
    Event,
    InboundMessage,
    Promise,
)
from app.services.compliance_service import (
    get_or_create_compliance_record,
    is_customer_blocked,
    register_contact,
)
from app.services.diagnosis_agent import is_mock_mode, run_diagnosis_batch
from app.services.intervention_agent import (
    route_intervention,
    run_intervention_batch,
)
from app.services.promise_agent import (
    process_inbound_reply,
    run_reply_processing_batch,
)
from app.services.promise_evaluator import evaluate_promise_statuses
from app.data.generate_synthetic_invoices import seed_database
from app.data.generate_synthetic_consumer_events import seed_consumer_events
from app.data.generate_synthetic_customer_replies import seed_customer_replies

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_step4_data():
    """Setup clean state across invoices, consumer events, diagnoses, actions, and replies."""
    seed_database(reset=True)
    seed_consumer_events(reset=True)
    db = SessionLocal()
    try:
        # 1. Run diagnoses
        run_diagnosis_batch(db=db)
        # 2. Run interventions
        run_intervention_batch(db=db)
        # 3. Seed synthetic customer replies
        seed_customer_replies(reset=True)
    finally:
        db.close()
    yield


def test_fix4_constants_dynamic_literals():
    """FIX 4: Confirm REPLY_TYPES and PROMISE_STATUSES are populated in constants.py."""
    assert len(REPLY_TYPES) == 4
    assert "promise_to_pay" in REPLY_TYPES
    assert "dispute" in REPLY_TYPES
    assert "payment_made" in REPLY_TYPES
    assert "other" in REPLY_TYPES

    assert len(PROMISE_STATUSES) == 3
    assert "pending" in PROMISE_STATUSES
    assert "kept" in PROMISE_STATUSES
    assert "broken" in PROMISE_STATUSES


def test_fix2_require_real_agent_in_promise_agent():
    """FIX 2: Verify require_real_agent=True raises error when mock mode is active."""
    if is_mock_mode():
        db = SessionLocal()
        try:
            msg = db.scalars(select(InboundMessage)).first()
            assert msg is not None

            with pytest.raises(RuntimeError) as exc_info1:
                process_inbound_reply(msg.id, db, require_real_agent=True)
            assert "Mock mode is active" in str(exc_info1.value)

            with pytest.raises(RuntimeError) as exc_info2:
                run_reply_processing_batch(db, require_real_agent=True)
            assert "Mock mode is active" in str(exc_info2.value)
        finally:
            db.close()


def test_reply_processing_and_default_amount():
    """PART D & FIX 6: Test reply processing, promise creation, and event amount defaulting."""
    db = SessionLocal()
    try:
        # Create a specific promise message without explicit amount
        event = db.scalars(select(Event)).first()
        assert event is not None

        test_msg = InboundMessage(
            event_id=event.id,
            channel="whatsapp",
            raw_text="I promise to clear the full balance by 2026-09-15.",
            reply_type=None,
        )
        db.add(test_msg)
        db.commit()
        db.refresh(test_msg)

        res = process_inbound_reply(test_msg.id, db)
        assert res["reply_type"] == "promise_to_pay"
        assert res["promised_date"] == "2026-09-15"
        # FIX 6: Promised amount defaults to event.amount when unstated
        assert Decimal(str(res["promised_amount"])) == event.amount
        assert res["promise_id"] is not None

        # Verify Promise row created
        promise = db.get(Promise, uuid.UUID(res["promise_id"]))
        assert promise is not None
        assert promise.status == "pending"
        assert promise.raw_reply_text == test_msg.raw_text
        assert promise.promised_date == date(2026, 9, 15)
    finally:
        db.close()


def test_batch_reply_processing_and_idempotency():
    """PART D & FIX 8: Run reply processing batch and verify summary fields and idempotency."""
    db = SessionLocal()
    try:
        summary1 = run_reply_processing_batch(db)
        assert "total_processed" in summary1
        assert "by_reply_type" in summary1
        assert "promises_created" in summary1
        assert "failures" in summary1
        assert summary1["total_processed"] > 0
        assert summary1["promises_created"] > 0

        # Run again -> total_processed must be 0 (Idempotency)
        summary2 = run_reply_processing_batch(db)
        assert summary2["total_processed"] == 0
    finally:
        db.close()


def test_promise_evaluator_backdated_broken():
    """PART E: Test evaluate_promise_statuses marks past promises as broken."""
    db = SessionLocal()
    try:
        event = db.scalars(select(Event)).first()
        assert event is not None

        past_date = date.today() - timedelta(days=7)
        future_date = date.today() + timedelta(days=7)

        # Insert 1 past promise and 1 future promise
        p_past = Promise(
            event_id=event.id,
            promised_amount=Decimal("50000.00"),
            promised_date=past_date,
            status="pending",
            raw_reply_text="Past test promise",
        )
        p_future = Promise(
            event_id=event.id,
            promised_amount=Decimal("50000.00"),
            promised_date=future_date,
            status="pending",
            raw_reply_text="Future test promise",
        )
        db.add_all([p_past, p_future])
        db.commit()

        eval_summary = evaluate_promise_statuses(db)
        assert eval_summary["newly_broken"] >= 1
        assert eval_summary["still_pending"] >= 1

        db.refresh(p_past)
        db.refresh(p_future)
        assert p_past.status == "broken"
        assert p_future.status == "pending"

        # Verify audit log entry for broken promise
        audit = db.scalars(
            select(AuditLog).where(
                AuditLog.event_id == event.id,
                AuditLog.agent_name == "promise_evaluator",
                AuditLog.decision == "broken",
            )
        ).first()
        assert audit is not None
    finally:
        db.close()


def test_compliance_escalation_after_3_contacts():
    """PART F: Test contact count limit (3) triggers escalation_flag=True on exactly the 3rd attempt."""
    db = SessionLocal()
    try:
        cust_id = f"TEST-CUST-3CONTACTS-{uuid.uuid4().hex[:6]}"
        rec = get_or_create_compliance_record(cust_id, db)
        assert rec.contact_count == 0
        assert rec.escalation_flag is False

        # Contact 1
        res1 = register_contact(cust_id, db)
        assert res1["contact_count"] == 1
        assert res1["escalation_flag"] is False

        # Contact 2
        res2 = register_contact(cust_id, db)
        assert res2["contact_count"] == 2
        assert res2["escalation_flag"] is False

        # Contact 3 -> Escalation threshold reached!
        res3 = register_contact(cust_id, db)
        assert res3["contact_count"] == 3
        assert res3["escalation_flag"] is True
        assert "Maximum contact attempts reached" in res3["escalation_reason"]
    finally:
        db.close()


def test_compliance_escalation_after_1_broken_promise():
    """PART F: Test 1 broken promise triggers escalation_flag=True even with 1 contact."""
    db = SessionLocal()
    try:
        cust_id = f"TEST-CUST-BROKEN-{uuid.uuid4().hex[:6]}"
        # Create event & broken promise for this customer
        event = Event(
            source_type="checkout",
            source_id=f"pay_{uuid.uuid4().hex[:6]}",
            customer_id=cust_id,
            amount=Decimal("15000.00"),
            currency="INR",
            status="failed",
            raw_payload={},
        )
        db.add(event)
        db.commit()
        db.refresh(event)

        promise = Promise(
            event_id=event.id,
            promised_amount=Decimal("15000.00"),
            promised_date=date.today() - timedelta(days=2),
            status="broken",
            raw_reply_text="Broken commitment test",
        )
        db.add(promise)
        db.commit()

        # Register contact 1 for this customer
        res = register_contact(cust_id, db)
        assert res["contact_count"] == 1
        assert res["escalation_flag"] is True
        assert "Broken payment promise detected" in res["escalation_reason"]
    finally:
        db.close()


def test_compliance_gating_in_route_intervention():
    """PART F: Blocked customer gets action status 'blocked_pending_review' and contact count doesn't increment."""
    db = SessionLocal()
    try:
        cust_id = f"TEST-CUST-GATED-{uuid.uuid4().hex[:6]}"
        rec = get_or_create_compliance_record(cust_id, db)
        rec.escalation_flag = True
        rec.contact_count = 3
        db.commit()

        event = Event(
            source_type="invoice",
            source_id=f"inv_{uuid.uuid4().hex[:6]}",
            customer_id=cust_id,
            amount=Decimal("55000.00"),
            currency="INR",
            status="overdue",
            raw_payload={"days_overdue": 15, "invoice_number": "INV-GATED-01"},
        )
        db.add(event)
        db.commit()
        db.refresh(event)

        # Add diagnosis
        diag = Diagnosis(
            event_id=event.id,
            root_cause="forgetfulness",
            confidence=Decimal("0.85"),
            reasoning="Test diagnosis",
        )
        db.add(diag)
        db.commit()

        # Route intervention on blocked customer
        act_res = route_intervention(event.id, db)
        assert act_res["status"] == "blocked_pending_review"

        # Verify contact count did NOT increment
        db.refresh(rec)
        assert rec.contact_count == 3

        # Verify compliance gate audit log entry
        audit = db.scalars(
            select(AuditLog).where(
                AuditLog.event_id == event.id,
                AuditLog.agent_name == "compliance_gate",
                AuditLog.decision == "blocked",
            )
        ).first()
        assert audit is not None
    finally:
        db.close()


def test_api_promises_and_compliance():
    """PART G & FIX 5: Test API endpoints for promises, compliance, and filters."""
    # 1. Evaluate promises endpoint
    res_eval = client.post("/promises/evaluate")
    assert res_eval.status_code == 200
    assert "newly_broken" in res_eval.json()

    # 2. List promises with filter
    res_proms = client.get("/promises?status=broken")
    assert res_proms.status_code == 200
    assert "items" in res_proms.json()

    # 3. Process replies endpoint
    res_proc = client.post("/replies/process")
    assert res_proc.status_code == 200
    assert "by_reply_type" in res_proc.json()

    # 4. List compliance records with escalation_flag filter (FIX 5)
    res_comp_filtered = client.get("/compliance?escalation_flag=true")
    assert res_comp_filtered.status_code == 200
    comp_items = res_comp_filtered.json()["items"]
    for c in comp_items:
        assert c["escalation_flag"] is True

    # 5. Get compliance for single customer
    if comp_items:
        test_cust = comp_items[0]["customer_id"]
        res_single = client.get(f"/compliance/{test_cust}")
        assert res_single.status_code == 200
        assert res_single.json()["customer_id"] == test_cust

    # 6. Compliance 404 for unknown customer
    res_404 = client.get("/compliance/UNKNOWN-NONEXISTENT-CUSTOMER-999")
    assert res_404.status_code == 404
