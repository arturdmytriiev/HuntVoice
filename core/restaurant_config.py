"""
Restaurant configuration for business rules, hours, holidays, and booking policies.
Timezone-aware configuration for Europe/Bratislava.
"""

from dataclasses import dataclass, field
from datetime import date, time, datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple
from enum import Enum
import pytz

from core.utils_datetime import TIMEZONE, get_current_datetime


class DayOfWeek(Enum):
    """Days of the week."""
    MONDAY = 0
    TUESDAY = 1
    WEDNESDAY = 2
    THURSDAY = 3
    FRIDAY = 4
    SATURDAY = 5
    SUNDAY = 6


@dataclass
class TimeRange:
    """Time range with opening and closing times."""
    open_time: time
    close_time: time
    last_reservation_offset_minutes: int = 120  # How long before closing last reservation is allowed

    @property
    def last_reservation_time(self) -> time:
        """Calculate the last allowed reservation time."""
        close_dt = datetime.combine(date.today(), self.close_time)
        last_res_dt = close_dt - timedelta(minutes=self.last_reservation_offset_minutes)
        return last_res_dt.time()

    def is_time_within(self, check_time: time) -> bool:
        """Check if a time falls within this range (for reservations)."""
        return self.open_time <= check_time <= self.last_reservation_time

    def is_open_at(self, check_time: time) -> bool:
        """Check if the restaurant is open at this time."""
        return self.open_time <= check_time < self.close_time


@dataclass
class SpecialHours:
    """Special hours for a specific date (holiday, event, etc.)."""
    date: date
    time_range: Optional[TimeRange]  # None means closed
    description: str = ""

    @property
    def is_closed(self) -> bool:
        """Check if the restaurant is closed on this date."""
        return self.time_range is None


@dataclass
class BookingRules:
    """Booking rules and constraints."""
    # Time slot settings
    time_slot_granularity_minutes: int = 30  # Allowed intervals (15, 30, 60)
    default_duration_minutes: int = 90  # Default reservation duration
    min_duration_minutes: int = 60
    max_duration_minutes: int = 180

    # Lead time settings
    minimum_lead_time_minutes: int = 60  # Minimum time before reservation
    maximum_horizon_days: int = 60  # Maximum days in advance

    # Party size settings
    min_party_size: int = 1
    max_party_size: int = 20
    large_party_threshold: int = 8  # Parties >= this need special handling
    max_party_without_notes: int = 8  # Parties > this require notes

    # Capacity settings
    total_tables: int = 20
    max_capacity: int = 120  # Total restaurant capacity
    max_concurrent_reservations: int = 15
    seats_per_table: int = 6  # Average seats per table

    def is_valid_time_slot(self, reservation_time: time) -> bool:
        """Check if the time aligns with the slot granularity."""
        total_minutes = reservation_time.hour * 60 + reservation_time.minute
        return total_minutes % self.time_slot_granularity_minutes == 0

    def get_adjusted_duration_for_party(self, party_size: int) -> int:
        """Get adjusted duration based on party size."""
        if party_size >= 10:
            return min(self.default_duration_minutes + 30, self.max_duration_minutes)
        if party_size >= 6:
            return min(self.default_duration_minutes + 15, self.max_duration_minutes)
        return self.default_duration_minutes


