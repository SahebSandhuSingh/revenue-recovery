import argparse
import os
import random
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List

# Ensure backend root is in sys.path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from sqlalchemy import delete, func, select
from app.database import SessionLocal
from app.models import Event

# Overlapping and distinct consumer customer IDs
OVERLAPPING_CUSTOMERS = [
    "CUST-DELHI-KIRANA-01",
    "CUST-MUMBAI-RETAIL-02",
    "CUST-BLR-MART-03",
]

CONSUMER_CUSTOMERS = [
    f"CUST-CONSUMER-{i:03d}" for i in range(101, 125)
]


def generate_checkout_events() -> List[Dict[str, Any]]:
    """Generate 10 realistic checkout payment failure events."""
    events = [
        # Soft declines (~5)
        {
            "amount": Decimal("1499.00"),
            "status": "failed",
            "payload": {
                "error_code": "GATEWAY_ERROR",
                "error_description": "Bank network connection timed out during 3DS authentication",
                "error_reason": "bank_technical_glitch",
                "method": "upi",
                "bank": "HDFC",
                "acquirer_data": {"rrn": "329810293812"},
            },
        },
        {
            "amount": Decimal("2999.00"),
            "status": "failed",
            "payload": {
                "error_code": "BAD_REQUEST_PAYMENT_TIMED_OUT",
                "error_description": "Customer did not complete MPIN authorization within 8 minutes",
                "error_reason": "payment_timed_out",
                "method": "upi",
                "bank": "ICICI",
            },
        },
        {
            "amount": Decimal("850.00"),
            "status": "failed",
            "payload": {
                "error_code": "GATEWAY_ERROR",
                "error_description": "Issuer switch inoperative / NPCI downtime",
                "error_reason": "network_failure",
                "method": "netbanking",
                "bank": "SBI",
            },
        },
        {
            "amount": Decimal("4500.00"),
            "status": "failed",
            "payload": {
                "error_code": "BAD_REQUEST_ERROR",
                "error_description": "Incorrect OTP entered by customer twice",
                "error_reason": "authentication_failed",
                "method": "card",
                "card_network": "Visa",
            },
        },
        {
            "amount": Decimal("1200.00"),
            "status": "failed",
            "payload": {
                "error_code": "GATEWAY_ERROR",
                "error_description": "Temporary payment processing delay at beneficiary bank",
                "error_reason": "server_timeout",
                "method": "upi",
                "bank": "Axis",
            },
        },
        # Hard declines (~3)
        {
            "amount": Decimal("6400.00"),
            "status": "failed",
            "payload": {
                "error_code": "BAD_REQUEST_ERROR",
                "error_description": "Card expiry date has passed (Exp: 01/24)",
                "error_reason": "expired_card",
                "method": "card",
                "card_network": "Mastercard",
                "card_last4": "4242",
            },
        },
        {
            "amount": Decimal("12500.00"),
            "status": "failed",
            "payload": {
                "error_code": "BAD_REQUEST_ERROR",
                "error_description": "Card reported lost or stolen by cardholder",
                "error_reason": "card_blocked_permanently",
                "method": "card",
                "card_network": "Visa",
                "card_last4": "8811",
            },
        },
        {
            "amount": Decimal("990.00"),
            "status": "failed",
            "payload": {
                "error_code": "BAD_REQUEST_ERROR",
                "error_description": "International transactions not enabled on domestic debit card",
                "error_reason": "channel_disabled",
                "method": "card",
                "card_network": "RuPay",
            },
        },
        # Ambiguous / Cash flow distress (~2)
        {
            "amount": Decimal("18500.00"),
            "status": "failed",
            "payload": {
                "error_code": "BAD_REQUEST_ERROR",
                "error_description": "Transaction declined due to insufficient funds in account",
                "error_reason": "insufficient_funds",
                "method": "netbanking",
                "bank": "HDFC",
                "failure_count_30d": 4,
            },
        },
        {
            "amount": Decimal("24000.00"),
            "status": "failed",
            "payload": {
                "error_code": "BAD_REQUEST_ERROR",
                "error_description": "Customer account balance below required transaction threshold",
                "error_reason": "insufficient_funds",
                "method": "upi",
                "bank": "SBI",
            },
        },
    ]

    all_custs = OVERLAPPING_CUSTOMERS + CONSUMER_CUSTOMERS
    results = []
    for i, e in enumerate(events):
        cust_id = all_custs[i % len(all_custs)]
        results.append(
            {
                "source_type": "checkout",
                "source_id": f"pay_chk_{1000 + i}",
                "customer_id": cust_id,
                "amount": e["amount"],
                "currency": "INR",
                "status": e["status"],
                "raw_payload": e["payload"],
            }
        )
    return results


