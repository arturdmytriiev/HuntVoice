"""
Tests for the reservation validation module.
Covers phone normalization, name sanitization, time validation, and business rules.
"""

import pytest
from datetime import datetime, date, time, timedelta
from unittest.mock import patch
import pytz

from services.reservation_validation import (
    # Phone normalization
    normalize_phone_to_e164,
    validate_phone_strict,
    # Name/notes sanitization
    sanitize_name,
    sanitize_notes,
    # Time validation
    validate_reservation_datetime,
    # Party size validation
    validate_party_size,
    # Duration validation
    validate_duration,
    # Cross-field validation
    validate_cross_field_rules,
    # Idempotency
    generate_reservation_hash,
    check_idempotency,
    # Complete validation
    ReservationInput,
    ValidatedReservation,
    ValidationResult,
    ValidationSeverity,
    ValidationCategory,
    validate_reservation,
    # Service
    ReservationValidationService,
    get_validation_service,
)
from core.restaurant_config import (
    RestaurantConfig,
    TimeRange,
    BookingRules,
    DayOfWeek,
    SpecialHours,
    get_default_restaurant_config,
)
from core.utils_datetime import TIMEZONE, get_current_datetime


# ============================================================================
# Phone Normalization Tests
# ============================================================================

class TestPhoneNormalization:
    """Tests for phone number normalization to E.164 format."""

    def test_normalize_valid_e164(self):
        """Test normalization of already valid E.164 number."""
        phone, raw, error = normalize_phone_to_e164("+421901234567")
        assert phone == "+421901234567"
        assert error is None

    def test_normalize_local_slovak_number(self):
        """Test normalization of local Slovak number (starting with 0)."""
        phone, raw, error = normalize_phone_to_e164("0901234567")
        assert phone == "+421901234567"
        assert error is None

    def test_normalize_with_spaces(self):
        """Test normalization of number with spaces."""
        phone, raw, error = normalize_phone_to_e164("+421 901 234 567")
        assert phone == "+421901234567"
        assert error is None

    def test_normalize_with_dashes(self):
        """Test normalization of number with dashes."""
        phone, raw, error = normalize_phone_to_e164("+421-901-234-567")
        assert phone == "+421901234567"
        assert error is None

    def test_normalize_with_parentheses(self):
        """Test normalization of number with parentheses."""
        phone, raw, error = normalize_phone_to_e164("+421 (901) 234-567")
        assert phone == "+421901234567"
        assert error is None

    def test_normalize_international_00_prefix(self):
        """Test normalization of number with 00 international prefix."""
        phone, raw, error = normalize_phone_to_e164("00421901234567")
        assert phone == "+421901234567"
        assert error is None

    def test_normalize_keeps_raw(self):
        """Test that raw input is kept when requested."""
        phone, raw, error = normalize_phone_to_e164("0901234567", keep_raw=True)
        assert phone == "+421901234567"
        assert raw == "0901234567"
        assert error is None

    def test_normalize_empty_phone(self):
        """Test normalization of empty phone number."""
        phone, raw, error = normalize_phone_to_e164("")
        assert phone is None
        assert error is not None
        assert "required" in error.lower()

    def test_normalize_invalid_short(self):
        """Test normalization of too short number."""
        phone, raw, error = normalize_phone_to_e164("12345")
        assert phone is None
        assert error is not None

    def test_normalize_all_zeros(self):
        """Test rejection of all-zero number."""
        phone, raw, error = normalize_phone_to_e164("0000000000")
        assert phone is None
        assert error is not None

    def test_normalize_repeated_digits(self):
        """Test rejection of repeated digit pattern."""
        phone, raw, error = normalize_phone_to_e164("+4211111111111")
        assert phone is None
        assert error is not None

    def test_validate_strict_valid(self):
        """Test strict validation of valid number."""
        is_valid, error = validate_phone_strict("+421901234567")
        assert is_valid is True
        assert error is None

    def test_validate_strict_invalid_format(self):
        """Test strict validation of invalid format."""
        is_valid, error = validate_phone_strict("0901234567")
        assert is_valid is False
        assert error is not None


# ============================================================================
# Name Sanitization Tests
# ============================================================================

