"""Unit tests for the reservation service."""
import pytest
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from src.reservation_service import (
    ReservationService,
    ReservationConflictError,
    ReservationNotFoundError,
)
from src.models import Reservation


@pytest.mark.unit
class TestReservationCRUD:
    """Test CRUD operations for reservations."""

    def test_create_reservation_success(self, reservation_service, sample_reservation_data):
        """Test creating a reservation successfully."""
        reservation = reservation_service.create_reservation(**sample_reservation_data)

        assert reservation.id is not None
        assert reservation.customer_name == sample_reservation_data["customer_name"]
        assert reservation.phone_number == sample_reservation_data["phone_number"]
        assert reservation.party_size == sample_reservation_data["party_size"]
        assert reservation.reservation_time == sample_reservation_data["reservation_time"]
        assert reservation.notes == sample_reservation_data["notes"]
        assert reservation.cancelled is False
        assert reservation.created_at is not None

    def test_create_reservation_minimal(self, reservation_service, base_time):
        """Test creating a reservation with minimal required fields."""
        reservation = reservation_service.create_reservation(
            customer_name="Jane Smith",
            phone_number="9876543210",
            party_size=2,
            reservation_time=base_time.replace(hour=19),
        )

        assert reservation.id is not None
        assert reservation.customer_name == "Jane Smith"
        assert reservation.notes is None

    def test_get_reservation_success(self, create_sample_reservation):
        """Test retrieving a reservation by ID."""
        created = create_sample_reservation()
        retrieved = create_sample_reservation.__self__.get_reservation(created.id)

        assert retrieved.id == created.id
        assert retrieved.customer_name == created.customer_name
        assert retrieved.phone_number == created.phone_number

    def test_get_reservation_not_found(self, reservation_service):
        """Test retrieving a non-existent reservation raises error."""
        with pytest.raises(ReservationNotFoundError, match="Reservation 999 not found"):
            reservation_service.get_reservation(999)

    def test_update_reservation_name(self, create_sample_reservation):
        """Test updating customer name."""
        reservation = create_sample_reservation()
        service = create_sample_reservation.__self__

        updated = service.update_reservation(
            reservation.id,
            customer_name="Updated Name",
        )

        assert updated.customer_name == "Updated Name"
        assert updated.phone_number == reservation.phone_number  # Unchanged
        assert updated.updated_at > reservation.updated_at

    def test_update_reservation_phone(self, create_sample_reservation):
        """Test updating phone number."""
        reservation = create_sample_reservation()
        service = create_sample_reservation.__self__

        updated = service.update_reservation(
            reservation.id,
            phone_number="5555555555",
        )

        assert updated.phone_number == "5555555555"

    def test_update_reservation_party_size(self, create_sample_reservation, base_time):
        """Test updating party size."""
        reservation = create_sample_reservation(party_size=2)
        service = create_sample_reservation.__self__

        updated = service.update_reservation(
            reservation.id,
            party_size=6,
        )

        assert updated.party_size == 6

    def test_update_reservation_time(self, create_sample_reservation, base_time):
        """Test updating reservation time."""
        reservation = create_sample_reservation()
        service = create_sample_reservation.__self__

        new_time = base_time.replace(hour=20, minute=30)
        updated = service.update_reservation(
            reservation.id,
            reservation_time=new_time,
        )

        assert updated.reservation_time == new_time

    def test_update_reservation_not_found(self, reservation_service):
        """Test updating a non-existent reservation raises error."""
        with pytest.raises(ReservationNotFoundError):
            reservation_service.update_reservation(999, customer_name="Test")

    def test_update_reservation_multiple_fields(self, create_sample_reservation, base_time):
        """Test updating multiple fields at once."""
        reservation = create_sample_reservation()
        service = create_sample_reservation.__self__

        new_time = base_time.replace(hour=21)
        updated = service.update_reservation(
            reservation.id,
            customer_name="New Name",
            party_size=8,
            reservation_time=new_time,
            notes="Updated notes",
        )

        assert updated.customer_name == "New Name"
        assert updated.party_size == 8
        assert updated.reservation_time == new_time
        assert updated.notes == "Updated notes"

    def test_cancel_reservation(self, create_sample_reservation):
        """Test cancelling a reservation."""
        reservation = create_sample_reservation()
        service = create_sample_reservation.__self__

        cancelled = service.cancel_reservation(reservation.id)

        assert cancelled.cancelled is True
        assert cancelled.updated_at > reservation.updated_at

    def test_cancel_reservation_not_found(self, reservation_service):
        """Test cancelling a non-existent reservation raises error."""
        with pytest.raises(ReservationNotFoundError):
            reservation_service.cancel_reservation(999)

    def test_delete_reservation(self, create_sample_reservation):
        """Test permanently deleting a reservation."""
        reservation = create_sample_reservation()
        service = create_sample_reservation.__self__

        service.delete_reservation(reservation.id)

        with pytest.raises(ReservationNotFoundError):
            service.get_reservation(reservation.id)

    def test_delete_reservation_not_found(self, reservation_service):
        """Test deleting a non-existent reservation raises error."""
        with pytest.raises(ReservationNotFoundError):
            reservation_service.delete_reservation(999)