def generate_subscription_events() -> List[Dict[str, Any]]:
    """Generate 10 realistic recurring subscription failure events."""
    events = [
        # Soft declines (~5)
        {
            "amount": Decimal("999.00"),
            "status": "failed",
            "payload": {
                "subscription_id": "sub_premium_01",
                "plan_name": "Pro Monthly Plan",
                "subscription_status": "active",
                "retry_count": 1,
                "max_retries": 3,
                "failure_reason": "issuer_timeout",
                "error_code": "GATEWAY_TIMEOUT",
                "next_retry_at": "2026-08-26T00:00:00Z",
            },
        },
        {
            "amount": Decimal("1999.00"),
            "status": "failed",
            "payload": {
                "subscription_id": "sub_team_02",
                "plan_name": "Team Annual Subscription",
                "subscription_status": "active",
                "retry_count": 2,
                "max_retries": 4,
                "failure_reason": "bank_down",
                "error_code": "ISSUER_SWITCH_DOWN",
                "next_retry_at": "2026-08-27T00:00:00Z",
            },
        },
        {
            "amount": Decimal("499.00"),
            "status": "failed",
            "payload": {
                "subscription_id": "sub_starter_03",
                "plan_name": "Starter Cloud Tier",
                "subscription_status": "active",
                "retry_count": 1,
                "max_retries": 3,
                "failure_reason": "temporary_bank_rate_limit",
                "error_code": "RATE_LIMIT_EXCEEDED",
            },
        },
        {
            "amount": Decimal("1499.00"),
            "status": "failed",
            "payload": {
                "subscription_id": "sub_growth_04",
                "plan_name": "Growth Analytics Plan",
                "subscription_status": "active",
                "retry_count": 1,
                "max_retries": 3,
                "failure_reason": "card_security_validation_in_progress",
                "error_code": "SECURITY_CHECK_PENDING",
            },
        },
        {
            "amount": Decimal("799.00"),
            "status": "failed",
            "payload": {
                "subscription_id": "sub_music_05",
                "plan_name": "Family Stream Bundle",
                "subscription_status": "active",
                "retry_count": 2,
                "max_retries": 3,
                "failure_reason": "upi_autopay_psp_busy",
                "error_code": "PSP_UNAVAILABLE",
            },
        },
        # Hard declines (~3)
        {
            "amount": Decimal("3499.00"),
            "status": "halted",
            "payload": {
                "subscription_id": "sub_enterprise_06",
                "plan_name": "Enterprise Core",
                "subscription_status": "halted",
                "retry_count": 4,
                "max_retries": 4,
                "failure_reason": "card_expired_no_updated_token",
                "error_code": "TOKEN_EXPIRED",
                "card_last4": "1009",
            },
        },
        {
            "amount": Decimal("2499.00"),
            "status": "cancelled",
            "payload": {
                "subscription_id": "sub_saas_07",
                "plan_name": "Developer Pro Suite",
                "subscription_status": "cancelled",
                "retry_count": 3,
                "failure_reason": "recurring_mandate_revoked_by_customer_bank",
                "error_code": "MANDATE_REVOKED",
            },
        },
        {
            "amount": Decimal("899.00"),
            "status": "halted",
            "payload": {
                "subscription_id": "sub_fitness_08",
                "plan_name": "Daily Fitness Pass",
                "subscription_status": "halted",
                "retry_count": 4,
                "failure_reason": "account_closed",
                "error_code": "ACCOUNT_DOES_NOT_EXIST",
            },
        },
        # Ambiguous / Cash flow distress (~2)
        {
            "amount": Decimal("7500.00"),
            "status": "pending",
            "payload": {
                "subscription_id": "sub_b2b_tools_09",
                "plan_name": "Agency Suite Monthly",
                "subscription_status": "pending",
                "retry_count": 3,
                "max_retries": 4,
                "failure_reason": "insufficient_balance_on_due_date",
                "error_code": "LOW_BALANCE",
                "recurring_streak_failed": 3,
            },
        },
        {
            "amount": Decimal("12000.00"),
            "status": "pending",
            "payload": {
                "subscription_id": "sub_cloud_10",
                "plan_name": "High Compute Cluster",
                "subscription_status": "pending",
                "retry_count": 3,
                "max_retries": 4,
                "failure_reason": "repeated_debit_declined_nsf",
                "error_code": "NON_SUFFICIENT_FUNDS",
            },
        },
    ]

    all_custs = CONSUMER_CUSTOMERS[5:] + OVERLAPPING_CUSTOMERS
    results = []
    for i, e in enumerate(events):
        cust_id = all_custs[i % len(all_custs)]
        results.append(
            {
                "source_type": "subscription",
                "source_id": f"sub_evt_{2000 + i}",
                "customer_id": cust_id,
                "amount": e["amount"],
                "currency": "INR",
                "status": e["status"],
                "raw_payload": e["payload"],
            }
        )
    return results


