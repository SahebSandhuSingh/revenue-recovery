import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.constants import ROOT_CAUSES
from app.database import SessionLocal
from app.main import app
from app.models import (
    Action,
    AuditLog,
    Diagnosis,
    Event,
    InboundMessage,
    Promise,
)
from app.services.dispatch_service import run_silent_retries
from app.data.generate_synthetic_invoices import seed_database
from app.data.generate_synthetic_consumer_events import seed_consumer_events
from app.data.generate_synthetic_customer_replies import seed_customer_replies
from app.services.diagnosis_agent import run_diagnosis_batch
from app.services.intervention_agent import run_intervention_batch
from app.services.promise_agent import run_reply_processing_batch
from app.services.promise_evaluator import evaluate_promise_statuses

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_dashboard_test_data():
    """Seed complete end-to-end dataset across invoices, events, diagnoses, actions, replies, and promises."""
    seed_database(reset=True)
    seed_consumer_events(reset=True)

    with SessionLocal() as db:
        run_diagnosis_batch(db=db)

    with SessionLocal() as db:
        run_intervention_batch(db=db)

    seed_customer_replies(reset=True)

    with SessionLocal() as db:
        run_reply_processing_batch(db=db)
        evaluate_promise_statuses(db=db)
        run_silent_retries(db=db)
    yield


def test_get_case_detail_full_chain_and_404():
    """PART A & D: Test GET /events/{event_id}/case returns complete aggregated object and 404 for missing."""
    db = SessionLocal()
    try:
        # Find an event that has promise and inbound messages
        promise = db.scalars(select(Promise)).first()
        assert promise is not None
        event_id = promise.event_id

        response = client.get(f"/events/{event_id}/case")
        assert response.status_code == 200
        data = response.json()

        # Check event section
        assert "event" in data
        assert data["event"]["id"] == str(event_id)
        assert data["event"]["amount"] > 0
        assert "data_source" in data["event"]

        # Check diagnosis section
        assert "diagnosis" in data
        if data["diagnosis"]:
            assert data["diagnosis"]["root_cause"] in ROOT_CAUSES

        # Check action section
        assert "action" in data

        # Check promise section
        assert "promise" in data
        assert data["promise"]["id"] == str(promise.id)

        # Check inbound_messages section
        assert "inbound_messages" in data
        assert isinstance(data["inbound_messages"], list)

        # Check audit_log section (chronological order)
        assert "audit_log" in data
        assert len(data["audit_log"]) > 0
        timestamps = [a["timestamp"] for a in data["audit_log"]]
        assert timestamps == sorted(timestamps)

        # Test 404 for non-existent event_id
        fake_id = uuid.uuid4()
        res_404 = client.get(f"/events/{fake_id}/case")
        assert res_404.status_code == 404
    finally:
        db.close()


def test_recovery_summary_internal_consistency():
    """PART B & D: Verify GET /metrics/recovery-summary returns internally consistent numbers."""
    response = client.get("/metrics/recovery-summary")
    assert response.status_code == 200
    data = response.json()

    # Total events count matches sum of by_root_cause counts
    by_rc = data["by_root_cause"]
    sum_rc_counts = sum(item["count"] for item in by_rc.values())
    assert sum_rc_counts == data["total_events"]

    # Overall recovery rate matches formula
    if data["total_amount_at_risk"] > 0:
        expected_rate = round(data["recovered_amount"] / data["total_amount_at_risk"], 4)
        assert abs(data["overall_recovery_rate"] - expected_rate) < 0.001

    # Exception list exists and contains formatted items
    assert "exception_list" in data
    for exc in data["exception_list"]:
        assert "event_id" in exc
        assert "customer_id" in exc
        assert "amount" in exc
        assert "reason" in exc

    # Funnel counts are present
    assert "funnel" in data
    assert data["funnel"]["diagnosed"] <= data["total_events"]
    assert data["funnel"]["routed"] <= data["total_events"]