@pytest.mark.unit
class TestReservationListing:
    """Test listing and searching reservations."""

    def test_list_reservations_empty(self, reservation_service):
        """Test listing reservations when database is empty."""
        reservations = reservation_service.list_reservations()
        assert len(reservations) == 0

    def test_list_all_reservations(self, populate_reservations):
        """Test listing all reservations."""
        created = populate_reservations(5)
        service = populate_reservations.__self__

        reservations = service.list_reservations()

        assert len(reservations) == 5
        assert all(not r.cancelled for r in reservations)

    def test_list_reservations_exclude_cancelled(self, populate_reservations):
        """Test that cancelled reservations are excluded by default."""
        created = populate_reservations(3)
        service = populate_reservations.__self__

        # Cancel one reservation
        service.cancel_reservation(created[1].id)

        reservations = service.list_reservations(include_cancelled=False)

        assert len(reservations) == 2
        assert all(not r.cancelled for r in reservations)

    def test_list_reservations_include_cancelled(self, populate_reservations):
        """Test including cancelled reservations."""
        created = populate_reservations(3)
        service = populate_reservations.__self__

        # Cancel one reservation
        service.cancel_reservation(created[1].id)

        reservations = service.list_reservations(include_cancelled=True)

        assert len(reservations) == 3
        assert sum(r.cancelled for r in reservations) == 1

    def test_list_reservations_time_range(self, reservation_service, base_time):
        """Test filtering reservations by time range."""
        # Create reservations at different times
        reservation_service.create_reservation(
            customer_name="Early",
            phone_number="1111111111",
            party_size=2,
            reservation_time=base_time.replace(hour=17),
        )
        reservation_service.create_reservation(
            customer_name="Middle",
            phone_number="2222222222",
            party_size=2,
            reservation_time=base_time.replace(hour=19),
        )
        reservation_service.create_reservation(
            customer_name="Late",
            phone_number="3333333333",
            party_size=2,
            reservation_time=base_time.replace(hour=21),
        )

        # Query for middle time range
        start = base_time.replace(hour=18)
        end = base_time.replace(hour=20)
        reservations = reservation_service.list_reservations(start_time=start, end_time=end)

        assert len(reservations) == 1
        assert reservations[0].customer_name == "Middle"

    def test_list_reservations_ordered_by_time(self, reservation_service, base_time):
        """Test that reservations are ordered by time."""
        # Create in random order
        times = [21, 17, 19, 18, 20]
        for i, hour in enumerate(times):
            reservation_service.create_reservation(
                customer_name=f"Customer {i}",
                phone_number=f"111111111{i}",
                party_size=2,
                reservation_time=base_time.replace(hour=hour),
            )

        reservations = reservation_service.list_reservations()

        # Verify they're sorted by time
        for i in range(len(reservations) - 1):
            assert reservations[i].reservation_time <= reservations[i + 1].reservation_time

    def test_search_by_phone(self, reservation_service, base_time):
        """Test searching reservations by phone number."""
        target_phone = "5551234567"

        # Create reservations with different phone numbers
        reservation_service.create_reservation(
            customer_name="Target 1",
            phone_number=target_phone,
            party_size=2,
            reservation_time=base_time.replace(hour=18),
        )
        reservation_service.create_reservation(
            customer_name="Other",
            phone_number="5559999999",
            party_size=2,
            reservation_time=base_time.replace(hour=19),
        )
        reservation_service.create_reservation(
            customer_name="Target 2",
            phone_number=target_phone,
            party_size=4,
            reservation_time=base_time.replace(hour=20),
        )

        results = reservation_service.search_by_phone(target_phone)

        assert len(results) == 2
        assert all(r.phone_number == target_phone for r in results)
        # Should be ordered by time descending
        assert results[0].customer_name == "Target 2"
        assert results[1].customer_name == "Target 1"

    def test_search_by_phone_no_results(self, reservation_service):
        """Test searching by phone with no matches."""
        results = reservation_service.search_by_phone("0000000000")
        assert len(results) == 0

    def test_search_by_name(self, reservation_service, base_time):
        """Test searching reservations by name (case-insensitive partial match)."""
        # Create reservations
        reservation_service.create_reservation(
            customer_name="John Smith",
            phone_number="1111111111",
            party_size=2,
            reservation_time=base_time.replace(hour=18),
        )
        reservation_service.create_reservation(
            customer_name="Jane Doe",
            phone_number="2222222222",
            party_size=2,
            reservation_time=base_time.replace(hour=19),
        )
        reservation_service.create_reservation(
            customer_name="Johnny Walker",
            phone_number="3333333333",
            party_size=2,
            reservation_time=base_time.replace(hour=20),
        )

        # Search for "john" should match "John Smith" and "Johnny Walker"
        results = reservation_service.search_by_name("john")

        assert len(results) == 2
        names = [r.customer_name for r in results]
        assert "John Smith" in names
        assert "Johnny Walker" in names

    def test_search_by_name_case_insensitive(self, reservation_service, base_time):
        """Test that name search is case-insensitive."""
        reservation_service.create_reservation(
            customer_name="Alice Wonder",
            phone_number="1111111111",
            party_size=2,
            reservation_time=base_time.replace(hour=18),
        )

        results = reservation_service.search_by_name("ALICE")
        assert len(results) == 1

        results = reservation_service.search_by_name("wonder")
        assert len(results) == 1

    def test_search_by_name_no_results(self, reservation_service):
        """Test searching by name with no matches."""
        results = reservation_service.search_by_name("NonExistent")
        assert len(results) == 0