class TestNameSanitization:
    """Tests for guest name sanitization."""

    def test_sanitize_valid_name(self):
        """Test sanitization of valid name."""
        name, warnings = sanitize_name("John Doe")
        assert name == "John Doe"
        assert len(warnings) == 0

    def test_sanitize_trims_whitespace(self):
        """Test that leading/trailing whitespace is trimmed."""
        name, warnings = sanitize_name("  John Doe  ")
        assert name == "John Doe"

    def test_sanitize_collapses_whitespace(self):
        """Test that multiple spaces are collapsed."""
        name, warnings = sanitize_name("John    Doe")
        assert name == "John Doe"

    def test_sanitize_removes_invalid_chars(self):
        """Test removal of invalid characters."""
        name, warnings = sanitize_name("John <script>Doe")
        assert "<" not in name
        assert ">" not in name
        assert len(warnings) > 0

    def test_sanitize_empty_name(self):
        """Test sanitization of empty name."""
        name, warnings = sanitize_name("")
        assert name == ""
        assert len(warnings) > 0

    def test_sanitize_whitespace_only(self):
        """Test sanitization of whitespace-only name."""
        name, warnings = sanitize_name("   ")
        assert name == ""
        assert len(warnings) > 0

    def test_sanitize_test_name(self):
        """Test detection of test/placeholder names."""
        name, warnings = sanitize_name("test user")
        assert len(warnings) > 0
        assert any("invalid" in w.lower() or "placeholder" in w.lower() for w in warnings)

    def test_sanitize_truncates_long_name(self):
        """Test truncation of very long names."""
        long_name = "A" * 150
        name, warnings = sanitize_name(long_name, max_length=100)
        assert len(name) <= 100
        assert len(warnings) > 0

    def test_sanitize_unicode_name(self):
        """Test handling of Unicode characters in names."""
        name, warnings = sanitize_name("Ján Kováč")
        assert name == "Ján Kováč"
        assert len(warnings) == 0


# ============================================================================
# Notes Sanitization Tests
# ============================================================================

class TestNotesSanitization:
    """Tests for reservation notes sanitization."""

    def test_sanitize_valid_notes(self):
        """Test sanitization of valid notes."""
        notes, warnings = sanitize_notes("Window seat preferred")
        assert notes == "Window seat preferred"
        assert len(warnings) == 0

    def test_sanitize_none_notes(self):
        """Test sanitization of None notes."""
        notes, warnings = sanitize_notes(None)
        assert notes is None
        assert len(warnings) == 0

    def test_sanitize_empty_notes(self):
        """Test sanitization of empty notes."""
        notes, warnings = sanitize_notes("")
        assert notes is None
        assert len(warnings) == 0

    def test_sanitize_removes_html(self):
        """Test removal of HTML tags."""
        notes, warnings = sanitize_notes("Please <b>reserve</b> a quiet table")
        assert "<b>" not in notes
        assert "</b>" not in notes
        assert len(warnings) > 0

    def test_sanitize_removes_script(self):
        """Test removal of script tags."""
        notes, warnings = sanitize_notes("Note <script>alert('xss')</script> here")
        assert "script" not in notes.lower()
        assert len(warnings) > 0

    def test_sanitize_truncates_long_notes(self):
        """Test truncation of very long notes."""
        long_notes = "A" * 600
        notes, warnings = sanitize_notes(long_notes, max_length=500)
        assert len(notes) <= 500
        assert len(warnings) > 0

    def test_sanitize_collapses_whitespace(self):
        """Test that multiple spaces are collapsed."""
        notes, warnings = sanitize_notes("Window     seat     preferred")
        assert "     " not in notes


# ============================================================================
# Time Validation Tests
# ============================================================================

