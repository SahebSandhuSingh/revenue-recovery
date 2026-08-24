import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.constants import (
    ACTION_TYPES,
    CHANNELS,
    PRIORITIES,
    PROMISE_STATUSES,
    REPLY_TYPES,
    ROOT_CAUSES,
)

# Literal types derived directly from constants.py (FIX 2 & FIX 4)
EventSourceType = Literal["checkout", "subscription", "mandate", "invoice"]
InvoiceStatus = Literal["paid", "overdue", "disputed", "pending"]

DiagnosisRootCause = Literal[tuple(ROOT_CAUSES)]
ActionType = Literal[tuple(ACTION_TYPES)]
Channel = Literal[tuple(CHANNELS)]
Priority = Literal[tuple(PRIORITIES)]
ReplyType = Literal[tuple(REPLY_TYPES)]
PromiseStatus = Literal[tuple(PROMISE_STATUSES)]


# --- Health Schema ---
class HealthResponse(BaseModel):
    status: str
    database: str


# --- Event Schemas ---
class EventBase(BaseModel):
    source_type: EventSourceType
    source_id: str = Field(..., max_length=255)
    customer_id: str = Field(..., max_length=255)
    amount: Decimal = Field(..., ge=0)
    currency: str = Field(default="INR", max_length=10)
    status: str = Field(..., max_length=50)
    raw_payload: Dict[str, Any] = Field(default_factory=dict)


class EventCreate(EventBase):
    pass


class EventResponse(EventBase):
    id: uuid.UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaginatedEventsResponse(BaseModel):
    items: List[EventResponse]
    total: int
    limit: int
    offset: int


# --- Invoice Schemas ---
class InvoiceBase(BaseModel):
    customer_id: str = Field(..., max_length=255)
    invoice_number: str = Field(..., max_length=100)
    gst_number: str = Field(..., max_length=20)
    hsn_code: str = Field(..., max_length=20)
    amount: Decimal = Field(..., ge=0)
    due_date: date
    credit_terms: str = Field(..., max_length=50)
    status: InvoiceStatus


class InvoiceCreate(InvoiceBase):
    pass


class InvoiceResponse(InvoiceBase):
    id: uuid.UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaginatedInvoicesResponse(BaseModel):
    items: List[InvoiceResponse]
    total: int
    limit: int
    offset: int


# --- Sync Schema ---
class SyncResult(BaseModel):
    synced_count: int
    message: str


# --- Diagnosis Schemas ---
class DiagnosisResponse(BaseModel):
    id: uuid.UUID
    event_id: uuid.UUID
    root_cause: Optional[DiagnosisRootCause] = None
    confidence: Optional[float] = Field(None, ge=0, le=1)
    reasoning: Optional[str] = None
    created_at: datetime
    # Event metadata join fields
    source_type: Optional[str] = None
    customer_id: Optional[str] = None
    amount: Optional[Decimal] = None
    currency: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class PaginatedDiagnosesResponse(BaseModel):
    items: List[DiagnosisResponse]
    total: int
    limit: int
    offset: int


class DiagnosisBatchFailure(BaseModel):
    event_id: str
    error: str
    retry_count: int


class DiagnosisBatchSummary(BaseModel):
    total_processed: int
    by_root_cause: Dict[str, int]
    failures: List[DiagnosisBatchFailure]


# --- Intervention / Action Schemas ---
class ActionResponse(BaseModel):
    id: uuid.UUID
    event_id: uuid.UUID
    action_type: Optional[ActionType] = None
    channel: Optional[Channel] = None
    priority: Optional[Priority] = None
    message_draft: Optional[str] = None
    status: Optional[str] = "planned"
    created_at: datetime
    # Event metadata join fields
    source_type: Optional[str] = None
    customer_id: Optional[str] = None
    amount: Optional[Decimal] = None
    currency: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class PaginatedActionsResponse(BaseModel):
    items: List[ActionResponse]
    total: int
    limit: int
    offset: int


class ActionBatchFailure(BaseModel):
    event_id: str
    error: str
    retry_count: int


class ActionBatchSummary(BaseModel):
    total_processed: int
    by_action_type: Dict[str, int]
    by_channel: Dict[str, int]
    failures: List[ActionBatchFailure]


# --- Promise Schemas ---
class PromiseResponse(BaseModel):
    id: uuid.UUID
    event_id: uuid.UUID
    promised_amount: Optional[Decimal] = None
    promised_date: Optional[date] = None
    status: Optional[PromiseStatus] = None
    raw_reply_text: Optional[str] = None
    created_at: Optional[datetime] = None
    # Joined event fields
    source_type: Optional[str] = None
    customer_id: Optional[str] = None
    amount: Optional[Decimal] = None
    currency: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class PaginatedPromisesResponse(BaseModel):
    items: List[PromiseResponse]
    total: int
    limit: int
    offset: int


class PromiseEvaluationSummary(BaseModel):
    evaluated: int
    newly_broken: int
    still_pending: int


# --- Reply Processing Schemas ---
class ReplyBatchFailure(BaseModel):
    message_id: str
    error: str
    retry_count: int


class ReplyProcessingBatchSummary(BaseModel):
    total_processed: int
    by_reply_type: Dict[str, int]
    promises_created: int
    failures: List[ReplyBatchFailure]


# --- Compliance Schemas ---
class ComplianceStatusResponse(BaseModel):
    id: uuid.UUID
    customer_id: str
    contact_count: int
    last_contact_at: Optional[datetime] = None
    escalation_flag: bool
    broken_promises_count: Optional[int] = None
    escalation_reason: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class PaginatedComplianceResponse(BaseModel):
    items: List[ComplianceStatusResponse]
    total: int
    limit: int
    offset: int
