"""Domain enums for Voice AI Restaurant Bot."""

from enum import Enum


class ReservationStatus(str, Enum):
    """Reservation status enumeration."""

    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELED = "canceled"
    COMPLETED = "completed"
    NO_SHOW = "no_show"


class CallIntent(str, Enum):
    """Call intent enumeration."""

    MAKE_RESERVATION = "make_reservation"
    CANCEL_RESERVATION = "cancel_reservation"
    MODIFY_RESERVATION = "modify_reservation"
    CHECK_AVAILABILITY = "check_availability"
    GENERAL_INQUIRY = "general_inquiry"
    UNKNOWN = "unknown"


class CallStatus(str, Enum):
    """Call session status."""

    INITIATED = "initiated"
    IN_PROGRESS = "in_progress"
    COLLECTING_INFO = "collecting_info"
    CONFIRMING = "confirming"
    COMPLETED = "completed"
    FAILED = "failed"
    ABANDONED = "abandoned"


class AuditAction(str, Enum):
    """Audit log action types."""

    RESERVATION_CREATED = "reservation_created"
    RESERVATION_CONFIRMED = "reservation_confirmed"
    RESERVATION_CANCELED = "reservation_canceled"
    RESERVATION_MODIFIED = "reservation_modified"
    RESERVATION_NO_SHOW = "reservation_no_show"
    CALL_INITIATED = "call_initiated"
    CALL_COMPLETED = "call_completed"
    CALL_FAILED = "call_failed"


class DayOfWeek(str, Enum):
    """Days of the week."""

    MONDAY = "monday"
    TUESDAY = "tuesday"
    WEDNESDAY = "wednesday"
    THURSDAY = "thursday"
    FRIDAY = "friday"
    SATURDAY = "saturday"
    SUNDAY = "sunday"


class TimeSlot(str, Enum):
    """Common time slot categories."""

    BREAKFAST = "breakfast"  # 7:00 - 11:00
    LUNCH = "lunch"          # 11:00 - 15:00
    DINNER = "dinner"        # 17:00 - 22:00
    LATE_NIGHT = "late_night"  # 22:00 - 00:00