@pytest.mark.unit
class TestConflictDetection:
    """Test reservation conflict detection."""

    def test_create_reservation_with_conflict(self, create_sample_reservation):
        """Test that creating a conflicting reservation raises error."""
        # Create first reservation for party of 40
        first = create_sample_reservation(party_size=40)
        service = create_sample_reservation.__self__

        # Try to create overlapping reservation that would exceed capacity (50)
        with pytest.raises(ReservationConflictError, match="Cannot accommodate"):
            service.create_reservation(
                customer_name="Conflict",
                phone_number="9999999999",
                party_size=15,  # 40 + 15 = 55 > 50
                reservation_time=first.reservation_time,
            )

    def test_create_reservation_no_conflict_different_time(
        self, create_sample_reservation, base_time
    ):
        """Test that reservations at different times don't conflict."""
        # Create first reservation
        first = create_sample_reservation(
            party_size=40,
            reservation_time=base_time.replace(hour=17),
        )
        service = create_sample_reservation.__self__

        # Create second reservation 3 hours later (outside turnover window)
        second = service.create_reservation(
            customer_name="No Conflict",
            phone_number="9999999999",
            party_size=40,
            reservation_time=base_time.replace(hour=20, minute=30),
        )

        assert second.id != first.id

    def test_create_reservation_within_turnover_window(
        self, create_sample_reservation, base_time
    ):
        """Test conflict detection within table turnover window."""
        # Create first reservation for party of 30
        first = create_sample_reservation(
            party_size=30,
            reservation_time=base_time.replace(hour=18),
        )
        service = create_sample_reservation.__self__

        # Try to create reservation 1 hour later (within 2-hour turnover)
        # 30 + 25 = 55 > 50 capacity
        with pytest.raises(ReservationConflictError):
            service.create_reservation(
                customer_name="Conflict",
                phone_number="9999999999",
                party_size=25,
                reservation_time=base_time.replace(hour=19),
            )

    def test_update_reservation_with_conflict(self, reservation_service, base_time):
        """Test that updating a reservation to create conflict raises error."""
        # Create two non-conflicting reservations
        res1 = reservation_service.create_reservation(
            customer_name="First",
            phone_number="1111111111",
            party_size=30,
            reservation_time=base_time.replace(hour=18),
        )
        res2 = reservation_service.create_reservation(
            customer_name="Second",
            phone_number="2222222222",
            party_size=15,
            reservation_time=base_time.replace(hour=21),
        )

        # Try to update res2 to conflict with res1
        with pytest.raises(ReservationConflictError):
            reservation_service.update_reservation(
                res2.id,
                party_size=25,  # 30 + 25 = 55 > 50
                reservation_time=base_time.replace(hour=18, minute=30),
            )

    def test_update_reservation_no_conflict_self(self, create_sample_reservation):
        """Test that updating a reservation doesn't conflict with itself."""
        reservation = create_sample_reservation(party_size=40)
        service = create_sample_reservation.__self__

        # Should not raise conflict even though 40 + 40 > 50
        updated = service.update_reservation(
            reservation.id,
            party_size=40,  # Same size
        )

        assert updated.party_size == 40

    def test_cancelled_reservations_dont_cause_conflict(
        self, reservation_service, base_time
    ):
        """Test that cancelled reservations don't count toward capacity."""
        # Create and cancel a large reservation
        res1 = reservation_service.create_reservation(
            customer_name="Cancelled",
            phone_number="1111111111",
            party_size=45,
            reservation_time=base_time.replace(hour=19),
        )
        reservation_service.cancel_reservation(res1.id)

        # Should be able to create new reservation at same time
        res2 = reservation_service.create_reservation(
            customer_name="New",
            phone_number="2222222222",
            party_size=45,
            reservation_time=base_time.replace(hour=19),
        )

        assert res2.id is not None