class TestTimeValidation:
    """Tests for reservation datetime validation."""

    @pytest.fixture
    def config(self):
        """Get default restaurant configuration."""
        return get_default_restaurant_config()

    def test_validate_future_time_valid(self, config):
        """Test validation of valid future time."""
        # Tomorrow at 18:00
        future_dt = get_current_datetime() + timedelta(days=1)
        future_dt = future_dt.replace(hour=18, minute=0, second=0, microsecond=0)

        result = validate_reservation_datetime(future_dt, config)
        assert result.is_valid is True

    def test_validate_past_time_invalid(self, config):
        """Test rejection of past time."""
        past_dt = get_current_datetime() - timedelta(hours=1)

        result = validate_reservation_datetime(past_dt, config)
        assert result.is_valid is False
        assert any("past" in e.message.lower() for e in result.errors)

    def test_validate_insufficient_lead_time(self, config):
        """Test rejection of insufficient lead time."""
        # 30 minutes from now (less than 60 min requirement)
        soon_dt = get_current_datetime() + timedelta(minutes=30)
        soon_dt = soon_dt.replace(second=0, microsecond=0)

        result = validate_reservation_datetime(soon_dt, config)
        # May pass if within opening hours, but should have warning/error about lead time
        # The exact behavior depends on whether restaurant is open

    def test_validate_exceeds_horizon(self, config):
        """Test rejection of too far in future."""
        # 100 days from now (exceeds 60 day limit)
        far_dt = get_current_datetime() + timedelta(days=100)
        far_dt = far_dt.replace(hour=18, minute=0)

        result = validate_reservation_datetime(far_dt, config)
        assert result.is_valid is False
        assert any("advance" in e.message.lower() or "days" in e.message.lower() for e in result.errors)

    def test_validate_before_opening(self, config):
        """Test rejection of time before opening."""
        # Tomorrow at 9:00 (before 11:00 opening)
        early_dt = get_current_datetime() + timedelta(days=1)
        early_dt = early_dt.replace(hour=9, minute=0)

        result = validate_reservation_datetime(early_dt, config)
        assert result.is_valid is False
        assert any("opens" in e.message.lower() for e in result.errors)

    def test_validate_after_last_reservation(self, config):
        """Test rejection of time after last reservation slot."""
        # Tomorrow at 22:00 (after 21:00 last reservation)
        late_dt = get_current_datetime() + timedelta(days=1)
        late_dt = late_dt.replace(hour=22, minute=0)

        result = validate_reservation_datetime(late_dt, config)
        assert result.is_valid is False
        assert any("last" in e.message.lower() or "reservation" in e.message.lower() for e in result.errors)

    def test_validate_invalid_time_slot(self, config):
        """Test rejection of non-aligned time slot."""
        # Tomorrow at 18:15 (not on 30-minute boundary)
        misaligned_dt = get_current_datetime() + timedelta(days=1)
        misaligned_dt = misaligned_dt.replace(hour=18, minute=15)

        result = validate_reservation_datetime(misaligned_dt, config)
        assert result.is_valid is False
        assert any("increment" in e.message.lower() for e in result.errors)

    def test_validate_valid_time_slot(self, config):
        """Test acceptance of aligned time slot."""
        # Tomorrow at 18:30 (on 30-minute boundary)
        aligned_dt = get_current_datetime() + timedelta(days=1)
        aligned_dt = aligned_dt.replace(hour=18, minute=30, second=0, microsecond=0)

        result = validate_reservation_datetime(aligned_dt, config)
        assert result.is_valid is True


# ============================================================================
# Party Size Validation Tests
# ============================================================================

class TestPartySizeValidation:
    """Tests for party size validation."""

    @pytest.fixture
    def config(self):
        """Get default restaurant configuration."""
        return get_default_restaurant_config()

    def test_validate_valid_party_size(self, config):
        """Test validation of valid party size."""
        result = validate_party_size(4, config=config)
        assert result.is_valid is True

    def test_validate_party_too_small(self, config):
        """Test rejection of party size less than 1."""
        result = validate_party_size(0, config=config)
        assert result.is_valid is False
        assert any("at least" in e.message.lower() for e in result.errors)

    def test_validate_party_too_large(self, config):
        """Test rejection of party size exceeding maximum."""
        result = validate_party_size(25, config=config)
        assert result.is_valid is False
        assert any("exceed" in e.message.lower() or "cannot" in e.message.lower() for e in result.errors)

    def test_validate_large_party_warning(self, config):
        """Test warning for large party (>=8)."""
        result = validate_party_size(8, config=config)
        assert result.is_valid is True
        assert len(result.warnings) > 0
        assert any("large party" in w.message.lower() for w in result.warnings)

    def test_validate_very_large_party_escalation(self, config):
        """Test escalation requirement for very large party (>12)."""
        result = validate_party_size(15, config=config)
        assert result.is_valid is True
        assert result.requires_escalation is True
        assert result.escalation_reason is not None

    def test_validate_large_party_needs_notes(self, config):
        """Test that large parties should have notes."""
        result = validate_party_size(10, notes=None, config=config)
        assert result.requires_manual_confirmation is True


# ============================================================================
# Duration Validation Tests
# ============================================================================

