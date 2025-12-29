"""Database models for the Voice AI Restaurant Bot."""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, Enum, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import enum

Base = declarative_base()


class CallStatus(str, enum.Enum):
    """Call status enumeration."""
    INITIATED = "initiated"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class ReservationStatus(str, enum.Enum):
    """Reservation status enumeration."""
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class CallLog(Base):
    """Model for storing call logs."""
    __tablename__ = "call_logs"

    id = Column(Integer, primary_key=True, index=True)
    call_sid = Column(String(255), unique=True, index=True, nullable=False)
    from_number = Column(String(50), nullable=False)
    to_number = Column(String(50), nullable=False)
    status = Column(Enum(CallStatus), default=CallStatus.INITIATED, nullable=False)
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    ended_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    transcript = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    conversation_state = relationship("ConversationState", back_populates="call_log", uselist=False)
    reservation = relationship("Reservation", back_populates="call_log", uselist=False)


class ConversationState(Base):
    """Model for storing conversation state during calls."""
    __tablename__ = "conversation_states"

    id = Column(Integer, primary_key=True, index=True)
    call_sid = Column(String(255), ForeignKey("call_logs.call_sid"), unique=True, nullable=False, index=True)
    current_step = Column(String(100), default="greeting", nullable=False)
    state_data = Column(Text, nullable=True)  # JSON string of state data
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    call_log = relationship("CallLog", back_populates="conversation_state")


class Reservation(Base):
    """Model for storing restaurant reservations."""
    __tablename__ = "reservations"

    id = Column(Integer, primary_key=True, index=True)
    call_sid = Column(String(255), ForeignKey("call_logs.call_sid"), unique=True, nullable=True, index=True)
    customer_name = Column(String(255), nullable=False)
    customer_phone = Column(String(50), nullable=False)
    party_size = Column(Integer, nullable=False)
    reservation_date = Column(DateTime, nullable=False)
    special_requests = Column(Text, nullable=True)
    status = Column(Enum(ReservationStatus), default=ReservationStatus.PENDING, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    call_log = relationship("CallLog", back_populates="reservation")
