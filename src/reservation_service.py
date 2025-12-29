"""Reservation service for managing restaurant reservations."""
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from src.models import Reservation


class ReservationConflictError(Exception):
    """Raised when a reservation conflicts with an existing one."""
    pass


class ReservationNotFoundError(Exception):
    """Raised when a reservation is not found."""
    pass


class ReservationService:
    """Service for managing restaurant reservations."""

    def __init__(self, db_session: Session, max_capacity: int = 50, table_turnover_minutes: int = 120):
        """
        Initialize the reservation service.

        Args:
            db_session: SQLAlchemy database session
            max_capacity: Maximum number of guests the restaurant can handle
            table_turnover_minutes: How long a table is occupied (default 2 hours)
        """
        self.db = db_session
        self.max_capacity = max_capacity
        self.table_turnover_minutes = table_turnover_minutes

    def create_reservation(
        self,
        customer_name: str,
        phone_number: str,
        party_size: int,
        reservation_time: datetime,
        notes: Optional[str] = None,
    ) -> Reservation:
        """
        Create a new reservation.

        Args:
            customer_name: Name of the customer
            phone_number: Customer's phone number
            party_size: Number of people in the party
            reservation_time: Desired reservation time
            notes: Optional notes for the reservation

        Returns:
            Created Reservation object

        Raises:
            ReservationConflictError: If the reservation conflicts with capacity
        """
        # Check for conflicts
        if not self.is_time_available(reservation_time, party_size):
            raise ReservationConflictError(
                f"Cannot accommodate party of {party_size} at {reservation_time}. "
                f"Restaurant is at or near capacity."
            )

        reservation = Reservation(
            customer_name=customer_name,
            phone_number=phone_number,
            party_size=party_size,
            reservation_time=reservation_time,
            notes=notes,
            cancelled=False,
        )

        self.db.add(reservation)
        self.db.commit()
        self.db.refresh(reservation)

        return reservation

    def get_reservation(self, reservation_id: int) -> Reservation:
        """
        Get a reservation by ID.

        Args:
            reservation_id: ID of the reservation

        Returns:
            Reservation object

        Raises:
            ReservationNotFoundError: If reservation not found
        """
        reservation = self.db.query(Reservation).filter(Reservation.id == reservation_id).first()

        if not reservation:
            raise ReservationNotFoundError(f"Reservation {reservation_id} not found")

        return reservation

    def update_reservation(
        self,
        reservation_id: int,
        customer_name: Optional[str] = None,
        phone_number: Optional[str] = None,
        party_size: Optional[int] = None,
        reservation_time: Optional[datetime] = None,
        notes: Optional[str] = None,
    ) -> Reservation:
        """
        Update an existing reservation.

        Args:
            reservation_id: ID of the reservation to update
            customer_name: New customer name (optional)
            phone_number: New phone number (optional)
            party_size: New party size (optional)
            reservation_time: New reservation time (optional)
            notes: New notes (optional)

        Returns:
            Updated Reservation object

        Raises:
            ReservationNotFoundError: If reservation not found
            ReservationConflictError: If update creates a conflict
        """
        reservation = self.get_reservation(reservation_id)

        # If changing time or party size, check availability
        new_time = reservation_time if reservation_time else reservation.reservation_time
        new_size = party_size if party_size else reservation.party_size

        if (reservation_time or party_size) and not self.is_time_available(
            new_time, new_size, exclude_reservation_id=reservation_id
        ):
            raise ReservationConflictError(
                f"Cannot update reservation: party of {new_size} at {new_time} would exceed capacity"
            )

        # Update fields
        if customer_name:
            reservation.customer_name = customer_name
        if phone_number:
            reservation.phone_number = phone_number
        if party_size:
            reservation.party_size = party_size
        if reservation_time:
            reservation.reservation_time = reservation_time
        if notes is not None:
            reservation.notes = notes

        reservation.updated_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(reservation)

        return reservation

    def cancel_reservation(self, reservation_id: int) -> Reservation:
        """
        Cancel a reservation.

        Args:
            reservation_id: ID of the reservation to cancel

        Returns:
            Cancelled Reservation object

        Raises:
            ReservationNotFoundError: If reservation not found
        """
        reservation = self.get_reservation(reservation_id)
        reservation.cancelled = True
        reservation.updated_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(reservation)

        return reservation

    def delete_reservation(self, reservation_id: int) -> None:
        """
        Permanently delete a reservation.

        Args:
            reservation_id: ID of the reservation to delete

        Raises:
            ReservationNotFoundError: If reservation not found
        """
        reservation = self.get_reservation(reservation_id)
        self.db.delete(reservation)
        self.db.commit()

    def list_reservations(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        include_cancelled: bool = False,
    ) -> List[Reservation]:
        """
        List reservations within a time range.

        Args:
            start_time: Start of time range (optional)
            end_time: End of time range (optional)
            include_cancelled: Whether to include cancelled reservations

        Returns:
            List of Reservation objects
        """
        query = self.db.query(Reservation)

        if not include_cancelled:
            query = query.filter(Reservation.cancelled == False)

        if start_time:
            query = query.filter(Reservation.reservation_time >= start_time)

        if end_time:
            query = query.filter(Reservation.reservation_time <= end_time)

        return query.order_by(Reservation.reservation_time).all()

    def is_time_available(
        self,
        reservation_time: datetime,
        party_size: int,
        exclude_reservation_id: Optional[int] = None,
    ) -> bool:
        """
        Check if a time slot is available for a given party size.

        Args:
            reservation_time: Desired reservation time
            party_size: Size of the party
            exclude_reservation_id: Reservation ID to exclude from conflict check (for updates)

        Returns:
            True if time is available, False otherwise
        """
        # Calculate the time window that overlaps with this reservation
        turnover_delta = timedelta(minutes=self.table_turnover_minutes)
        window_start = reservation_time - turnover_delta
        window_end = reservation_time + turnover_delta

        # Find all active reservations that overlap with this time window
        query = self.db.query(Reservation).filter(
            and_(
                Reservation.cancelled == False,
                Reservation.reservation_time >= window_start,
                Reservation.reservation_time < window_end,
            )
        )

        if exclude_reservation_id:
            query = query.filter(Reservation.id != exclude_reservation_id)

        overlapping_reservations = query.all()

        # Calculate total capacity needed during this time
        current_capacity = sum(r.party_size for r in overlapping_reservations)

        return (current_capacity + party_size) <= self.max_capacity

    def find_available_slots(
        self,
        date: datetime,
        party_size: int,
        start_hour: int = 17,
        end_hour: int = 22,
        slot_interval_minutes: int = 30,
    ) -> List[datetime]:
        """
        Find available time slots for a given date and party size.

        Args:
            date: The date to search (time will be ignored)
            party_size: Size of the party
            start_hour: Start of dining hours (default 5 PM)
            end_hour: End of dining hours (default 10 PM)
            slot_interval_minutes: Minutes between slots (default 30)

        Returns:
            List of available datetime slots
        """
        available_slots = []

        # Create base date at midnight
        base_date = date.replace(hour=0, minute=0, second=0, microsecond=0)

        # Generate time slots
        current_time = base_date.replace(hour=start_hour)
        end_time = base_date.replace(hour=end_hour)

        while current_time <= end_time:
            if self.is_time_available(current_time, party_size):
                available_slots.append(current_time)

            current_time += timedelta(minutes=slot_interval_minutes)

        return available_slots

    def search_by_phone(self, phone_number: str) -> List[Reservation]:
        """
        Search for reservations by phone number.

        Args:
            phone_number: Phone number to search for

        Returns:
            List of Reservation objects
        """
        return (
            self.db.query(Reservation)
            .filter(Reservation.phone_number == phone_number)
            .order_by(Reservation.reservation_time.desc())
            .all()
        )

    def search_by_name(self, customer_name: str) -> List[Reservation]:
        """
        Search for reservations by customer name (case-insensitive partial match).

        Args:
            customer_name: Customer name to search for

        Returns:
            List of Reservation objects
        """
        return (
            self.db.query(Reservation)
            .filter(Reservation.customer_name.ilike(f"%{customer_name}%"))
            .order_by(Reservation.reservation_time.desc())
            .all()
        )