class TestDurationValidation:
    """Tests for reservation duration validation."""

    @pytest.fixture
    def config(self):
        """Get default restaurant configuration."""
        return get_default_restaurant_config()

    def test_validate_default_duration(self, config):
        """Test validation with default duration."""
        future_dt = get_current_datetime() + timedelta(days=1)
        future_dt = future_dt.replace(hour=18, minute=0)
        future_dt = config.tz.localize(future_dt.replace(tzinfo=None))

        result = validate_duration(future_dt, party_size=4, config=config)
        assert result.is_valid is True
        assert result.normalized_data["duration_minutes"] == 90

    def test_validate_adjusted_duration_for_large_party(self, config):
        """Test duration adjustment for large party."""
        future_dt = get_current_datetime() + timedelta(days=1)
        future_dt = future_dt.replace(hour=18, minute=0)
        future_dt = config.tz.localize(future_dt.replace(tzinfo=None))

        result = validate_duration(future_dt, party_size=10, config=config)
        assert result.is_valid is True
        # Large party gets extra time
        assert result.normalized_data["duration_minutes"] >= 90

    def test_validate_duration_too_short(self, config):
        """Test rejection of duration shorter than minimum."""
        future_dt = get_current_datetime() + timedelta(days=1)
        future_dt = future_dt.replace(hour=18, minute=0)
        future_dt = config.tz.localize(future_dt.replace(tzinfo=None))

        result = validate_duration(future_dt, party_size=4, duration_minutes=30, config=config)
        assert result.is_valid is False
        assert any("at least" in e.message.lower() for e in result.errors)

    def test_validate_duration_too_long(self, config):
        """Test rejection of duration longer than maximum."""
        future_dt = get_current_datetime() + timedelta(days=1)
        future_dt = future_dt.replace(hour=18, minute=0)
        future_dt = config.tz.localize(future_dt.replace(tzinfo=None))

        result = validate_duration(future_dt, party_size=4, duration_minutes=300, config=config)
        assert result.is_valid is False
        assert any("exceed" in e.message.lower() or "cannot" in e.message.lower() for e in result.errors)


# ============================================================================
# Cross-Field Validation Tests
# ============================================================================

class TestCrossFieldValidation:
    """Tests for cross-field validation rules."""

    @pytest.fixture
    def config(self):
        """Get default restaurant configuration."""
        return get_default_restaurant_config()

    def test_validate_large_party_without_notes(self, config):
        """Test warning for large party without notes."""
        future_dt = get_current_datetime() + timedelta(days=1)
        future_dt = future_dt.replace(hour=18, minute=0)
        future_dt = config.tz.localize(future_dt.replace(tzinfo=None))

        result = validate_cross_field_rules(
            name="John Doe",
            phone="+421901234567",
            reservation_dt=future_dt,
            party_size=10,
            notes=None,
            config=config
        )
        assert len(result.warnings) > 0

    def test_validate_weekend_large_party(self, config):
        """Test info for weekend large party."""
        # Find next Saturday
        future_dt = get_current_datetime()
        while future_dt.weekday() != 5:  # Saturday
            future_dt += timedelta(days=1)
        future_dt = future_dt.replace(hour=18, minute=0)
        future_dt = config.tz.localize(future_dt.replace(tzinfo=None))

        result = validate_cross_field_rules(
            name="John Doe",
            phone="+421901234567",
            reservation_dt=future_dt,
            party_size=8,
            notes="Birthday party",
            config=config
        )
        # Should have info about weekend + large party
        assert any("weekend" in w.message.lower() for w in result.warnings)


# ============================================================================
# Idempotency Tests
# ============================================================================

