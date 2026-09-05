import argparse
import os
import random
import sys
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List

# Ensure backend root is in sys.path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from sqlalchemy import delete, select
from app.database import SessionLocal
from app.models import Action, Event, InboundMessage, Promise


def generate_replies(actions_with_events: List[Any]) -> List[Dict[str, Any]]:
    """Generate realistic synthetic customer replies across target distributions."""
    random.seed(42)  # Deterministic seed for reproducible evaluation
    today = date.today()
    now_utc = datetime.now(timezone.utc)

    # Calculate past and future dates for promise generation
    past_date_1 = (today - timedelta(days=12)).isoformat()
    past_date_2 = (today - timedelta(days=5)).isoformat()
    past_date_3 = (today - timedelta(days=20)).isoformat()
    future_date_1 = (today + timedelta(days=4)).isoformat()
    future_date_2 = (today + timedelta(days=10)).isoformat()
    future_date_3 = (today + timedelta(days=18)).isoformat()

    # Reply intent pools
    promise_templates = [
        # Deliberately backdated promises (~1/3 of promises for broken-promise testing in Part E)
        # Note: Intentionally backdated for automated testing of the broken-promise evaluation path.
        (
            f"We had a brief delay in bank reconciliation, but I promise to clear the full amount by {past_date_1}.",
            None,
        ),
        (
            f"Will transfer ₹50,000 towards this pending balance by {past_date_2}. Thanks for your patience.",
            Decimal("50000.00"),
        ),
        (
            f"Apologies for the delay! We will initiate NEFT payment of ₹1,00,000 on {past_date_3}.",
            Decimal("100000.00"),
        ),
        # Valid future promises (~2/3 of promises)
        (
            f"Our billing cycle runs at month-end. We will settle this entire invoice by {future_date_1}.",
            None,
        ),
        (
            f"I will pay ₹75,000 on {future_date_2} as discussed with the accounts team.",
            Decimal("75000.00"),
        ),
        (
            f"Please hold off on followups. Payment of ₹1,20,000 will be made on {future_date_3}.",
            Decimal("120000.00"),
        ),
        (
            f"We are clearing all supplier dues by {future_date_1} afternoon.",
            None,
        ),
    ]

    dispute_templates = [
        "We are contesting this charge. 10 cases of detergent in the last shipment arrived damaged and water-soaked.",
        "There is a discrepancy in pricing. The agreed bulk discount of 12% was omitted from this invoice.",
        "Our warehouse team has not verified the delivery of these goods yet. Please send the signed Proof of Delivery (POD).",
        "We were double billed for the July subscription cycle. Please rectify the statement before requesting payment.",
    ]

    payment_made_templates = [
        "Payment was already completed yesterday via RTGS from our Axis Bank account. UTR ref: AXIS9928102831.",
        "We already transferred the full amount this morning. Please update your records.",
        "Auto-debit already deducted this amount from my ICICI account on the 1st. Please check your bank feed.",
    ]

    records = []

    # Distribution across eligible outreach actions:
    # ~40% promise_to_pay, ~20% dispute, ~15% payment_made, ~25% skipped
    for action, event in actions_with_events:
        roll = random.random()

        if roll < 0.25:
            # 25% Skipped (no customer reply)
            continue
        elif roll < 0.65:
            # 40% Promise to pay
            text_template, _ = random.choice(promise_templates)
            raw_text = text_template
        elif roll < 0.85:
            # 20% Dispute
            raw_text = random.choice(dispute_templates)
        else:
            # 15% Payment Made
            raw_text = random.choice(payment_made_templates)

        received_at = now_utc - timedelta(hours=random.randint(1, 48))

        records.append(
            {
                "event_id": event.id,
                "channel": action.channel if action.channel != "none" else "whatsapp",
                "raw_text": raw_text,
                "reply_type": None,  # Crucial: Unclassified for Part D agent
                "received_at": received_at,
            }
        )

    return records


def seed_customer_replies(reset: bool = False):
    """Seed PostgreSQL with synthetic inbound customer replies for planned actions."""
    db = SessionLocal()
    try:
        # Check existing inbound messages
        existing_count = db.scalar(select(InboundMessage.id))
        if existing_count:
            if not reset:
                print(
                    "\n[WARNING] Database already contains inbound messages. Use '--reset' flag to re-seed."
                )
                return
            else:
                print("[RESET] Deleting existing inbound messages and associated promises...")
                db.execute(delete(Promise))
                db.execute(delete(InboundMessage))
                db.commit()

        # Fetch eligible actions with channel != 'none'
        eligible = db.execute(
            select(Action, Event)
            .join(Event, Action.event_id == Event.id)
            .where(Action.channel != "none")
        ).all()

        if not eligible:
            print("[WARNING] No eligible outreach actions found (channel != 'none'). Please run intervention router first.")
            return

        print(f"[SEEDING] Generating synthetic customer replies for {len(eligible)} outreach actions...")
        reply_data = generate_replies(eligible)
        message_models = [InboundMessage(**row) for row in reply_data]
        db.add_all(message_models)
        db.commit()

        print("\n" + "=" * 55)
        print(" RECOUP SYNTHETIC CUSTOMER REPLIES GENERATION COMPLETE")
        print("=" * 55)
        print(f"Total Outreach Actions Evaluated : {len(eligible)}")
        print(f"Total Inbound Messages Created  : {len(message_models)}")
        print(f"Skipped / No Response Actions    : {len(eligible) - len(message_models)}")
        print("=" * 55 + "\n")

    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(
        description="Generate synthetic customer replies for planned outreach actions."
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Truncate existing inbound messages and re-seed.",
    )
    args = parser.parse_args()
    seed_customer_replies(reset=args.reset)


if __name__ == "__main__":
    main()
