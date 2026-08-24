from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Invoice
from app.schemas import InvoiceCreate, InvoiceResponse, PaginatedInvoicesResponse

router = APIRouter(prefix="/invoices", tags=["invoices"])


@router.get("", response_model=PaginatedInvoicesResponse)
def list_invoices(
    status: Optional[str] = Query(
        None, description="Filter invoices by status (paid, overdue, disputed, pending)"
    ),
    limit: int = Query(50, ge=1, le=500, description="Number of items to return"),
    offset: int = Query(0, ge=0, description="Number of items to skip"),
    db: Session = Depends(get_db),
):
    """List invoices with pagination and optional status filter."""
    base_query = select(Invoice)
    count_query = select(func.count(Invoice.id))

    if status:
        base_query = base_query.where(Invoice.status == status)
        count_query = count_query.where(Invoice.status == status)

    total = db.scalar(count_query) or 0
    items = db.scalars(
        base_query.order_by(Invoice.created_at.desc()).offset(offset).limit(limit)
    ).all()

    return PaginatedInvoicesResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=InvoiceResponse, status_code=status.HTTP_201_CREATED)
def create_invoice(
    invoice_in: InvoiceCreate,
    db: Session = Depends(get_db),
):
    """Create a new invoice."""
    invoice = Invoice(**invoice_in.model_dump())
    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    return invoice