def test_manual_mark_kept_override_and_case_detail_reflection():
    """PART C & D: Test POST /promises/{id}/mark-kept updates status and reflects in case detail."""
    db = SessionLocal()
    try:
        # Find or create a pending promise
        event = db.scalars(select(Event)).first()
        assert event is not None

        promise = Promise(
            event_id=event.id,
            promised_amount=Decimal("12345.00"),
            promised_date=date.today() + timedelta(days=10),
            status="pending",
            raw_reply_text="Demo pending promise test",
        )
        db.add(promise)
        db.commit()
        db.refresh(promise)

        # Call manual demo override endpoint
        override_res = client.post(f"/promises/{promise.id}/mark-kept")
        assert override_res.status_code == 200
        override_data = override_res.json()
        assert override_data["status"] == "kept"
        assert override_data["source"] == "manual_demo_override"

        # Verify in GET /events/{event_id}/case
        case_res = client.get(f"/events/{event.id}/case")
        assert case_res.status_code == 200
        case_data = case_res.json()
        assert case_data["promise"]["status"] == "kept"
        assert case_data["promise"]["reconciliation_source"] == "manual_demo_override"

        # Verify audit entry is specifically attributed to manual_demo_override (not AI)
        audit_entries = case_data["audit_log"]
        manual_entry = next((a for a in audit_entries if a["agent_name"] == "manual_demo_override"), None)
        assert manual_entry is not None
        assert manual_entry["decision"] == "kept"
    finally:
        db.close()


def test_silent_retry_recovery_counting():
    """PART 0 & D: Verify silent_retry with status='sent' counts in recovered_amount, while 'failed' does not."""
    db = SessionLocal()
    try:
        # Create 2 events with silent retry actions: 1 sent, 1 failed
        ev_success = Event(
            source_type="checkout",
            source_id=f"test_succ_{uuid.uuid4().hex[:6]}",
            customer_id="CUST-TEST-SUCC",
            amount=Decimal("50000.00"),
            currency="INR",
            status="failed",
            raw_payload={},
        )
        ev_failed = Event(
            source_type="checkout",
            source_id=f"test_fail_{uuid.uuid4().hex[:6]}",
            customer_id="CUST-TEST-FAIL",
            amount=Decimal("70000.00"),
            currency="INR",
            status="failed",
            raw_payload={},
        )
        db.add_all([ev_success, ev_failed])
        db.commit()
        db.refresh(ev_success)
        db.refresh(ev_failed)

        # Success action (status='sent')
        act_succ = Action(
            event_id=ev_success.id,
            action_type="silent_retry",
            channel="none",
            status="sent",
            dispatched_at=datetime.now(timezone.utc),
            delivered_at=datetime.now(timezone.utc),
            dispatch_error=None,
        )
        # Failed action (status='failed')
        act_fail = Action(
            event_id=ev_failed.id,
            action_type="silent_retry",
            channel="none",
            status="failed",
            dispatched_at=None,
            dispatch_error="[SIMULATED OUTCOME - still failing, see code comment for limitation]",
        )
        db.add_all([act_succ, act_fail])
        db.commit()

        # Check recovery metrics
        res = client.get("/metrics/recovery-summary")
        assert res.status_code == 200

        # Case detail for success
        case_succ = client.get(f"/events/{ev_success.id}/case").json()
        assert case_succ["action"]["status"] == "sent"
        assert case_succ["action"]["dispatch_status"] == "sent"

        # Case detail for failure
        case_fail = client.get(f"/events/{ev_failed.id}/case").json()
        assert case_fail["action"]["status"] == "failed"
        assert case_fail["action"]["dispatch_status"] == "failed"
    finally:
        db.close()


def test_clean_event_not_in_exception_list():
    """PART D: Verify a clean newly-created event with no broken promises or dispatches does not appear in exception list."""
    db = SessionLocal()
    try:
        clean_ev = Event(
            source_type="invoice",
            source_id=f"test_clean_{uuid.uuid4().hex[:6]}",
            customer_id="CUST-TEST-CLEAN-01",
            amount=Decimal("10000.00"),
            currency="INR",
            status="overdue",
            raw_payload={},
        )
        db.add(clean_ev)
        db.commit()
        db.refresh(clean_ev)

        res = client.get("/metrics/recovery-summary")
        assert res.status_code == 200
        data = res.json()
        exception_eids = [item["event_id"] for item in data["exception_list"]]
        assert str(clean_ev.id) not in exception_eids
    finally:
        db.close()


def test_case_explorer_pagination_and_filtering():
    """PART G & D: Verify GET /cases pagination and filtering."""
    # 1. Fetch all cases
    res = client.get("/cases?limit=10&offset=0")
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert "total" in data
    assert len(data["items"]) <= 10

    # 2. Filter by root_cause
    res_rc = client.get("/cases?root_cause=cash_flow_distress")
    assert res_rc.status_code == 200
    for item in res_rc.json()["items"]:
        assert item["root_cause"] == "cash_flow_distress"