def generate_mandate_events() -> List[Dict[str, Any]]:
    """Generate 10 realistic UPI AutoPay and e-mandate failure events."""
    events = [
        # Soft declines (~5)
        {
            "amount": Decimal("3500.00"),
            "status": "failed",
            "payload": {
                "umn": "recoup.mandate.hdfc.001@upi",
                "mandate_status": "failed",
                "failure_reason": "debit_execution_timeout_npci",
                "error_code": "NPCI_PROCESSING_TIMEOUT",
                "frequency": "monthly",
            },
        },
        {
            "amount": Decimal("1500.00"),
            "status": "failed",
            "payload": {
                "umn": "recoup.mandate.icici.002@upi",
                "mandate_status": "failed",
                "failure_reason": "bank_cbs_offline_nightly_batch",
                "error_code": "CORE_BANKING_UNAVAILABLE",
                "frequency": "monthly",
            },
        },
        {
            "amount": Decimal("4200.00"),
            "status": "failed",
            "payload": {
                "umn": "recoup.mandate.sbi.003@upi",
                "mandate_status": "failed",
                "failure_reason": "remitter_bank_throttle_limit",
                "error_code": "BANK_RATE_LIMIT",
                "frequency": "monthly",
            },
        },
        {
            "amount": Decimal("2100.00"),
            "status": "failed",
            "payload": {
                "umn": "recoup.mandate.axis.004@upi",
                "mandate_status": "failed",
                "failure_reason": "upi_switch_technical_error",
                "error_code": "PSP_TECHNICAL_ERROR",
                "frequency": "monthly",
            },
        },
        {
            "amount": Decimal("5000.00"),
            "status": "failed",
            "payload": {
                "umn": "recoup.mandate.kotak.005@upi",
                "mandate_status": "failed",
                "failure_reason": "scheduled_execution_window_missed",
                "error_code": "WINDOW_EXPIRED",
                "frequency": "monthly",
            },
        },
        # Hard declines (~3)
        {
            "amount": Decimal("7500.00"),
            "status": "revoked",
            "payload": {
                "umn": "recoup.mandate.hdfc.006@upi",
                "mandate_status": "revoked",
                "failure_reason": "customer_manually_cancelled_mandate_in_upi_app",
                "error_code": "MANDATE_USER_REVOKED",
                "revoked_at": "2026-08-20T10:30:00Z",
            },
        },
        {
            "amount": Decimal("10000.00"),
            "status": "expired",
            "payload": {
                "umn": "recoup.mandate.sbi.007@upi",
                "mandate_status": "expired",
                "failure_reason": "mandate_validity_period_ended",
                "error_code": "VALIDITY_PERIOD_EXPIRED",
                "valid_until": "2026-07-31",
            },
        },
        {
            "amount": Decimal("6200.00"),
            "status": "revoked",
            "payload": {
                "umn": "recoup.mandate.icici.008@upi",
                "mandate_status": "revoked",
                "failure_reason": "account_frozen_or_debit_freeze_active",
                "error_code": "ACCOUNT_DEBIT_BLOCKED",
            },
        },
        # Ambiguous / Cash flow distress (~2)
        {
            "amount": Decimal("15000.00"),
            "status": "failed",
            "payload": {
                "umn": "recoup.mandate.axis.009@upi",
                "mandate_status": "failed",
                "failure_reason": "insufficient_balance_in_linked_account",
                "error_code": "INSUFFICIENT_FUNDS_U16",
                "consecutive_failed_cycles": 2,
            },
        },
        {
            "amount": Decimal("22000.00"),
            "status": "failed",
            "payload": {
                "umn": "recoup.mandate.kotak.010@upi",
                "mandate_status": "failed",
                "failure_reason": "debit_declined_insufficient_funds",
                "error_code": "NSF_REJECTED",
                "consecutive_failed_cycles": 3,
            },
        },
    ]

    all_custs = CONSUMER_CUSTOMERS[12:] + OVERLAPPING_CUSTOMERS
    results = []
    for i, e in enumerate(events):
        cust_id = all_custs[i % len(all_custs)]
        results.append(
            {
                "source_type": "mandate",
                "source_id": f"man_evt_{3000 + i}",
                "customer_id": cust_id,
                "amount": e["amount"],
                "currency": "INR",
                "status": e["status"],
                "raw_payload": e["payload"],
            }
        )
    return results


