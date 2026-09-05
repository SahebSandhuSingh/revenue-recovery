import logging
import os
from typing import Any, Dict, List, Optional
import razorpay

from dotenv import load_dotenv
load_dotenv()

logger = logging.getLogger(__name__)


class RazorpayClient:
    """Wrapper client for Razorpay Payment Gateway, Subscriptions, and Mandates."""

    def __init__(
        self,
        key_id: Optional[str] = None,
        key_secret: Optional[str] = None,
    ):
        self.key_id = key_id or os.getenv("RAZORPAY_KEY_ID", "")
        self.key_secret = key_secret or os.getenv("RAZORPAY_KEY_SECRET", "")

        if self.key_id and self.key_secret:
            self.client = razorpay.Client(auth=(self.key_id, self.key_secret))
            self.client.set_app_details({"title": "Recoup", "version": "1.0.0"})
        else:
            self.client = None
            logger.warning(
                "RazorpayClient initialized without API keys; running in sandbox/mock stub mode."
            )

    def fetch_failed_payments(self, count: int = 100, skip: int = 0) -> List[Dict[str, Any]]:
        """Fetch failed one-off payments from Razorpay test/live gateway."""
        if not self.client:
            logger.warning("fetch_failed_payments: Razorpay client not configured.")
            return []
        try:
            res = self.client.payment.all({"count": count, "skip": skip})
            items = res.get("items", [])
            return [p for p in items if p.get("status") == "failed"]
        except Exception as exc:
            logger.error(f"Error fetching payments from Razorpay: {exc}")
            return []

    def fetch_failed_subscriptions(self, count: int = 100, skip: int = 0) -> List[Dict[str, Any]]:
        """Fetch failed recurring subscription charges from Razorpay."""
        if not self.client:
            return []
        try:
            res = self.client.subscription.all({"count": count, "skip": skip})
            items = res.get("items", [])
            return [s for s in items if s.get("status") in ("pending", "halted")]
        except Exception as exc:
            logger.error(f"Error fetching subscriptions from Razorpay: {exc}")
            return []

    def fetch_failed_mandates(self, count: int = 100, skip: int = 0) -> List[Dict[str, Any]]:
        """Fetch failed e-mandate and UPI AutoPay recurring debit attempts."""
        logger.info("Stub: fetch_failed_mandates called (returning empty list)")
        return []

    def sync_failed_payments(self, db) -> int:
        """Fetch failed payments from Razorpay test API and persist into events table."""
        from decimal import Decimal
        from sqlalchemy import select
        from app.models import Event

        failed_payments = self.fetch_failed_payments()
        synced = 0
        for item in failed_payments:
            payment_id = item.get("id")
            existing = db.scalars(
                select(Event).where(Event.source_id == payment_id)
            ).first()
            if not existing:
                amount = Decimal(item.get("amount", 0)) / 100
                ev = Event(
                    source_type="checkout",
                    data_source="razorpay",
                    source_id=payment_id,
                    customer_id=item.get("contact") or item.get("email") or f"cust_{payment_id}",
                    amount=amount,
                    currency=item.get("currency", "INR"),
                    status="failed",
                    raw_payload=item,
                )
                db.add(ev)
                synced += 1
        if synced > 0:
            db.commit()
        return synced
