from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import SyncResult
from app.services.razorpay_client import RazorpayClient

router = APIRouter(prefix="/razorpay", tags=["razorpay"])


@router.post(
    "/sync",
    response_model=SyncResult,
    summary="Synchronize failed payments from Razorpay test API to events table",
)
def sync_razorpay_endpoint(db: Session = Depends(get_db)):
    """Fetch failed payments from Razorpay test API and ingest new events."""
    client = RazorpayClient()
    synced_count = client.sync_failed_payments(db)
    return SyncResult(
        synced_count=synced_count,
        message=f"Successfully synced {synced_count} Razorpay failed payment event(s).",
    )