def seed_consumer_events(reset: bool = False):
    """Seed ~30 synthetic consumer-side events into PostgreSQL."""
    db = SessionLocal()
    try:
        # Check existing consumer events
        existing = db.scalars(
            select(Event).where(
                Event.source_type.in_(["checkout", "subscription", "mandate"])
            )
        ).all()

        if len(existing) > 0:
            if not reset:
                print(
                    f"\n[WARNING] Database already contains {len(existing)} consumer events."
                )
                print("Use '--reset' flag to truncate consumer events and re-seed.")
                return
            else:
                print(f"[RESET] Deleting {len(existing)} existing consumer events...")
                db.execute(
                    delete(Event).where(
                        Event.source_type.in_(["checkout", "subscription", "mandate"])
                    )
                )
                db.commit()

        print("[SEEDING] Generating ~30 synthetic consumer events...")
        checkout_events = generate_checkout_events()
        subscription_events = generate_subscription_events()
        mandate_events = generate_mandate_events()

        all_records = checkout_events + subscription_events + mandate_events
        event_models = [Event(**row) for row in all_records]
        db.add_all(event_models)
        db.commit()

        print("\n" + "=" * 55)
        print(" RECOUP SYNTHETIC CONSUMER EVENTS SEEDING COMPLETE")
        print("=" * 55)
        print(f"Total Consumer Events : {len(event_models)}")
        print(f"Unique Customers      : {len(set(r['customer_id'] for r in all_records))}")
        print("-" * 55)
        print("Breakdown by Source Type:")
        print(f"  - CHECKOUT     : {len(checkout_events):>2} events")
        print(f"  - SUBSCRIPTION : {len(subscription_events):>2} events")
        print(f"  - MANDATE      : {len(mandate_events):>2} events")
        print("=" * 55 + "\n")

    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(
        description="Seed Recoup database with ~30 synthetic consumer payment failure events."
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Truncate existing consumer events and re-seed.",
    )
    args = parser.parse_args()
    seed_consumer_events(reset=args.reset)


if __name__ == "__main__":
    main()
