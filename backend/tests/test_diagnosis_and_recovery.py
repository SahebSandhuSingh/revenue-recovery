import os
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, delete

from app.constants import ROOT_CAUSES
from app.database import SessionLocal
from app.main import app
from app.models import Action, AuditLog, Diagnosis, Event, Invoice
from app.services.context_builder import build_case_context
from app.services.diagnosis_agent import (
    check_mock_mode_disabled,
    diagnose_event,
    is_mock_mode,
    run_diagnosis_batch,
)
from app.services.event_sync import sync_invoices_to_events
from app.data.generate_synthetic_invoices import seed_database
from app.data.generate_synthetic_consumer_events import seed_consumer_events

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_test_data():
    """Ensure database has fresh synthetic invoices and consumer events."""
    seed_database(reset=True)
    seed_consumer_events(reset=True)
    yield


def test_fix5_root_causes_constant():
    """FIX 5: Verify ROOT_CAUSES is defined with all 5 taxonomy values."""
    assert len(ROOT_CAUSES) == 5
    assert "soft_decline" in ROOT_CAUSES
    assert "hard_decline_or_expired" in ROOT_CAUSES
    assert "dispute" in ROOT_CAUSES
    assert "cash_flow_distress" in ROOT_CAUSES
    assert "forgetfulness" in ROOT_CAUSES


def test_fix1_mock_mode_safeguards():
    """FIX 1: Verify mock mode produces loud prefix and confidence 0.0, and check_mock_mode_disabled raises error."""
    if is_mock_mode():
        with pytest.raises(RuntimeError) as exc_info:
            check_mock_mode_disabled()
        assert "Mock mode is active" in str(exc_info.value)


def test_sync_invoices_to_events_idempotency():
    """PART B: Verify sync_invoices_to_events creates events and is strictly idempotent."""
    db = SessionLocal()
    try:
        # First sync
        synced_count = sync_invoices_to_events(db)
        # There are 18 overdue + 6 disputed = 24 invoices needing events
        assert synced_count >= 24

        # Verify raw_payload structure on one synced event
        synced_event = db.scalars(
            select(Event).where(Event.source_type == "invoice")
        ).first()
        assert synced_event is not None
        assert "days_overdue" in synced_event.raw_payload
        assert "invoice_number" in synced_event.raw_payload

        # Second sync must be 0 (Idempotency)
        second_synced_count = sync_invoices_to_events(db)
        assert second_synced_count == 0
    finally:
        db.close()


def test_context_builder():
    """PART C: Verify build_case_context computes deep metrics for B2B and consumer."""
    db = SessionLocal()
    try:
        # Test B2B event context
        b2b_event = db.scalars(
            select(Event).where(Event.source_type == "invoice")
        ).first()
        assert b2b_event is not None

        ctx_b2b = build_case_context(b2b_event.id, db)
        assert "b2b_context" in ctx_b2b
        assert "customer_history" in ctx_b2b["b2b_context"]
        cust_hist = ctx_b2b["b2b_context"]["customer_history"]
        assert "pct_paid_on_time" in cust_hist
        assert "total_invoices" in cust_hist
        assert "is_first_offense" in cust_hist

        # Test consumer event context
        consumer_event = db.scalars(
            select(Event).where(Event.source_type.in_(["checkout", "subscription", "mandate"]))
        ).first()
        assert consumer_event is not None

        ctx_consumer = build_case_context(consumer_event.id, db)
        assert "consumer_context" in ctx_consumer
        assert "total_events" in ctx_consumer["consumer_context"]
        assert "pct_failed" in ctx_consumer["consumer_context"]
    finally:
        db.close()


def test_diagnose_event_and_audit_log():
    """PART D & FIX 1: Verify single event diagnosis and audit trail generation."""
    db = SessionLocal()
    try:
        event = db.scalars(select(Event)).first()
        assert event is not None

        # Clean existing diagnosis if any
        db.execute(delete(Diagnosis).where(Diagnosis.event_id == event.id))
        db.execute(delete(AuditLog).where(AuditLog.event_id == event.id))
        db.commit()

        diag = diagnose_event(event.id, db)
        assert diag["root_cause"] in ROOT_CAUSES
        assert diag["confidence"] is not None
        assert 0.0 <= diag["confidence"] <= 1.0

        if is_mock_mode():
            assert "[MOCK]" in diag["reasoning"]
            assert diag["confidence"] == 0.0

        # Verify audit log entry
        audit = db.scalars(
            select(AuditLog).where(AuditLog.event_id == event.id)
        ).first()
        assert audit is not None
        assert audit.agent_name == "root_cause_diagnosis_agent"
        assert audit.decision == diag["root_cause"]
        assert audit.reasoning == diag["reasoning"]
    finally:
        db.close()


def test_batch_diagnosis_idempotency_and_summary():
    """PART D, FIX 3, FIX 4: Run batch diagnosis and verify idempotency on subsequent runs."""
    db = SessionLocal()
    try:
        # Run batch
        summary1 = run_diagnosis_batch(db=db)
        assert "total_processed" in summary1
        assert "by_root_cause" in summary1
        assert "failures" in summary1
        assert isinstance(summary1["failures"], list)

        # Re-run batch immediately -> total_processed must be 0 (FIX 4)
        summary2 = run_diagnosis_batch(db=db)
        assert summary2["total_processed"] == 0
    finally:
        db.close()


def test_api_endpoints():
    """PART E: Test all API routes."""
    # 1. Health check
    res_health = client.get("/health")
    assert res_health.status_code == 200
    assert res_health.json()["status"] == "ok"

    # 2. Invoices list with status filter
    res_inv = client.get("/invoices?status=overdue&limit=10")
    assert res_inv.status_code == 200
    data_inv = res_inv.json()
    assert len(data_inv["items"]) > 0
    for item in data_inv["items"]:
        assert item["status"] == "overdue"

    # 3. Sync endpoint
    res_sync = client.post("/sync/invoices-to-events")
    assert res_sync.status_code == 200
    assert "synced_count" in res_sync.json()

    # 4. Diagnose Run endpoint
    res_diag_run = client.post("/diagnose/run")
    assert res_diag_run.status_code == 200
    data_run = res_diag_run.json()
    assert "total_processed" in data_run
    assert "by_root_cause" in data_run

    # 5. List diagnoses
    res_diags = client.get("/diagnoses?limit=50")
    assert res_diags.status_code == 200
    diags_data = res_diags.json()
    assert diags_data["total"] > 0
    first_diag = diags_data["items"][0]
    assert first_diag["source_type"] is not None

    # 6. Filter diagnoses by root cause
    target_rc = first_diag["root_cause"]
    res_filtered = client.get(f"/diagnoses?root_cause={target_rc}")
    assert res_filtered.status_code == 200
    for d in res_filtered.json()["items"]:
        assert d["root_cause"] == target_rc

    # 7. Single event diagnosis endpoint
    event_id = first_diag["event_id"]
    res_single = client.get(f"/events/{event_id}/diagnosis")
    assert res_single.status_code == 200
    assert res_single.json()["event_id"] == str(event_id)