@dataclass
class RestaurantConfig:
    """Complete restaurant configuration."""

    # Restaurant info
    name: str = "Hunt Restaurant"
    timezone: str = "Europe/Bratislava"
    phone: str = "+421123456789"

    # Regular hours by day of week
    regular_hours: Dict[DayOfWeek, TimeRange] = field(default_factory=dict)

    # Special hours (holidays, events)
    special_hours: Dict[date, SpecialHours] = field(default_factory=dict)

    # Booking rules
    booking_rules: BookingRules = field(default_factory=BookingRules)

    # Holiday dates that are closed
    closed_dates: Set[date] = field(default_factory=set)

    def __post_init__(self):
        """Initialize default regular hours if not provided."""
        if not self.regular_hours:
            # Default: Open 11:00-23:00 every day
            default_hours = TimeRange(
                open_time=time(11, 0),
                close_time=time(23, 0),
                last_reservation_offset_minutes=120
            )
            for day in DayOfWeek:
                self.regular_hours[day] = default_hours

    @property
    def tz(self) -> pytz.timezone:
        """Get the timezone object."""
        return pytz.timezone(self.timezone)

    def get_hours_for_date(self, check_date: date) -> Optional[TimeRange]:
        """
        Get operating hours for a specific date.

        Returns:
            TimeRange for the date, or None if closed
        """
        # Check special hours first
        if check_date in self.special_hours:
            special = self.special_hours[check_date]
            return special.time_range

        # Check if explicitly closed
        if check_date in self.closed_dates:
            return None

        # Return regular hours for the day of week
        day_of_week = DayOfWeek(check_date.weekday())
        return self.regular_hours.get(day_of_week)

    def is_open_on_date(self, check_date: date) -> bool:
        """Check if the restaurant is open on a date."""
        return self.get_hours_for_date(check_date) is not None

    def is_valid_reservation_datetime(
        self,
        reservation_dt: datetime
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate if a datetime is valid for reservation.

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Ensure timezone aware
        if reservation_dt.tzinfo is None:
            reservation_dt = self.tz.localize(reservation_dt)
        else:
            reservation_dt = reservation_dt.astimezone(self.tz)

        now = get_current_datetime()
        rules = self.booking_rules

        # Check if in the past
        if reservation_dt <= now:
            return False, "Reservation time is in the past"

        # Check minimum lead time
        min_lead_time = now + timedelta(minutes=rules.minimum_lead_time_minutes)
        if reservation_dt < min_lead_time:
            return False, f"Reservation must be at least {rules.minimum_lead_time_minutes} minutes in advance"

        # Check maximum horizon
        max_date = now + timedelta(days=rules.maximum_horizon_days)
        if reservation_dt > max_date:
            return False, f"Reservation cannot be more than {rules.maximum_horizon_days} days in advance"

        # Get hours for the date
        hours = self.get_hours_for_date(reservation_dt.date())
        if hours is None:
            return False, "Restaurant is closed on this date"

        # Check if time is within operating hours
        res_time = reservation_dt.time()
        if not hours.is_time_within(res_time):
            return False, f"Reservation time must be between {hours.open_time.strftime('%H:%M')} and {hours.last_reservation_time.strftime('%H:%M')}"

        # Check time slot granularity
        if not rules.is_valid_time_slot(res_time):
            return False, f"Reservation time must be in {rules.time_slot_granularity_minutes}-minute increments"

        return True, None

    def validate_duration_against_closing(
        self,
        reservation_dt: datetime,
        duration_minutes: Optional[int] = None
    ) -> Tuple[bool, Optional[str], int]:
        """
        Validate that reservation duration doesn't exceed closing time.

        Returns:
            Tuple of (is_valid, error_message, adjusted_duration)
        """
        rules = self.booking_rules
        if duration_minutes is None:
            duration_minutes = rules.default_duration_minutes

        # Ensure timezone aware
        if reservation_dt.tzinfo is None:
            reservation_dt = self.tz.localize(reservation_dt)

        hours = self.get_hours_for_date(reservation_dt.date())
        if hours is None:
            return False, "Restaurant is closed on this date", 0

        # Calculate end time
        end_dt = reservation_dt + timedelta(minutes=duration_minutes)
        close_dt = datetime.combine(reservation_dt.date(), hours.close_time)
        close_dt = self.tz.localize(close_dt)

        if end_dt > close_dt:
            # Calculate maximum possible duration
            max_duration = int((close_dt - reservation_dt).total_seconds() / 60)
            if max_duration < rules.min_duration_minutes:
                return False, f"Not enough time before closing (need at least {rules.min_duration_minutes} minutes)", 0

            # Return adjusted duration
            return True, f"Duration adjusted to fit closing time", max_duration

        return True, None, duration_minutes


def get_default_restaurant_config() -> RestaurantConfig:
    """Get the default restaurant configuration."""
    # Define regular hours
    weekday_hours = TimeRange(
        open_time=time(11, 0),
        close_time=time(23, 0),
        last_reservation_offset_minutes=120
    )

    weekend_hours = TimeRange(
        open_time=time(10, 0),
        close_time=time(23, 59),
        last_reservation_offset_minutes=120
    )

    regular_hours = {
        DayOfWeek.MONDAY: weekday_hours,
        DayOfWeek.TUESDAY: weekday_hours,
        DayOfWeek.WEDNESDAY: weekday_hours,
        DayOfWeek.THURSDAY: weekday_hours,
        DayOfWeek.FRIDAY: weekday_hours,
        DayOfWeek.SATURDAY: weekend_hours,
        DayOfWeek.SUNDAY: weekend_hours,
    }

    booking_rules = BookingRules(
        time_slot_granularity_minutes=30,
        default_duration_minutes=90,
        minimum_lead_time_minutes=60,
        maximum_horizon_days=60,
        min_party_size=1,
        max_party_size=20,
        large_party_threshold=8,
        max_party_without_notes=8,
    )

    config = RestaurantConfig(
        name="Hunt Restaurant",
        timezone="Europe/Bratislava",
        regular_hours=regular_hours,
        booking_rules=booking_rules,
    )

    return config


# Singleton instance
_restaurant_config_instance: Optional[RestaurantConfig] = None


def get_restaurant_config() -> RestaurantConfig:
    """Get the restaurant configuration singleton."""
    global _restaurant_config_instance
    if _restaurant_config_instance is None:
        _restaurant_config_instance = get_default_restaurant_config()
    return _restaurant_config_instance