@pytest.mark.unit
class TestAvailabilitySearch:
    """Test availability search functionality."""

    def test_is_time_available_empty_db(self, reservation_service, base_time):
        """Test that all times are available in empty database."""
        test_time = base_time.replace(hour=19)
        assert reservation_service.is_time_available(test_time, 4) is True
        assert reservation_service.is_time_available(test_time, 50) is True

    def test_is_time_available_with_capacity(self, reservation_service, base_time):
        """Test availability calculation with existing reservations."""
        test_time = base_time.replace(hour=19)

        # Create reservation for 30 people
        reservation_service.create_reservation(
            customer_name="First",
            phone_number="1111111111",
            party_size=30,
            reservation_time=test_time,
        )

        # 20 more should fit (30 + 20 = 50)
        assert reservation_service.is_time_available(test_time, 20) is True

        # 21 more should not fit (30 + 21 = 51 > 50)
        assert reservation_service.is_time_available(test_time, 21) is False

    def test_is_time_available_exceeds_capacity(self, reservation_service, base_time):
        """Test that requests exceeding capacity return False."""
        test_time = base_time.replace(hour=19)

        # Request for 51 people exceeds max capacity of 50
        assert reservation_service.is_time_available(test_time, 51) is False

    def test_find_available_slots_all_available(self, reservation_service, base_time):
        """Test finding available slots when all times are free."""
        date = base_time.date()
        slots = reservation_service.find_available_slots(
            base_time,
            party_size=4,
            start_hour=17,
            end_hour=20,
            slot_interval_minutes=30,
        )

        # Should have slots at 5:00, 5:30, 6:00, 6:30, 7:00, 7:30, 8:00
        assert len(slots) == 7
        assert slots[0].hour == 17
        assert slots[-1].hour == 20

    def test_find_available_slots_some_unavailable(self, reservation_service, base_time):
        """Test finding available slots when some times are booked."""
        # Book 7 PM with large party
        reservation_service.create_reservation(
            customer_name="Booked",
            phone_number="1111111111",
            party_size=48,
            reservation_time=base_time.replace(hour=19),
        )

        slots = reservation_service.find_available_slots(
            base_time,
            party_size=5,  # 48 + 5 = 53 > 50
            start_hour=17,
            end_hour=20,
            slot_interval_minutes=60,
        )

        # Should exclude times within 2-hour turnover window of 7 PM
        # Available: 5 PM, 9 PM (if we extended hours)
        # Within turnover window: 6 PM, 7 PM, 8 PM
        slot_hours = [s.hour for s in slots]
        assert 17 in slot_hours  # 5 PM available
        assert 19 not in slot_hours  # 7 PM not available

    def test_find_available_slots_custom_hours(self, reservation_service, base_time):
        """Test finding available slots with custom operating hours."""
        slots = reservation_service.find_available_slots(
            base_time,
            party_size=4,
            start_hour=11,  # Lunch starting at 11 AM
            end_hour=14,  # Until 2 PM
            slot_interval_minutes=30,
        )

        assert len(slots) == 7  # 11:00, 11:30, 12:00, 12:30, 1:00, 1:30, 2:00
        assert slots[0].hour == 11
        assert slots[-1].hour == 14

    def test_find_available_slots_different_intervals(self, reservation_service, base_time):
        """Test finding available slots with different time intervals."""
        # 15-minute intervals
        slots_15 = reservation_service.find_available_slots(
            base_time,
            party_size=4,
            start_hour=18,
            end_hour=19,
            slot_interval_minutes=15,
        )

        # Should have 18:00, 18:15, 18:30, 18:45, 19:00
        assert len(slots_15) == 5

        # 60-minute intervals
        slots_60 = reservation_service.find_available_slots(
            base_time,
            party_size=4,
            start_hour=18,
            end_hour=19,
            slot_interval_minutes=60,
        )

        # Should have 18:00, 19:00
        assert len(slots_60) == 2

    def test_find_available_slots_fully_booked(self, reservation_service, base_time):
        """Test finding available slots when fully booked."""
        # Fill all capacity for the entire time range
        for hour in range(17, 21):
            reservation_service.create_reservation(
                customer_name=f"Guest {hour}",
                phone_number=f"111111{hour:04d}",
                party_size=50,
                reservation_time=base_time.replace(hour=hour),
            )

        slots = reservation_service.find_available_slots(
            base_time,
            party_size=1,
            start_hour=17,
            end_hour=20,
        )

        # No slots should be available
        assert len(slots) == 0

    def test_find_available_slots_ignores_cancelled(self, reservation_service, base_time):
        """Test that cancelled reservations don't affect availability."""
        # Create and cancel a large reservation
        res = reservation_service.create_reservation(
            customer_name="Cancelled",
            phone_number="1111111111",
            party_size=50,
            reservation_time=base_time.replace(hour=19),
        )
        reservation_service.cancel_reservation(res.id)

        # All slots should still be available
        slots = reservation_service.find_available_slots(
            base_time,
            party_size=4,
            start_hour=18,
            end_hour=20,
        )

        # Should have slots including 7 PM
        slot_hours = [s.hour for s in slots]
        assert 19 in slot_hours
