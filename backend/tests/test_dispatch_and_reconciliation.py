import uuid
from datetime import date, timedelta
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.constants import ACTION_STATUSES, DISPATCH_RESULTS, RECONCILIATION_SOURCES
from app.database import SessionLocal
from app.main import app
from app.models import Action, AuditLog, Diagnosis, Event, Promise
from app.services.dispatch_service import dispatch_action, run_dispatch_batch
from app.services.reconciliation_service import (
    reconcile_payment,
    simulate_payment_reconciliation,
)
from app.data.generate_synthetic_invoices import seed_database
from app.data.generate_synthetic_consumer_events import seed_consumer_events
from app.services.diagnosis_agent import run_diagnosis_batch
from app.services.intervention_agent import run_intervention_batch

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_step5_data():
    """Seed full pipeline: invoices → events → diagnoses → interventions."""
    seed_database(reset=True)
    seed_consumer_events(reset=True)
    db = SessionLocal()
    try:
        run_diagnosis_batch(db=db)
        run_intervention_batch(db=db)
    finally:
        db.close()
    yield


def test_constants_step5():
    """Verify Step 5 constants are populated."""
    assert len(ACTION_STATUSES) >= 6
    assert "dispatched" in ACTION_STATUSES
    assert "delivered" in ACTION_STATUSES
    assert "failed" in ACTION_STATUSES
    assert len(DISPATCH_RESULTS) == 3
    assert len(RECONCILIATION_SOURCES) == 3


def test_dispatch_single_action():
    """Test dispatching a single planned action transitions its lifecycle."""
    db = SessionLocal()
    try:
        action = db.scalars(
            select(Action).where(Action.status == "planned")
        ).first()
        if not action:
            pytest.skip("No planned actions available")

        result = dispatch_action(action.id, db)
        assert result["action_id"] == str(action.id)
        assert result["status"] in ("delivered", "failed")
        assert result["simulated"] is True

        db.refresh(action)
        assert action.dispatched_at is not None
        if action.status == "delivered":
            assert action.delivered_at is not None
            assert action.dispatch_error is None
        elif action.status == "failed":
            assert action.dispatch_error is not None
    finally:
        db.close()


def test_dispatch_skips_non_planned():
    """Test that dispatching a non-planned action returns 'skipped'."""
    db = SessionLocal()
    try:
        # Find an already-dispatched action
        action = db.scalars(
            select(Action).where(Action.status.in_(["delivered", "failed"]))
        ).first()
        if not action:
            pytest.skip("No dispatched actions available")

        result = dispatch_action(action.id, db)
        assert result["result"] == "skipped"
    finally:
        db.close()


def test_dispatch_batch():
    """Test batch dispatch processes all remaining planned actions."""
    db = SessionLocal()
    try:
        summary = run_dispatch_batch(db)
        assert "total_dispatched" in summary
        assert "by_status" in summary
        assert "by_channel" in summary
        assert "failures" in summary

        # All planned should now be dispatched
        remaining_planned = db.scalars(
            select(Action).where(Action.status == "planned")
        ).all()
        assert len(remaining_planned) == 0
    finally:
        db.close()


def test_dispatch_batch_idempotent():
    """Running dispatch batch again processes 0 (no planned actions left)."""
    db = SessionLocal()
    try:
        summary = run_dispatch_batch(db)
        assert summary["total_dispatched"] == 0
    finally:
        db.close()


def test_dispatch_audit_trail():
    """Verify dispatch creates audit_log entries."""
    db = SessionLocal()
    try:
        audit = db.scalars(
            select(AuditLog).where(AuditLog.agent_name == "dispatch_service")
        ).first()
        assert audit is not None
        assert audit.decision.startswith("dispatch_")
    finally:
        db.close()


def test_reconcile_single_promise():
    """Test manually reconciling a single promise as 'kept'."""
    db = SessionLocal()
    try:
        # Create a test promise
        event = db.scalars(select(Event)).first()
        assert event is not None

        promise = Promise(
            event_id=event.id,
            promised_amount=Decimal("25000.00"),
            promised_date=date.today() + timedelta(days=5),
            status="pending",
            raw_reply_text="Test reconciliation promise",
        )
        db.add(promise)
        db.commit()
        db.refresh(promise)

        result = reconcile_payment(promise.id, db, source="manual")
        assert result["status"] == "kept"
        assert result["already_reconciled"] is False
        assert result["source"] == "manual"

        db.refresh(promise)
        assert promise.status == "kept"
        assert promise.reconciled_at is not None
        assert promise.reconciliation_source == "manual"

        # Reconciling again should return already_reconciled=True
        result2 = reconcile_payment(promise.id, db, source="manual")
        assert result2["already_reconciled"] is True
    finally:
        db.close()


def test_reconcile_not_found():
    """Test reconciling a non-existent promise raises ValueError."""
    db = SessionLocal()
    try:
        fake_id = uuid.uuid4()
        with pytest.raises(ValueError):
            reconcile_payment(fake_id, db)
    finally:
        db.close()


def test_simulate_reconciliation_batch():
    """Test simulated batch reconciliation marks some promises as kept."""
    db = SessionLocal()
    try:
        # Ensure we have pending promises linked to delivered actions
        summary = simulate_payment_reconciliation(db, reconciliation_rate=0.80)
        assert "total_eligible" in summary
        assert "reconciled_count" in summary
        assert "skipped_count" in summary
        assert summary["reconciliation_rate"] == 0.80

        # Verify some promises are now 'kept'
        kept_count = len(
            db.scalars(select(Promise).where(Promise.status == "kept")).all()
        )
        assert kept_count > 0
    finally:
        db.close()


def test_reconciliation_audit_trail():
    """Verify reconciliation creates audit_log entries."""
    db = SessionLocal()
    try:
        audit = db.scalars(
            select(AuditLog).where(AuditLog.agent_name == "payment_reconciliation")
        ).first()
        assert audit is not None
        assert "kept" in audit.decision
    finally:
        db.close()


def test_api_dispatch_batch():
    """Test POST /dispatch/run endpoint."""
    response = client.post("/dispatch/run")
    assert response.status_code == 200
    data = response.json()
    assert "total_dispatched" in data
    assert "by_status" in data
    assert "by_channel" in data


def test_api_dispatch_single_not_found():
    """Test POST /dispatch/{action_id} returns 404 for missing action."""
    fake_id = uuid.uuid4()
    response = client.post(f"/dispatch/{fake_id}")
    assert response.status_code == 404


def test_api_reconcile_single_not_found():
    """Test POST /reconcile/{promise_id} returns 404 for missing promise."""
    fake_id = uuid.uuid4()
    response = client.post(f"/reconcile/{fake_id}")
    assert response.status_code == 404


def test_api_simulate_reconciliation():
    """Test POST /reconcile/simulate/batch endpoint."""
    response = client.post("/reconcile/simulate/batch?reconciliation_rate=0.5")
    assert response.status_code == 200
    data = response.json()
    assert "total_eligible" in data
    assert "reconciled_count" in data
