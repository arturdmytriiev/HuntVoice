"""Test script to verify database and domain models setup."""

import asyncio
from datetime import date, time, datetime

# Test imports
print("Testing imports...")

# Domain layer
from domain.enums import (
    ReservationStatus,
    CallIntent,
    CallStatus,
    AuditAction,
    DayOfWeek,
    TimeSlot,
)
from domain.models import (
    ReservationCreate,
    ReservationRecord,
    AvailabilityQuery,
    CallStateData,
    CallSessionCreate,
    AuditLogCreate,
)

# Database layer
from db.base import Base, TimestampMixin
from db.models_sqlalchemy import Reservation, CallSession, AuditLog
from db.session import AsyncSessionLocal, init_db

print("✓ All imports successful!")


def test_enums():
    """Test enum creation."""
    print("\nTesting enums...")
    assert ReservationStatus.PENDING == "pending"
    assert CallIntent.MAKE_RESERVATION == "make_reservation"
    assert CallStatus.INITIATED == "initiated"
    assert AuditAction.RESERVATION_CREATED == "reservation_created"
    print("✓ Enums working correctly!")


def test_pydantic_models():
    """Test Pydantic model creation."""
    print("\nTesting Pydantic models...")

    # Test ReservationCreate
    reservation = ReservationCreate(
        name="John Doe",
        phone="+1234567890",
        date=date(2024, 12, 31),
        time=time(19, 0),
        guests=4,
        notes="Window seat please",
    )
    assert reservation.name == "John Doe"
    assert reservation.guests == 4
    print("  ✓ ReservationCreate model")

    # Test CallSessionCreate
    call = CallSessionCreate(
        call_id="call_123",
        phone_number="+1234567890",
        intent=CallIntent.MAKE_RESERVATION,
        status=CallStatus.INITIATED,
    )
    assert call.call_id == "call_123"
    print("  ✓ CallSessionCreate model")

    # Test AuditLogCreate
    audit = AuditLogCreate(
        action=AuditAction.RESERVATION_CREATED,
        entity_type="reservation",
        entity_id="uuid-here",
        metadata={"source": "test"},
    )
    assert audit.action == AuditAction.RESERVATION_CREATED
    print("  ✓ AuditLogCreate model")

    print("✓ All Pydantic models working correctly!")


def test_sqlalchemy_models():
    """Test SQLAlchemy model structure."""
    print("\nTesting SQLAlchemy models...")

    # Check table names
    assert Reservation.__tablename__ == "reservations"
    assert CallSession.__tablename__ == "call_sessions"
    assert AuditLog.__tablename__ == "audit_log"
    print("  ✓ Table names correct")

    # Check model has required columns
    reservation_columns = [c.name for c in Reservation.__table__.columns]
    assert "id" in reservation_columns
    assert "name" in reservation_columns
    assert "phone" in reservation_columns
    assert "date" in reservation_columns
    assert "time" in reservation_columns
    assert "status" in reservation_columns
    print("  ✓ Reservation columns correct")

    call_columns = [c.name for c in CallSession.__table__.columns]
    assert "call_id" in call_columns
    assert "state_json" in call_columns
    assert "status" in call_columns
    print("  ✓ CallSession columns correct")

    audit_columns = [c.name for c in AuditLog.__table__.columns]
    assert "id" in audit_columns
    assert "action" in audit_columns
    assert "entity_type" in audit_columns
    assert "metadata" in audit_columns
    print("  ✓ AuditLog columns correct")

    print("✓ All SQLAlchemy models structured correctly!")


async def test_session():
    """Test async session creation."""
    print("\nTesting async session...")
    async with AsyncSessionLocal() as session:
        assert session is not None
        print("✓ Async session created successfully!")


def main():
    """Run all tests."""
    print("=" * 60)
    print("HuntVoice Database Layer Setup Verification")
    print("=" * 60)

    test_enums()
    test_pydantic_models()
    test_sqlalchemy_models()
    asyncio.run(test_session())

    print("\n" + "=" * 60)
    print("✓ All tests passed! Setup is correct.")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Set up PostgreSQL database")
    print("2. Configure DATABASE_URL in .env file")
    print("3. Run: alembic -c db/alembic.ini revision --autogenerate -m 'Initial'")
    print("4. Run: alembic -c db/alembic.ini upgrade head")


if __name__ == "__main__":
    main()
