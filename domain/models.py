"""Domain models using Pydantic v2 for Voice AI Restaurant Bot."""

from datetime import date, time, datetime
from typing import Optional, Dict, Any
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict, field_validator

from .enums import ReservationStatus, CallIntent, CallStatus, AuditAction


class ReservationBase(BaseModel):
    """Base reservation model with common fields."""

    name: str = Field(..., min_length=1, max_length=100, description="Guest name")
    phone: str = Field(..., pattern=r"^\+?[1-9]\d{1,14}$", description="Phone number in E.164 format")
    date: date = Field(..., description="Reservation date")
    time: time = Field(..., description="Reservation time")
    guests: int = Field(..., ge=1, le=20, description="Number of guests")
    notes: Optional[str] = Field(None, max_length=500, description="Special requests or notes")

    model_config = ConfigDict(
        str_strip_whitespace=True,
        from_attributes=True,
    )


class ReservationCreate(ReservationBase):
    """Model for creating a new reservation."""

    pass


class ReservationUpdate(BaseModel):
    """Model for updating an existing reservation."""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    phone: Optional[str] = Field(None, pattern=r"^\+?[1-9]\d{1,14}$")
    date: Optional[date] = None
    time: Optional[time] = None
    guests: Optional[int] = Field(None, ge=1, le=20)
    notes: Optional[str] = Field(None, max_length=500)
    status: Optional[ReservationStatus] = None

    model_config = ConfigDict(str_strip_whitespace=True)


class ReservationRecord(ReservationBase):
    """Complete reservation record from database."""

    id: UUID
    status: ReservationStatus
    created_at: datetime
    updated_at: Optional[datetime] = None
    canceled_at: Optional[datetime] = None

    model_config = ConfigDict(
        from_attributes=True,
        str_strip_whitespace=True,
    )


class AvailabilityQuery(BaseModel):
    """Query model for checking availability."""

    date: date
    time: Optional[time] = None
    guests: int = Field(..., ge=1, le=20)
    duration_minutes: int = Field(default=90, ge=30, le=240)

    model_config = ConfigDict(str_strip_whitespace=True)


class AvailabilitySlot(BaseModel):
    """Available time slot."""

    time: time
    available_tables: int
    max_capacity: int

    model_config = ConfigDict(from_attributes=True)


class AvailabilityResponse(BaseModel):
    """Response with available slots."""

    date: date
    slots: list[AvailabilitySlot]
    total_available: int

    model_config = ConfigDict(from_attributes=True)


class CallStateData(BaseModel):
    """Call state data structure."""

    call_id: str
    phone_number: str
    intent: CallIntent
    status: CallStatus
    collected_data: Dict[str, Any] = Field(default_factory=dict)
    current_step: Optional[str] = None
    error_count: int = Field(default=0, ge=0)
    started_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(
        str_strip_whitespace=True,
        from_attributes=True,
    )

    @field_validator("collected_data", mode="before")
    @classmethod
    def validate_collected_data(cls, v: Any) -> Dict[str, Any]:
        """Ensure collected_data is a dictionary."""
        if v is None:
            return {}
        if isinstance(v, dict):
            return v
        raise ValueError("collected_data must be a dictionary")


class CallSessionCreate(BaseModel):
    """Model for creating a call session."""

    call_id: str = Field(..., min_length=1, max_length=100)
    phone_number: str = Field(..., pattern=r"^\+?[1-9]\d{1,14}$")
    intent: CallIntent = CallIntent.UNKNOWN
    status: CallStatus = CallStatus.INITIATED

    model_config = ConfigDict(str_strip_whitespace=True)


class CallSessionUpdate(BaseModel):
    """Model for updating a call session."""

    status: Optional[CallStatus] = None
    intent: Optional[CallIntent] = None
    collected_data: Optional[Dict[str, Any]] = None
    current_step: Optional[str] = None
    error_count: Optional[int] = Field(None, ge=0)

    model_config = ConfigDict(str_strip_whitespace=True)


class AuditLogEntry(BaseModel):
    """Audit log entry model."""

    id: int
    action: AuditAction
    entity_type: str = Field(..., max_length=50)
    entity_id: str = Field(..., max_length=100)
    user_id: Optional[str] = Field(None, max_length=100)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    ip_address: Optional[str] = Field(None, max_length=45)
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
        str_strip_whitespace=True,
    )


class AuditLogCreate(BaseModel):
    """Model for creating an audit log entry."""

    action: AuditAction
    entity_type: str = Field(..., max_length=50)
    entity_id: str = Field(..., max_length=100)
    user_id: Optional[str] = Field(None, max_length=100)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    ip_address: Optional[str] = Field(None, max_length=45)

    model_config = ConfigDict(str_strip_whitespace=True)


class ReservationCancelRequest(BaseModel):
    """Request to cancel a reservation."""

    reservation_id: UUID
    reason: Optional[str] = Field(None, max_length=500)

    model_config = ConfigDict(str_strip_whitespace=True)