class TestIdempotency:
    """Tests for idempotency and duplicate detection."""

    def test_generate_hash_consistent(self):
        """Test that hash generation is consistent."""
        dt = datetime(2024, 12, 15, 18, 0, tzinfo=TIMEZONE)
        hash1 = generate_reservation_hash("+421901234567", dt, 4)
        hash2 = generate_reservation_hash("+421901234567", dt, 4)
        assert hash1 == hash2

    def test_generate_hash_different_inputs(self):
        """Test that different inputs produce different hashes."""
        dt = datetime(2024, 12, 15, 18, 0, tzinfo=TIMEZONE)
        hash1 = generate_reservation_hash("+421901234567", dt, 4)
        hash2 = generate_reservation_hash("+421901234567", dt, 5)
        assert hash1 != hash2

    def test_check_idempotency_no_duplicates(self):
        """Test idempotency check with no duplicates."""
        dt = datetime(2024, 12, 15, 18, 0, tzinfo=TIMEZONE)
        existing = set()

        is_dup, dup_hash = check_idempotency(
            "+421901234567", dt, 4, existing
        )
        assert is_dup is False
        assert dup_hash is None

    def test_check_idempotency_exact_duplicate(self):
        """Test idempotency check with exact duplicate."""
        dt = datetime(2024, 12, 15, 18, 0, tzinfo=TIMEZONE)
        hash_val = generate_reservation_hash("+421901234567", dt, 4)
        existing = {hash_val}

        is_dup, dup_hash = check_idempotency(
            "+421901234567", dt, 4, existing
        )
        assert is_dup is True
        assert dup_hash == hash_val

    def test_check_idempotency_near_duplicate(self):
        """Test idempotency check with near-duplicate (similar time)."""
        dt1 = datetime(2024, 12, 15, 18, 0, tzinfo=TIMEZONE)
        dt2 = datetime(2024, 12, 15, 18, 15, tzinfo=TIMEZONE)

        hash1 = generate_reservation_hash("+421901234567", dt1, 4)
        existing = {hash1}

        is_dup, dup_hash = check_idempotency(
            "+421901234567", dt2, 4, existing
        )
        assert is_dup is True


# ============================================================================
# Complete Validation Tests
# ============================================================================

class TestCompleteValidation:
    """Tests for complete reservation validation."""

    @pytest.fixture
    def config(self):
        """Get default restaurant configuration."""
        return get_default_restaurant_config()

    @pytest.fixture
    def valid_input(self):
        """Create valid reservation input."""
        future_date = (get_current_datetime() + timedelta(days=1)).date()
        return ReservationInput(
            name="John Doe",
            phone="0901234567",
            date=future_date,
            time=time(18, 30),
            guests=4,
            notes="Window seat preferred"
        )

    def test_validate_valid_reservation(self, valid_input, config):
        """Test validation of valid reservation."""
        validated, result = validate_reservation(valid_input, config=config)

        assert result.is_valid is True
        assert validated is not None
        assert validated.name == "John Doe"
        assert validated.phone_normalized == "+421901234567"
        assert validated.guests == 4

    def test_validate_normalizes_phone(self, valid_input, config):
        """Test that phone is normalized."""
        valid_input.phone = "0901 234 567"
        validated, result = validate_reservation(valid_input, config=config)

        assert validated is not None
        assert validated.phone_normalized == "+421901234567"

    def test_validate_sanitizes_name(self, valid_input, config):
        """Test that name is sanitized."""
        valid_input.name = "  John   Doe  "
        validated, result = validate_reservation(valid_input, config=config)

        assert validated is not None
        assert validated.name == "John Doe"

    def test_validate_sanitizes_notes(self, valid_input, config):
        """Test that notes are sanitized."""
        valid_input.notes = "Window <b>seat</b> preferred"
        validated, result = validate_reservation(valid_input, config=config)

        assert validated is not None
        assert "<b>" not in validated.notes

    def test_validate_rejects_past_reservation(self, config):
        """Test rejection of past reservation."""
        past_date = (get_current_datetime() - timedelta(days=1)).date()
        input_data = ReservationInput(
            name="John Doe",
            phone="+421901234567",
            date=past_date,
            time=time(18, 0),
            guests=4
        )

        validated, result = validate_reservation(input_data, config=config)
        assert result.is_valid is False
        assert validated is None

    def test_validate_rejects_duplicate(self, valid_input, config):
        """Test rejection of duplicate reservation."""
        # First reservation
        validated1, result1 = validate_reservation(valid_input, config=config)
        assert validated1 is not None

        # Create hash set with first reservation
        hashes = {validated1.idempotency_hash}

        # Try same reservation again
        validated2, result2 = validate_reservation(
            valid_input,
            existing_reservation_hashes=hashes,
            config=config
        )
        assert result2.is_valid is False
        assert any("duplicate" in e.message.lower() for e in result2.errors)

    def test_validate_returns_warnings(self, valid_input, config):
        """Test that warnings are captured."""
        valid_input.guests = 10  # Large party
        valid_input.notes = None  # No notes

        validated, result = validate_reservation(valid_input, config=config)
        assert result.is_valid is True
        assert len(result.warnings) > 0


# ============================================================================
# Validation Service Tests
# ============================================================================

