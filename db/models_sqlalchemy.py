"""SQLAlchemy models for Voice AI Restaurant Bot database tables."""

from datetime import datetime, date, time
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import String, Integer, DateTime, Date, Time, Text, JSON, Index
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin
from domain.enums import ReservationStatus, CallIntent, CallStatus, AuditAction


class Reservation(Base, TimestampMixin):
    """Reservation table model."""

    __tablename__ = "reservations"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        nullable=False,
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    phone: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
    )

    date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )

    time: Mapped[time] = mapped_column(
        Time,
        nullable=False,
    )

    guests: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=ReservationStatus.PENDING.value,
        index=True,
    )

    canceled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    __table_args__ = (
        Index("ix_reservations_date_time", "date", "time"),
        Index("ix_reservations_status_date", "status", "date"),
        Index("ix_reservations_phone_date", "phone", "date"),
    )

    def __repr__(self) -> str:
        """String representation of Reservation."""
        return (
            f"<Reservation(id={self.id}, name='{self.name}', "
            f"date={self.date}, time={self.time}, guests={self.guests}, "
            f"status='{self.status}')>"
        )


class CallSession(Base):
    """Call session table model for storing call state."""

    __tablename__ = "call_sessions"

    call_id: Mapped[str] = mapped_column(
        String(100),
        primary_key=True,
        nullable=False,
    )

    phone_number: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
    )

    intent: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=CallIntent.UNKNOWN.value,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=CallStatus.INITIATED.value,
        index=True,
    )

    state_json: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )

    current_step: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )

    error_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default="now()",
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default="now()",
        onupdate=datetime.utcnow,
    )

    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    __table_args__ = (
        Index("ix_call_sessions_phone_started", "phone_number", "started_at"),
        Index("ix_call_sessions_status_started", "status", "started_at"),
    )

    def __repr__(self) -> str:
        """String representation of CallSession."""
        return (
            f"<CallSession(call_id='{self.call_id}', "
            f"phone='{self.phone_number}', intent='{self.intent}', "
            f"status='{self.status}')>"
        )


class AuditLog(Base):
    """Audit log table for tracking all actions."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    action: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )

    entity_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )

    entity_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    user_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )

    metadata: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )

    ip_address: Mapped[Optional[str]] = mapped_column(
        String(45),  # IPv6 max length
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default="now()",
        index=True,
    )

    __table_args__ = (
        Index("ix_audit_log_entity", "entity_type", "entity_id"),
        Index("ix_audit_log_action_created", "action", "created_at"),
        Index("ix_audit_log_user_created", "user_id", "created_at"),
    )

    def __repr__(self) -> str:
        """String representation of AuditLog."""
        return (
            f"<AuditLog(id={self.id}, action='{self.action}', "
            f"entity_type='{self.entity_type}', entity_id='{self.entity_id}')>"
        )
