"""Pydantic schemas for request/response validation."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from database.models import CallStatus, ReservationStatus


# CallLog Schemas
class CallLogBase(BaseModel):
    """Base schema for CallLog."""
    call_sid: str
    from_number: str
    to_number: str
    status: CallStatus


class CallLogCreate(CallLogBase):
    """Schema for creating a CallLog."""
    pass


class CallLogUpdate(BaseModel):
    """Schema for updating a CallLog."""
    status: Optional[CallStatus] = None
    ended_at: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    transcript: Optional[str] = None


class CallLogResponse(CallLogBase):
    """Schema for CallLog response."""
    id: int
    started_at: datetime
    ended_at: Optional[datetime]
    duration_seconds: Optional[int]
    transcript: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ConversationState Schemas
class ConversationStateBase(BaseModel):
    """Base schema for ConversationState."""
    call_sid: str
    current_step: str
    state_data: Optional[str] = None


class ConversationStateCreate(ConversationStateBase):
    """Schema for creating a ConversationState."""
    pass


class ConversationStateUpdate(BaseModel):
    """Schema for updating a ConversationState."""
    current_step: Optional[str] = None
    state_data: Optional[str] = None


class ConversationStateResponse(ConversationStateBase):
    """Schema for ConversationState response."""
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Reservation Schemas
class ReservationBase(BaseModel):
    """Base schema for Reservation."""
    customer_name: str
    customer_phone: str
    party_size: int = Field(..., gt=0, le=50)
    reservation_date: datetime
    special_requests: Optional[str] = None


class ReservationCreate(ReservationBase):
    """Schema for creating a Reservation."""
    call_sid: Optional[str] = None


class ReservationUpdate(BaseModel):
    """Schema for updating a Reservation."""
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    party_size: Optional[int] = Field(None, gt=0, le=50)
    reservation_date: Optional[datetime] = None
    special_requests: Optional[str] = None
    status: Optional[ReservationStatus] = None


class ReservationResponse(ReservationBase):
    """Schema for Reservation response."""
    id: int
    call_sid: Optional[str]
    status: ReservationStatus
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