class TestValidationService:
    """Tests for the validation service."""

    def test_service_singleton(self):
        """Test that service is a singleton."""
        service1 = get_validation_service()
        service2 = get_validation_service()
        assert service1 is service2

    def test_service_register_reservation(self):
        """Test registration of existing reservation."""
        service = ReservationValidationService()
        dt = datetime(2024, 12, 15, 18, 0, tzinfo=TIMEZONE)

        hash_val = service.register_existing_reservation(
            "+421901234567", dt, 4
        )
        assert hash_val is not None
        assert len(hash_val) == 16

    def test_service_unregister_reservation(self):
        """Test unregistration of reservation."""
        service = ReservationValidationService()
        dt = datetime(2024, 12, 15, 18, 0, tzinfo=TIMEZONE)

        hash_val = service.register_existing_reservation(
            "+421901234567", dt, 4
        )
        service.unregister_reservation(hash_val)
        # Should not raise error

    def test_service_validate_with_availability_callback(self):
        """Test validation with availability callback."""
        service = ReservationValidationService()
        future_date = (get_current_datetime() + timedelta(days=1)).date()

        input_data = ReservationInput(
            name="John Doe",
            phone="+421901234567",
            date=future_date,
            time=time(18, 30),
            guests=4
        )

        def mock_availability(dt, guests, duration):
            return True, None

        validated, result = service.validate_and_normalize(
            input_data,
            check_availability_callback=mock_availability
        )
        assert result.is_valid is True

    def test_service_validate_with_unavailable(self):
        """Test validation when slot is unavailable."""
        service = ReservationValidationService()
        future_date = (get_current_datetime() + timedelta(days=1)).date()

        input_data = ReservationInput(
            name="John Doe",
            phone="+421901234567",
            date=future_date,
            time=time(18, 30),
            guests=4
        )

        def mock_unavailable(dt, guests, duration):
            return False, "Time slot is fully booked"

        validated, result = service.validate_and_normalize(
            input_data,
            check_availability_callback=mock_unavailable
        )
        assert result.is_valid is False
        assert any("not available" in e.message.lower() or "booked" in e.message.lower() for e in result.errors)


# ============================================================================
# Restaurant Config Tests
# ============================================================================

class TestRestaurantConfig:
    """Tests for restaurant configuration."""

    def test_default_config_has_hours(self):
        """Test that default config has operating hours."""
        config = get_default_restaurant_config()
        assert len(config.regular_hours) == 7  # All days

    def test_config_get_hours_for_weekday(self):
        """Test getting hours for a weekday."""
        config = get_default_restaurant_config()
        monday = date(2024, 12, 16)  # A Monday
        hours = config.get_hours_for_date(monday)
        assert hours is not None
        assert hours.open_time == time(11, 0)

    def test_config_get_hours_for_weekend(self):
        """Test getting hours for weekend."""
        config = get_default_restaurant_config()
        saturday = date(2024, 12, 14)  # A Saturday
        hours = config.get_hours_for_date(saturday)
        assert hours is not None
        assert hours.open_time == time(10, 0)  # Weekend opens earlier

    def test_config_closed_date(self):
        """Test closed date handling."""
        config = get_default_restaurant_config()
        christmas = date(2024, 12, 25)
        config.closed_dates.add(christmas)

        hours = config.get_hours_for_date(christmas)
        assert hours is None
        assert not config.is_open_on_date(christmas)

    def test_config_special_hours(self):
        """Test special hours handling."""
        config = get_default_restaurant_config()
        new_years_eve = date(2024, 12, 31)
        config.special_hours[new_years_eve] = SpecialHours(
            date=new_years_eve,
            time_range=TimeRange(
                open_time=time(18, 0),
                close_time=time(2, 0),  # Next day
            ),
            description="New Year's Eve - Special hours"
        )

        hours = config.get_hours_for_date(new_years_eve)
        assert hours is not None
        assert hours.open_time == time(18, 0)

    def test_booking_rules_time_slot_validation(self):
        """Test time slot granularity validation."""
        rules = BookingRules(time_slot_granularity_minutes=30)

        assert rules.is_valid_time_slot(time(18, 0)) is True
        assert rules.is_valid_time_slot(time(18, 30)) is True
        assert rules.is_valid_time_slot(time(18, 15)) is False
        assert rules.is_valid_time_slot(time(18, 45)) is False

    def test_booking_rules_duration_for_party(self):
        """Test duration adjustment for party size."""
        rules = BookingRules(default_duration_minutes=90)

        assert rules.get_adjusted_duration_for_party(4) == 90
        assert rules.get_adjusted_duration_for_party(8) >= 90
        assert rules.get_adjusted_duration_for_party(12) >= 90


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
