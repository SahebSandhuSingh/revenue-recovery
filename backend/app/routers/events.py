from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Event
from app.schemas import EventCreate, EventResponse, PaginatedEventsResponse

router = APIRouter(prefix="/events", tags=["events"])


@router.get("", response_model=PaginatedEventsResponse)
def list_events(
    limit: int = Query(50, ge=1, le=500, description="Number of items to return"),
    offset: int = Query(0, ge=0, description="Number of items to skip"),
    db: Session = Depends(get_db),
):
    """List all events with pagination."""
    total = db.scalar(select(func.count(Event.id))) or 0
    query = (
        select(Event)
        .order_by(Event.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    items = db.scalars(query).all()

    return PaginatedEventsResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
def create_event(
    event_in: EventCreate,
    db: Session = Depends(get_db),
):
    """Create a new event."""
    event = Event(**event_in.model_dump())
    db.add(event)
    db.commit()
    db.refresh(event)
    return event
