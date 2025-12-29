"""
Reservation Service for managing restaurant reservations.
Handles reservation creation, cancellation, conflict checking, and audit logging.
"""
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any, Tuple
from pathlib import Path
from dataclasses import dataclass, asdict
from enum import Enum

from core.utils_datetime import (
    get_current_datetime,
    is_valid_reservation_time,
    format_datetime_russian,
    TIMEZONE
)


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ReservationStatus(Enum):
    """Reservation status enumeration."""
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    NO_SHOW = "no_show"


@dataclass
class Reservation:
    """Reservation data class."""
    id: str
    customer_name: str
    customer_phone: str
    datetime: datetime
    party_size: int
    status: str
    special_requests: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    table_number: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with datetime serialization."""
        data = asdict(self)
        # Convert datetime objects to ISO strings
        if self.datetime:
            data['datetime'] = self.datetime.isoformat()
        if self.created_at:
            data['created_at'] = self.created_at.isoformat()
        if self.updated_at:
            data['updated_at'] = self.updated_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Reservation':
        """Create Reservation from dictionary."""
        # Parse datetime strings
        if isinstance(data.get('datetime'), str):
            data['datetime'] = datetime.fromisoformat(data['datetime'])
        if isinstance(data.get('created_at'), str):
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        if isinstance(data.get('updated_at'), str):
            data['updated_at'] = datetime.fromisoformat(data['updated_at'])

        return cls(**data)


class ReservationService:
    """Service for managing restaurant reservations."""

    # Restaurant capacity settings
    MAX_PARTY_SIZE = 12
    TABLES_AVAILABLE = 20
    MAX_RESERVATIONS_PER_SLOT = 15  # Max concurrent reservations per time slot
    SLOT_DURATION_MINUTES = 120  # Standard reservation duration

    def __init__(self, data_dir: Optional[str] = None):
        """
        Initialize ReservationService.

        Args:
            data_dir: Directory for storing reservation data
        """
        if data_dir is None:
            # Default to data/ directory relative to project root
            project_root = Path(__file__).parent.parent
            data_dir = project_root / "data"

        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)

        self.reservations_file = self.data_dir / "reservations.json"
        self.audit_log_file = self.data_dir / "audit_log.json"

        self.reservations: Dict[str, Reservation] = {}
        self._load_reservations()

    def _load_reservations(self) -> None:
        """Load reservations from file."""
        if self.reservations_file.exists():
            try:
                with open(self.reservations_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.reservations = {
                        res_id: Reservation.from_dict(res_data)
                        for res_id, res_data in data.items()
                    }
                logger.info(f"Loaded {len(self.reservations)} reservations")
            except Exception as e:
                logger.error(f"Error loading reservations: {e}")
                self.reservations = {}
        else:
            self.reservations = {}

    def _save_reservations(self) -> None:
        """Save reservations to file."""
        try:
            data = {
                res_id: reservation.to_dict()
                for res_id, reservation in self.reservations.items()
            }
            with open(self.reservations_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving reservations: {e}")
            raise

    def _log_audit(
        self,
        action: str,
        reservation_id: str,
        details: Optional[Dict[str, Any]] = None,
        user: str = "system"
    ) -> None:
        """
        Log action to audit log.

        Args:
            action: Action performed (e.g., 'create', 'cancel', 'update')
            reservation_id: ID of affected reservation
            details: Additional details about the action
            user: User who performed the action
        """
        log_entry = {
            'timestamp': get_current_datetime().isoformat(),
            'action': action,
            'reservation_id': reservation_id,
            'user': user,
            'details': details or {}
        }

        try:
            # Load existing audit log
            audit_log = []
            if self.audit_log_file.exists():
                with open(self.audit_log_file, 'r', encoding='utf-8') as f:
                    audit_log = json.load(f)

            # Append new entry
            audit_log.append(log_entry)

            # Save updated log
            with open(self.audit_log_file, 'w', encoding='utf-8') as f:
                json.dump(audit_log, f, indent=2, ensure_ascii=False)

            logger.info(f"Audit log: {action} for reservation {reservation_id}")
        except Exception as e:
            logger.error(f"Error writing audit log: {e}")

    def _generate_reservation_id(self) -> str:
        """Generate unique reservation ID."""
        timestamp = get_current_datetime().strftime('%Y%m%d%H%M%S')
        count = len(self.reservations)
        return f"RES{timestamp}{count:04d}"

    def _check_conflicts(
        self,
        reservation_datetime: datetime,
        party_size: int,
        exclude_reservation_id: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Check for reservation conflicts.

        Args:
            reservation_datetime: Desired reservation time
            party_size: Number of guests
            exclude_reservation_id: Reservation ID to exclude from check (for updates)

        Returns:
            Tuple of (has_conflict, conflict_reason)
        """
        # Check if time is valid
        if not is_valid_reservation_time(reservation_datetime):
            return True, "Время не подходит для бронирования"

        # Check party size
        if party_size > self.MAX_PARTY_SIZE:
            return True, f"Максимальный размер группы: {self.MAX_PARTY_SIZE} человек"

        if party_size < 1:
            return True, "Размер группы должен быть не менее 1 человека"

        # Define time slot boundaries
        slot_start = reservation_datetime
        slot_end = reservation_datetime + timedelta(minutes=self.SLOT_DURATION_MINUTES)

        # Count overlapping reservations
        overlapping_reservations = 0
        total_guests_in_slot = 0

        for res_id, reservation in self.reservations.items():
            # Skip excluded reservation and cancelled reservations
            if res_id == exclude_reservation_id:
                continue
            if reservation.status == ReservationStatus.CANCELLED.value:
                continue

            # Check if this reservation overlaps with the time slot
            res_start = reservation.datetime
            res_end = res_start + timedelta(minutes=self.SLOT_DURATION_MINUTES)

            # Check for overlap
            if res_start < slot_end and res_end > slot_start:
                overlapping_reservations += 1
                total_guests_in_slot += reservation.party_size

        # Check capacity constraints
        if overlapping_reservations >= self.MAX_RESERVATIONS_PER_SLOT:
            return True, "На это время все столики заняты"

        # Check if we can accommodate the party size
        if total_guests_in_slot + party_size > self.TABLES_AVAILABLE * 6:  # Assume 6 seats per table
            return True, "Недостаточно свободных мест на это время"

        return False, None

    def create_reservation(
        self,
        customer_name: str,
        customer_phone: str,
        reservation_datetime: datetime,
        party_size: int,
        special_requests: Optional[str] = None
    ) -> Tuple[bool, Optional[Reservation], Optional[str]]:
        """
        Create a new reservation.

        Args:
            customer_name: Customer's name
            customer_phone: Customer's phone number
            reservation_datetime: Desired reservation time
            party_size: Number of guests
            special_requests: Optional special requests

        Returns:
            Tuple of (success, reservation, error_message)
        """
        # Check for conflicts
        has_conflict, conflict_reason = self._check_conflicts(
            reservation_datetime, party_size
        )

        if has_conflict:
            logger.warning(f"Reservation conflict: {conflict_reason}")
            return False, None, conflict_reason

        # Create reservation
        reservation_id = self._generate_reservation_id()
        current_time = get_current_datetime()

        reservation = Reservation(
            id=reservation_id,
            customer_name=customer_name,
            customer_phone=customer_phone,
            datetime=reservation_datetime,
            party_size=party_size,
            status=ReservationStatus.CONFIRMED.value,
            special_requests=special_requests,
            created_at=current_time,
            updated_at=current_time
        )

        # Save reservation
        self.reservations[reservation_id] = reservation
        self._save_reservations()

        # Log to audit
        self._log_audit(
            action='create',
            reservation_id=reservation_id,
            details={
                'customer_name': customer_name,
                'datetime': reservation_datetime.isoformat(),
                'party_size': party_size
            }
        )

        logger.info(f"Created reservation {reservation_id} for {customer_name}")
        return True, reservation, None

    def cancel_reservation(
        self,
        reservation_id: str,
        reason: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Cancel a reservation.

        Args:
            reservation_id: ID of reservation to cancel
            reason: Optional cancellation reason

        Returns:
            Tuple of (success, error_message)
        """
        if reservation_id not in self.reservations:
            return False, "Бронирование не найдено"

        reservation = self.reservations[reservation_id]

        if reservation.status == ReservationStatus.CANCELLED.value:
            return False, "Бронирование уже отменено"

        # Update status
        reservation.status = ReservationStatus.CANCELLED.value
        reservation.updated_at = get_current_datetime()

        self._save_reservations()

        # Log to audit
        self._log_audit(
            action='cancel',
            reservation_id=reservation_id,
            details={'reason': reason or 'No reason provided'}
        )

        logger.info(f"Cancelled reservation {reservation_id}")
        return True, None

    def get_reservation(self, reservation_id: str) -> Optional[Reservation]:
        """
        Get reservation by ID.

        Args:
            reservation_id: Reservation ID

        Returns:
            Reservation or None if not found
        """
        return self.reservations.get(reservation_id)

    def find_reservations(
        self,
        customer_phone: Optional[str] = None,
        customer_name: Optional[str] = None,
        date: Optional[datetime] = None,
        status: Optional[str] = None
    ) -> List[Reservation]:
        """
        Find reservations by criteria.

        Args:
            customer_phone: Filter by phone number
            customer_name: Filter by customer name
            date: Filter by reservation date
            status: Filter by status

        Returns:
            List of matching reservations
        """
        results = []

        for reservation in self.reservations.values():
            # Filter by phone
            if customer_phone and reservation.customer_phone != customer_phone:
                continue

            # Filter by name (partial match)
            if customer_name and customer_name.lower() not in reservation.customer_name.lower():
                continue

            # Filter by date (same day)
            if date and reservation.datetime.date() != date.date():
                continue

            # Filter by status
            if status and reservation.status != status:
                continue

            results.append(reservation)

        return results

    def find_availability(
        self,
        date: datetime,
        party_size: int,
        duration_hours: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Find available time slots for a given date and party size.

        Args:
            date: Desired date
            party_size: Number of guests
            duration_hours: Search window in hours from restaurant opening

        Returns:
            List of available time slots with datetime and capacity info
        """
        available_slots = []

        # Restaurant hours: 11:00 - 23:00
        # Check slots every 30 minutes
        start_hour = 11
        end_hour = 21  # Last reservation at 21:00 (gives 2 hours until closing)

        # Ensure date is in correct timezone
        if date.tzinfo is None:
            date = TIMEZONE.localize(date)
        else:
            date = date.astimezone(TIMEZONE)

        # Start from the given date at opening time
        check_date = date.replace(hour=start_hour, minute=0, second=0, microsecond=0)

        # Limit search to specified duration
        end_search = check_date + timedelta(hours=duration_hours)

        while check_date.hour < end_hour:
            # Check if this slot is available
            has_conflict, _ = self._check_conflicts(check_date, party_size)

            if not has_conflict and is_valid_reservation_time(check_date):
                available_slots.append({
                    'datetime': check_date,
                    'formatted': format_datetime_russian(check_date),
                    'time': check_date.strftime('%H:%M')
                })

            # Move to next slot (30 minutes)
            check_date += timedelta(minutes=30)

            # Stop if we've exceeded the search duration
            if check_date > end_search:
                break

        return available_slots

    def get_reservations_for_date(self, date: datetime) -> List[Reservation]:
        """
        Get all reservations for a specific date.

        Args:
            date: Date to query

        Returns:
            List of reservations for that date
        """
        return self.find_reservations(date=date)

    def update_reservation(
        self,
        reservation_id: str,
        **kwargs
    ) -> Tuple[bool, Optional[str]]:
        """
        Update reservation details.

        Args:
            reservation_id: ID of reservation to update
            **kwargs: Fields to update (party_size, datetime, special_requests, etc.)

        Returns:
            Tuple of (success, error_message)
        """
        if reservation_id not in self.reservations:
            return False, "Бронирование не найдено"

        reservation = self.reservations[reservation_id]

        # Check for datetime/party_size conflicts if being updated
        if 'datetime' in kwargs or 'party_size' in kwargs:
            new_datetime = kwargs.get('datetime', reservation.datetime)
            new_party_size = kwargs.get('party_size', reservation.party_size)

            has_conflict, conflict_reason = self._check_conflicts(
                new_datetime, new_party_size, exclude_reservation_id=reservation_id
            )

            if has_conflict:
                return False, conflict_reason

        # Update fields
        for key, value in kwargs.items():
            if hasattr(reservation, key):
                setattr(reservation, key, value)

        reservation.updated_at = get_current_datetime()
        self._save_reservations()

        # Log to audit
        self._log_audit(
            action='update',
            reservation_id=reservation_id,
            details=kwargs
        )

        logger.info(f"Updated reservation {reservation_id}")
        return True, None

    def get_audit_log(
        self,
        reservation_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Retrieve audit log entries.

        Args:
            reservation_id: Filter by specific reservation ID
            limit: Maximum number of entries to return

        Returns:
            List of audit log entries
        """
        if not self.audit_log_file.exists():
            return []

        try:
            with open(self.audit_log_file, 'r', encoding='utf-8') as f:
                audit_log = json.load(f)

            # Filter by reservation_id if provided
            if reservation_id:
                audit_log = [
                    entry for entry in audit_log
                    if entry.get('reservation_id') == reservation_id
                ]

            # Return most recent entries
            return audit_log[-limit:]
        except Exception as e:
            logger.error(f"Error reading audit log: {e}")
            return []


# Singleton instance
_reservation_service_instance: Optional[ReservationService] = None


def get_reservation_service(data_dir: Optional[str] = None) -> ReservationService:
    """
    Get or create ReservationService singleton instance.

    Args:
        data_dir: Optional data directory path

    Returns:
        ReservationService instance
    """
    global _reservation_service_instance

    if _reservation_service_instance is None:
        _reservation_service_instance = ReservationService(data_dir)

    return _reservation_service_instance
