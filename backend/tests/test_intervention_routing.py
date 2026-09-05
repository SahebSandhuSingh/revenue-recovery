import os
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, delete

from app.constants import ACTION_TYPES, CHANNELS, PRIORITIES, ROOT_CAUSES
from app.database import SessionLocal
from app.main import app
from app.models import Action, AuditLog, Diagnosis, Event, Invoice
from app.schemas import ActionType, Channel, Priority, DiagnosisRootCause
from app.services.context_builder import build_case_context
from app.services.diagnosis_agent import (
    check_mock_mode_disabled,
    diagnose_event,
    is_mock_mode,
    run_diagnosis_batch,
)
from app.services.event_sync import sync_invoices_to_events
from app.services.intervention_agent import (
    route_intervention,
    run_intervention_batch,
)
from app.data.generate_synthetic_invoices import seed_database
from app.data.generate_synthetic_consumer_events import seed_consumer_events

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_test_data():
    """Ensure database has fresh synthetic invoices, consumer events, and diagnoses."""
    seed_database(reset=True)
    seed_consumer_events(reset=True)
    db = SessionLocal()
    try:
        # Pre-diagnose events so intervention router has diagnosed cases to work with
        run_diagnosis_batch(db=db)
    finally:
        db.close()
    yield


def test_fix2_constants_dynamic_literal_derivation():
    """FIX 2: Verify ActionType, Channel, Priority, and DiagnosisRootCause match constants."""
    assert len(ROOT_CAUSES) == 5
    assert len(ACTION_TYPES) == 5
    assert len(CHANNELS) == 5
    assert len(PRIORITIES) == 3

    # Confirm action taxonomy
    for at in [
        "silent_retry",
        "payment_method_update_request",
        "dispute_resolution_draft",
        "payment_plan_offer",
        "friendly_nudge",
    ]:
        assert at in ACTION_TYPES

    # Confirm channels
    for ch in ["none", "email", "whatsapp", "sms", "voice"]:
        assert ch in CHANNELS

    # Confirm priorities
    for pr in ["low", "medium", "high"]:
        assert pr in PRIORITIES


def test_fix3_require_real_agent_enforcement():
    """FIX 3: Verify require_real_agent=True raises an error when GROQ_API_KEY is not set."""
    if is_mock_mode():
        db = SessionLocal()
        try:
            # 1. Test in route_intervention
            event_with_diag = db.scalars(
                select(Event).join(Diagnosis, Event.id == Diagnosis.event_id)
            ).first()
            assert event_with_diag is not None

            with pytest.raises(RuntimeError) as exc_info1:
                route_intervention(
                    event_with_diag.id, db, require_real_agent=True
                )
            assert "Mock mode is active" in str(exc_info1.value)

            # 2. Test in run_intervention_batch
            with pytest.raises(RuntimeError) as exc_info2:
                run_intervention_batch(db, require_real_agent=True)
            assert "Mock mode is active" in str(exc_info2.value)
        finally:
            db.close()


def test_fix4_get_event_action_404():
    """FIX 4: Verify GET /events/{event_id}/action returns 404 for unassociated/non-existent events."""
    random_event_id = uuid.uuid4()
    response = client.get(f"/events/{random_event_id}/action")
    assert response.status_code == 404
    assert "No planned action found" in response.json()["detail"]


def test_route_intervention_single_and_invariants():
    """Test single event intervention routing and channel invariants."""
    db = SessionLocal()
    try:
        # Find a diagnosed event
        diag = db.scalars(select(Diagnosis)).first()
        assert diag is not None
        event_id = diag.event_id

        # Clean existing action if any
        db.execute(delete(Action).where(Action.event_id == event_id))
        db.execute(
            delete(AuditLog).where(
                AuditLog.event_id == event_id,
                AuditLog.agent_name == "intervention_router_agent",
            )
        )
        db.commit()

        # Route intervention
        res = route_intervention(event_id, db)
        assert res["action_type"] in ACTION_TYPES
        assert res["channel"] in CHANNELS
        assert res["priority"] in PRIORITIES
        assert res["status"] in ("planned", "blocked_pending_review")

        if res["action_type"] == "silent_retry":
            assert res["channel"] == "none"
            assert res["message_draft"] is None or res["message_draft"] == ""
        else:
            assert res["channel"] != "none"
            assert res["message_draft"] is not None and len(res["message_draft"]) > 0

        # Verify audit log entry
        audit = db.scalars(
            select(AuditLog).where(
                AuditLog.event_id == event_id,
                AuditLog.agent_name == "intervention_router_agent",
            )
        ).first()
        assert audit is not None
        assert audit.decision == res["action_type"]
        assert len(audit.reasoning) > 0
    finally:
        db.close()


def test_batch_intervention_routing_and_idempotency():
    """Test run_intervention_batch and verify idempotency on subsequent runs."""
    db = SessionLocal()
    try:
        # 1. Run batch intervention
        summary1 = run_intervention_batch(db)
        assert "total_processed" in summary1
        assert "by_action_type" in summary1
        assert "by_channel" in summary1
        assert "failures" in summary1
        assert isinstance(summary1["failures"], list)

        # Confirm multiple action types are populated
        non_zero_actions = [
            count for count in summary1["by_action_type"].values() if count > 0
        ]
        assert len(non_zero_actions) >= 3

        # 2. Run again -> must be 0 (Idempotency)
        summary2 = run_intervention_batch(db)
        assert summary2["total_processed"] == 0
    finally:
        db.close()


def test_api_endpoints_actions():
    """Test /route/run and /actions API endpoints."""
    # 1. Trigger /route/run
    res_run = client.post("/route/run")
    assert res_run.status_code == 200
    data_run = res_run.json()
    assert "total_processed" in data_run
    assert "by_action_type" in data_run
    assert "by_channel" in data_run

    # 2. List all actions
    res_actions = client.get("/actions?limit=50")
    assert res_actions.status_code == 200
    data_actions = res_actions.json()
    assert data_actions["total"] > 0
    assert len(data_actions["items"]) > 0

    first_act = data_actions["items"][0]
    assert first_act["action_type"] in ACTION_TYPES
    assert first_act["source_type"] is not None

    # 3. Filter by action_type
    target_at = first_act["action_type"]
    res_filter_at = client.get(f"/actions?action_type={target_at}")
    assert res_filter_at.status_code == 200
    for act in res_filter_at.json()["items"]:
        assert act["action_type"] == target_at

    # 4. Filter by channel
    target_ch = first_act["channel"]
    res_filter_ch = client.get(f"/actions?channel={target_ch}")
    assert res_filter_ch.status_code == 200
    for act in res_filter_ch.json()["items"]:
        assert act["channel"] == target_ch

    # 5. Get action by event ID
    event_id = first_act["event_id"]
    res_single = client.get(f"/events/{event_id}/action")
    assert res_single.status_code == 200
    assert res_single.json()["event_id"] == str(event_id)
    assert res_single.json()["action_type"] == target_at
