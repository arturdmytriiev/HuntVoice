"""
Comprehensive reservation validation and normalization module.
Handles all business rules, input sanitization, and cross-field validation.
"""

import re
import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime, date, time, timedelta
from typing import Dict, List, Optional, Tuple, Any, Set
from enum import Enum

from core.utils_datetime import TIMEZONE, get_current_datetime
from core.restaurant_config import (
    RestaurantConfig,
    get_restaurant_config,
    BookingRules,
)


logger = logging.getLogger(__name__)


class ValidationSeverity(Enum):
    """Validation error severity levels."""
    ERROR = "error"  # Blocks reservation
    WARNING = "warning"  # Allowed but flagged
    INFO = "info"  # Informational message


class ValidationCategory(Enum):
    """Validation error categories."""
    PHONE = "phone"
    NAME = "name"
    DATE_TIME = "datetime"
    PARTY_SIZE = "party_size"
    DURATION = "duration"
    CAPACITY = "capacity"
    NOTES = "notes"
    CROSS_FIELD = "cross_field"
    IDEMPOTENCY = "idempotency"
    AVAILABILITY = "availability"


@dataclass
class ValidationError:
    """Represents a validation error or warning."""
    category: ValidationCategory
    severity: ValidationSeverity
    message: str
    field: Optional[str] = None
    code: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


@dataclass
class ValidationResult:
    """Result of validation with all errors and warnings."""
    is_valid: bool
    errors: List[ValidationError] = field(default_factory=list)
    warnings: List[ValidationError] = field(default_factory=list)
    normalized_data: Dict[str, Any] = field(default_factory=dict)
    requires_manual_confirmation: bool = False
    requires_escalation: bool = False
    escalation_reason: Optional[str] = None

    def add_error(self, error: ValidationError):
        """Add an error and mark as invalid."""
        if error.severity == ValidationSeverity.ERROR:
            self.errors.append(error)
            self.is_valid = False
        elif error.severity == ValidationSeverity.WARNING:
            self.warnings.append(error)
        else:
            self.warnings.append(error)

    def get_error_messages(self) -> List[str]:
        """Get all error messages."""
        return [e.message for e in self.errors]

    def get_warning_messages(self) -> List[str]:
        """Get all warning messages."""
        return [w.message for w in self.warnings]


# ============================================================================
# Phone Number Normalization & Validation
# ============================================================================

# Slovak country code
SLOVAK_COUNTRY_CODE = "+421"
DEFAULT_COUNTRY_CODE = SLOVAK_COUNTRY_CODE

# Valid phone number patterns for E.164
E164_PATTERN = re.compile(r'^\+[1-9]\d{6,14}$')
E164_STRICT_PATTERN = re.compile(r'^\+[1-9]\d{1,3}\d{6,12}$')

# Slovak mobile prefixes (after country code)
SLOVAK_MOBILE_PREFIXES = {'90', '91', '92', '93', '94', '95', '96', '97', '98', '99'}

# Invalid/suspicious patterns
INVALID_PHONE_PATTERNS = [
    r'^(\+?0+)$',  # All zeros
    r'^(\d)\1{6,}$',  # Same digit repeated 7+ times
    r'^1234567',  # Sequential digits
    r'^0000000',  # Leading zeros
    r'^\+0',  # Plus followed by zero
]


def normalize_phone_to_e164(
    phone: str,
    default_country_code: str = DEFAULT_COUNTRY_CODE,
    keep_raw: bool = False
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Normalize phone number to E.164 format.

    Args:
        phone: Raw phone number input
        default_country_code: Default country code to apply
        keep_raw: If True, returns the original input as well

    Returns:
        Tuple of (normalized_phone, raw_phone if keep_raw else None, error_message)
    """
    if not phone:
        return None, phone if keep_raw else None, "Phone number is required"

    raw_input = phone
    # Remove all whitespace and common separators
    cleaned = re.sub(r'[\s\-\.\(\)\[\]]', '', phone)

    # Remove common prefixes like "tel:", "phone:"
    cleaned = re.sub(r'^(tel:|phone:|mob:|mobile:)', '', cleaned, flags=re.IGNORECASE)

    # Handle 00 prefix (European international format)
    if cleaned.startswith('00'):
        cleaned = '+' + cleaned[2:]

    # Handle Slovak local format (starts with 0, like 0901234567)
    if cleaned.startswith('0') and not cleaned.startswith('00') and len(cleaned) >= 9:
        # Remove leading 0 and add country code
        cleaned = default_country_code + cleaned[1:]

    # Handle number without any prefix (assume local)
    if not cleaned.startswith('+'):
        # Check if it looks like a full number already
        if len(cleaned) >= 9 and cleaned[0] != '0':
            # Check if it might already have country code without +
            if cleaned.startswith('421'):
                cleaned = '+' + cleaned
            else:
                cleaned = default_country_code + cleaned
        elif len(cleaned) >= 9:
            cleaned = default_country_code + cleaned

    # Final cleanup - only digits and leading +
    if cleaned.startswith('+'):
        digits = re.sub(r'[^\d]', '', cleaned[1:])
        cleaned = '+' + digits
    else:
        digits = re.sub(r'[^\d]', '', cleaned)
        cleaned = '+' + digits

    # Validate the result
    raw_result = raw_input if keep_raw else None

    if not E164_PATTERN.match(cleaned):
        return None, raw_result, f"Invalid phone format: must be E.164 (got {cleaned})"

    # Check for suspicious patterns
    digits_only = cleaned[1:]  # Remove +
    for pattern in INVALID_PHONE_PATTERNS:
        if re.match(pattern, digits_only):
            return None, raw_result, "Phone number appears to be invalid"

    return cleaned, raw_result, None


def validate_phone_strict(phone: str) -> Tuple[bool, Optional[str]]:
    """
    Strictly validate a phone number.

    Args:
        phone: Phone number to validate (should be normalized E.164)

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not phone:
        return False, "Phone number is required"

    if not E164_PATTERN.match(phone):
        return False, "Phone number must be in E.164 format (e.g., +421901234567)"

    # Length validation (E.164 allows 7-15 digits after +)
    digits = phone[1:]  # Remove +
    if len(digits) < 7:
        return False, "Phone number is too short"
    if len(digits) > 15:
        return False, "Phone number is too long"

    # Check for suspicious patterns
    for pattern in INVALID_PHONE_PATTERNS:
        if re.match(pattern, digits):
            return False, "Phone number appears to be invalid"

    return True, None


# ============================================================================
# Name & Notes Sanitization
# ============================================================================

# Invalid name patterns
INVALID_NAME_PATTERNS = [
    r'^[0-9\s\-\.]+$',  # Only digits and punctuation
    r'^\s*$',  # Empty or whitespace only
    r'^(.)\1{3,}$',  # Same character repeated 4+ times
    r'^test\s*(user|name)?$',  # Test entries
    r'^xxx+$',  # Placeholder patterns
    r'^n/?a$',  # N/A entries
    r'^none$',  # None entries
    r'^unknown$',  # Unknown entries
]

# Characters to remove from names
NAME_INVALID_CHARS = re.compile(r'[<>{}|\[\]\\^`~@#$%&*+=]')

# Multiple whitespace pattern
MULTIPLE_WHITESPACE = re.compile(r'\s+')


def sanitize_name(name: str, max_length: int = 100) -> Tuple[str, List[str]]:
    """
    Sanitize and normalize a guest name.

    Args:
        name: Raw name input
        max_length: Maximum allowed length

    Returns:
        Tuple of (sanitized_name, list of warnings)
    """
    warnings = []

    if not name:
        return "", ["Name is empty"]

    # Trim whitespace
    sanitized = name.strip()

    # Remove invalid characters
    original = sanitized
    sanitized = NAME_INVALID_CHARS.sub('', sanitized)
    if sanitized != original:
        warnings.append("Invalid characters were removed from name")

    # Collapse multiple whitespace
    sanitized = MULTIPLE_WHITESPACE.sub(' ', sanitized)

    # Trim again after cleanup
    sanitized = sanitized.strip()

    # Check for invalid patterns
    name_lower = sanitized.lower()
    for pattern in INVALID_NAME_PATTERNS:
        if re.match(pattern, name_lower, re.IGNORECASE):
            warnings.append(f"Name appears to be invalid or placeholder")
            break

    # Truncate if too long
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length].rsplit(' ', 1)[0]  # Don't cut mid-word
        warnings.append(f"Name was truncated to {max_length} characters")

    return sanitized, warnings


def sanitize_notes(notes: Optional[str], max_length: int = 500) -> Tuple[Optional[str], List[str]]:
    """
    Sanitize and normalize reservation notes.

    Args:
        notes: Raw notes input
        max_length: Maximum allowed length

    Returns:
        Tuple of (sanitized_notes, list of warnings)
    """
    warnings = []

    if not notes:
        return None, []

    # Trim whitespace
    sanitized = notes.strip()

    if not sanitized:
        return None, []

    # Remove potentially dangerous patterns (basic XSS prevention)
    dangerous_patterns = [
        (r'<script[^>]*>.*?</script>', '[removed]'),
        (r'<[^>]+>', ''),  # Remove HTML tags
        (r'javascript:', ''),
        (r'on\w+\s*=', ''),  # Event handlers
    ]

    original = sanitized
    for pattern, replacement in dangerous_patterns:
        sanitized = re.sub(pattern, replacement, sanitized, flags=re.IGNORECASE | re.DOTALL)

    if sanitized != original:
        warnings.append("Potentially unsafe content was removed from notes")

    # Collapse multiple whitespace and newlines
    sanitized = MULTIPLE_WHITESPACE.sub(' ', sanitized)
    sanitized = re.sub(r'\n{3,}', '\n\n', sanitized)

    # Trim again
    sanitized = sanitized.strip()

    # Truncate if too long
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length]
        # Try to not cut mid-sentence
        last_period = sanitized.rfind('.')
        if last_period > max_length * 0.7:
            sanitized = sanitized[:last_period + 1]
        warnings.append(f"Notes were truncated to {max_length} characters")

    return sanitized if sanitized else None, warnings


# ============================================================================
# Time-Based Validation
# ============================================================================

def validate_reservation_datetime(
    reservation_dt: datetime,
    config: Optional[RestaurantConfig] = None
) -> ValidationResult:
    """
    Validate reservation datetime against all time-based rules.

    Args:
        reservation_dt: The proposed reservation datetime
        config: Restaurant configuration (uses default if not provided)

    Returns:
        ValidationResult with any errors/warnings
    """
    result = ValidationResult(is_valid=True)
    config = config or get_restaurant_config()
    rules = config.booking_rules

    # Ensure timezone aware
    if reservation_dt.tzinfo is None:
        reservation_dt = config.tz.localize(reservation_dt)
    else:
        reservation_dt = reservation_dt.astimezone(config.tz)

    now = get_current_datetime()

    # Check if in the past
    if reservation_dt <= now:
        result.add_error(ValidationError(
            category=ValidationCategory.DATE_TIME,
            severity=ValidationSeverity.ERROR,
            message="Reservation time is in the past",
            field="datetime",
            code="PAST_DATETIME"
        ))
        return result

    # Check minimum lead time
    min_lead_time = now + timedelta(minutes=rules.minimum_lead_time_minutes)
    if reservation_dt < min_lead_time:
        result.add_error(ValidationError(
            category=ValidationCategory.DATE_TIME,
            severity=ValidationSeverity.ERROR,
            message=f"Reservation must be at least {rules.minimum_lead_time_minutes} minutes in advance",
            field="datetime",
            code="INSUFFICIENT_LEAD_TIME",
            details={"minimum_minutes": rules.minimum_lead_time_minutes}
        ))

    # Check maximum horizon
    max_date = now + timedelta(days=rules.maximum_horizon_days)
    if reservation_dt > max_date:
        result.add_error(ValidationError(
            category=ValidationCategory.DATE_TIME,
            severity=ValidationSeverity.ERROR,
            message=f"Reservation cannot be more than {rules.maximum_horizon_days} days in advance",
            field="datetime",
            code="EXCEEDS_HORIZON",
            details={"maximum_days": rules.maximum_horizon_days}
        ))

    # Get hours for the date
    hours = config.get_hours_for_date(reservation_dt.date())
    if hours is None:
        result.add_error(ValidationError(
            category=ValidationCategory.DATE_TIME,
            severity=ValidationSeverity.ERROR,
            message="Restaurant is closed on this date",
            field="date",
            code="CLOSED_DATE"
        ))
        return result

    # Check if time is within operating hours
    res_time = reservation_dt.time()
    if res_time < hours.open_time:
        result.add_error(ValidationError(
            category=ValidationCategory.DATE_TIME,
            severity=ValidationSeverity.ERROR,
            message=f"Restaurant opens at {hours.open_time.strftime('%H:%M')}",
            field="time",
            code="BEFORE_OPENING"
        ))
    elif res_time > hours.last_reservation_time:
        result.add_error(ValidationError(
            category=ValidationCategory.DATE_TIME,
            severity=ValidationSeverity.ERROR,
            message=f"Last reservation is at {hours.last_reservation_time.strftime('%H:%M')}",
            field="time",
            code="AFTER_LAST_RESERVATION"
        ))

    # Check time slot granularity
    if not rules.is_valid_time_slot(res_time):
        result.add_error(ValidationError(
            category=ValidationCategory.DATE_TIME,
            severity=ValidationSeverity.ERROR,
            message=f"Reservation time must be in {rules.time_slot_granularity_minutes}-minute increments (e.g., 18:00, 18:30)",
            field="time",
            code="INVALID_TIME_SLOT",
            details={"granularity_minutes": rules.time_slot_granularity_minutes}
        ))

    return result


# ============================================================================
# Party Size & Capacity Validation
# ============================================================================

def validate_party_size(
    party_size: int,
    notes: Optional[str] = None,
    config: Optional[RestaurantConfig] = None
) -> ValidationResult:
    """
    Validate party size and apply capacity rules.

    Args:
        party_size: Number of guests
        notes: Optional reservation notes
        config: Restaurant configuration

    Returns:
        ValidationResult with any errors/warnings
    """
    result = ValidationResult(is_valid=True)
    config = config or get_restaurant_config()
    rules = config.booking_rules

    # Basic range validation
    if party_size < rules.min_party_size:
        result.add_error(ValidationError(
            category=ValidationCategory.PARTY_SIZE,
            severity=ValidationSeverity.ERROR,
            message=f"Party size must be at least {rules.min_party_size}",
            field="guests",
            code="PARTY_TOO_SMALL"
        ))

    if party_size > rules.max_party_size:
        result.add_error(ValidationError(
            category=ValidationCategory.PARTY_SIZE,
            severity=ValidationSeverity.ERROR,
            message=f"Party size cannot exceed {rules.max_party_size} guests",
            field="guests",
            code="PARTY_TOO_LARGE"
        ))

    # Large party handling
    if party_size >= rules.large_party_threshold:
        result.add_error(ValidationError(
            category=ValidationCategory.PARTY_SIZE,
            severity=ValidationSeverity.WARNING,
            message=f"Large party ({party_size} guests) - may require special arrangements",
            field="guests",
            code="LARGE_PARTY",
            details={"threshold": rules.large_party_threshold}
        ))

        # Check if notes are required for large parties
        if party_size > rules.max_party_without_notes:
            if not notes or len(notes.strip()) < 10:
                result.requires_manual_confirmation = True
                result.add_error(ValidationError(
                    category=ValidationCategory.CROSS_FIELD,
                    severity=ValidationSeverity.WARNING,
                    message=f"Large party (>{rules.max_party_without_notes} guests) should include notes with contact details or special requirements",
                    field="notes",
                    code="LARGE_PARTY_NOTES_RECOMMENDED"
                ))

    # Very large parties require escalation
    if party_size > 12:
        result.requires_escalation = True
        result.escalation_reason = f"Large party of {party_size} guests requires manager approval"
        result.add_error(ValidationError(
            category=ValidationCategory.PARTY_SIZE,
            severity=ValidationSeverity.WARNING,
            message="Party of more than 12 guests requires manual confirmation",
            field="guests",
            code="ESCALATION_REQUIRED"
        ))

    return result


# ============================================================================
# Duration Validation
# ============================================================================

def validate_duration(
    reservation_dt: datetime,
    party_size: int,
    duration_minutes: Optional[int] = None,
    config: Optional[RestaurantConfig] = None
) -> ValidationResult:
    """
    Validate reservation duration against closing time.

    Args:
        reservation_dt: Reservation start time
        party_size: Number of guests (affects duration)
        duration_minutes: Requested duration (or None for default)
        config: Restaurant configuration

    Returns:
        ValidationResult with adjusted duration in normalized_data
    """
    result = ValidationResult(is_valid=True)
    config = config or get_restaurant_config()
    rules = config.booking_rules

    # Get appropriate duration for party size
    if duration_minutes is None:
        duration_minutes = rules.get_adjusted_duration_for_party(party_size)

    # Validate duration bounds
    if duration_minutes < rules.min_duration_minutes:
        result.add_error(ValidationError(
            category=ValidationCategory.DURATION,
            severity=ValidationSeverity.ERROR,
            message=f"Reservation duration must be at least {rules.min_duration_minutes} minutes",
            field="duration",
            code="DURATION_TOO_SHORT"
        ))

    if duration_minutes > rules.max_duration_minutes:
        result.add_error(ValidationError(
            category=ValidationCategory.DURATION,
            severity=ValidationSeverity.ERROR,
            message=f"Reservation duration cannot exceed {rules.max_duration_minutes} minutes",
            field="duration",
            code="DURATION_TOO_LONG"
        ))

    # Check against closing time
    is_valid, message, adjusted_duration = config.validate_duration_against_closing(
        reservation_dt, duration_minutes
    )

    if not is_valid:
        result.add_error(ValidationError(
            category=ValidationCategory.DURATION,
            severity=ValidationSeverity.ERROR,
            message=message,
            field="duration",
            code="EXCEEDS_CLOSING"
        ))
    elif adjusted_duration != duration_minutes:
        result.add_error(ValidationError(
            category=ValidationCategory.DURATION,
            severity=ValidationSeverity.WARNING,
            message=f"Duration adjusted from {duration_minutes} to {adjusted_duration} minutes to fit closing time",
            field="duration",
            code="DURATION_ADJUSTED"
        ))

    result.normalized_data["duration_minutes"] = adjusted_duration
    return result


# ============================================================================
# Cross-Field Validation
# ============================================================================

def validate_cross_field_rules(
    name: str,
    phone: str,
    reservation_dt: datetime,
    party_size: int,
    notes: Optional[str] = None,
    config: Optional[RestaurantConfig] = None
) -> ValidationResult:
    """
    Validate cross-field business rules.

    Args:
        name: Guest name
        phone: Phone number
        reservation_dt: Reservation datetime
        party_size: Number of guests
        notes: Optional notes
        config: Restaurant configuration

    Returns:
        ValidationResult with cross-field validation results
    """
    result = ValidationResult(is_valid=True)
    config = config or get_restaurant_config()
    rules = config.booking_rules

    # Large party requires notes
    if party_size > rules.max_party_without_notes:
        if not notes or len(notes.strip()) < 10:
            result.add_error(ValidationError(
                category=ValidationCategory.CROSS_FIELD,
                severity=ValidationSeverity.WARNING,
                message=f"Parties larger than {rules.max_party_without_notes} guests should provide contact details or special requirements in notes",
                field="notes",
                code="LARGE_PARTY_NEEDS_NOTES"
            ))
            result.requires_manual_confirmation = True

    # Check for holiday/special date
    if reservation_dt.date() in config.special_hours:
        special = config.special_hours[reservation_dt.date()]
        if special.description:
            result.add_error(ValidationError(
                category=ValidationCategory.CROSS_FIELD,
                severity=ValidationSeverity.INFO,
                message=f"Note: {special.description}",
                field="date",
                code="SPECIAL_DATE",
                details={"description": special.description}
            ))

    # Weekend large party warning
    if reservation_dt.weekday() >= 5 and party_size >= 6:  # Saturday/Sunday
        result.add_error(ValidationError(
            category=ValidationCategory.CROSS_FIELD,
            severity=ValidationSeverity.INFO,
            message="Weekend reservations for larger parties may have limited availability",
            field="date",
            code="WEEKEND_LARGE_PARTY"
        ))

    # Same-day large party requires extra lead time
    now = get_current_datetime()
    if reservation_dt.date() == now.date() and party_size >= 6:
        hours_until = (reservation_dt - now).total_seconds() / 3600
        if hours_until < 4:
            result.add_error(ValidationError(
                category=ValidationCategory.CROSS_FIELD,
                severity=ValidationSeverity.WARNING,
                message="Same-day reservations for larger parties ideally need at least 4 hours notice",
                field="datetime",
                code="SAME_DAY_LARGE_PARTY"
            ))

    return result


# ============================================================================
# Idempotency & Duplicate Detection
# ============================================================================

def generate_reservation_hash(
    phone: str,
    reservation_dt: datetime,
    party_size: int
) -> str:
    """
    Generate a hash for duplicate detection.

    Args:
        phone: Normalized phone number
        reservation_dt: Reservation datetime
        party_size: Number of guests

    Returns:
        Hash string for idempotency checking
    """
    # Create a unique key from the key fields
    key_string = f"{phone}|{reservation_dt.isoformat()}|{party_size}"
    return hashlib.sha256(key_string.encode()).hexdigest()[:16]


def check_idempotency(
    phone: str,
    reservation_dt: datetime,
    party_size: int,
    existing_hashes: Set[str],
    time_window_minutes: int = 30
) -> Tuple[bool, Optional[str]]:
    """
    Check for potential duplicate reservations.

    Args:
        phone: Normalized phone number
        reservation_dt: Proposed reservation datetime
        party_size: Number of guests
        existing_hashes: Set of existing reservation hashes
        time_window_minutes: Window for considering near-duplicates

    Returns:
        Tuple of (is_duplicate, duplicate_hash)
    """
    # Check exact match
    exact_hash = generate_reservation_hash(phone, reservation_dt, party_size)
    if exact_hash in existing_hashes:
        return True, exact_hash

    # Check near-matches (same phone, nearby time)
    for offset in range(-time_window_minutes, time_window_minutes + 1, 15):
        if offset == 0:
            continue
        check_dt = reservation_dt + timedelta(minutes=offset)
        check_hash = generate_reservation_hash(phone, check_dt, party_size)
        if check_hash in existing_hashes:
            return True, check_hash

    return False, None


# ============================================================================
# Complete Reservation Validation
# ============================================================================

@dataclass
class ReservationInput:
    """Input data for reservation validation."""
    name: str
    phone: str
    date: date
    time: time
    guests: int
    notes: Optional[str] = None
    duration_minutes: Optional[int] = None


@dataclass
class ValidatedReservation:
    """Validated and normalized reservation data."""
    name: str
    phone_normalized: str
    phone_raw: Optional[str]
    datetime: datetime
    guests: int
    notes: Optional[str]
    duration_minutes: int
    idempotency_hash: str
    requires_manual_confirmation: bool = False
    requires_escalation: bool = False
    escalation_reason: Optional[str] = None


def validate_reservation(
    input_data: ReservationInput,
    existing_reservation_hashes: Optional[Set[str]] = None,
    config: Optional[RestaurantConfig] = None
) -> Tuple[Optional[ValidatedReservation], ValidationResult]:
    """
    Perform complete validation and normalization of a reservation.

    Args:
        input_data: Raw reservation input
        existing_reservation_hashes: Set of hashes for duplicate detection
        config: Restaurant configuration

    Returns:
        Tuple of (ValidatedReservation or None, ValidationResult)
    """
    config = config or get_restaurant_config()
    result = ValidationResult(is_valid=True)
    existing_hashes = existing_reservation_hashes or set()

    # -------------------------------------------------------------------------
    # 1. Sanitize name
    # -------------------------------------------------------------------------
    sanitized_name, name_warnings = sanitize_name(input_data.name)
    for warning in name_warnings:
        result.add_error(ValidationError(
            category=ValidationCategory.NAME,
            severity=ValidationSeverity.WARNING,
            message=warning,
            field="name",
            code="NAME_SANITIZED"
        ))

    if not sanitized_name:
        result.add_error(ValidationError(
            category=ValidationCategory.NAME,
            severity=ValidationSeverity.ERROR,
            message="Guest name is required",
            field="name",
            code="NAME_REQUIRED"
        ))

    # -------------------------------------------------------------------------
    # 2. Normalize and validate phone
    # -------------------------------------------------------------------------
    normalized_phone, raw_phone, phone_error = normalize_phone_to_e164(
        input_data.phone, keep_raw=True
    )

    if phone_error:
        result.add_error(ValidationError(
            category=ValidationCategory.PHONE,
            severity=ValidationSeverity.ERROR,
            message=phone_error,
            field="phone",
            code="INVALID_PHONE"
        ))
    else:
        # Additional strict validation
        is_valid_phone, strict_error = validate_phone_strict(normalized_phone)
        if not is_valid_phone:
            result.add_error(ValidationError(
                category=ValidationCategory.PHONE,
                severity=ValidationSeverity.ERROR,
                message=strict_error,
                field="phone",
                code="PHONE_VALIDATION_FAILED"
            ))

    # -------------------------------------------------------------------------
    # 3. Sanitize notes
    # -------------------------------------------------------------------------
    sanitized_notes, notes_warnings = sanitize_notes(input_data.notes)
    for warning in notes_warnings:
        result.add_error(ValidationError(
            category=ValidationCategory.NOTES,
            severity=ValidationSeverity.WARNING,
            message=warning,
            field="notes",
            code="NOTES_SANITIZED"
        ))

    # -------------------------------------------------------------------------
    # 4. Construct datetime and validate
    # -------------------------------------------------------------------------
    try:
        reservation_dt = datetime.combine(input_data.date, input_data.time)
        reservation_dt = config.tz.localize(reservation_dt)
    except Exception as e:
        result.add_error(ValidationError(
            category=ValidationCategory.DATE_TIME,
            severity=ValidationSeverity.ERROR,
            message=f"Invalid date/time: {str(e)}",
            field="datetime",
            code="DATETIME_INVALID"
        ))
        return None, result

    datetime_result = validate_reservation_datetime(reservation_dt, config)
    result.errors.extend(datetime_result.errors)
    result.warnings.extend(datetime_result.warnings)
    if not datetime_result.is_valid:
        result.is_valid = False

    # -------------------------------------------------------------------------
    # 5. Validate party size
    # -------------------------------------------------------------------------
    party_result = validate_party_size(input_data.guests, sanitized_notes, config)
    result.errors.extend(party_result.errors)
    result.warnings.extend(party_result.warnings)
    if not party_result.is_valid:
        result.is_valid = False
    if party_result.requires_manual_confirmation:
        result.requires_manual_confirmation = True
    if party_result.requires_escalation:
        result.requires_escalation = True
        result.escalation_reason = party_result.escalation_reason

    # -------------------------------------------------------------------------
    # 6. Validate duration
    # -------------------------------------------------------------------------
    duration_result = validate_duration(
        reservation_dt,
        input_data.guests,
        input_data.duration_minutes,
        config
    )
    result.errors.extend(duration_result.errors)
    result.warnings.extend(duration_result.warnings)
    if not duration_result.is_valid:
        result.is_valid = False

    final_duration = duration_result.normalized_data.get(
        "duration_minutes",
        config.booking_rules.default_duration_minutes
    )

    # -------------------------------------------------------------------------
    # 7. Cross-field validation
    # -------------------------------------------------------------------------
    if normalized_phone:  # Only if phone is valid
        cross_result = validate_cross_field_rules(
            sanitized_name,
            normalized_phone,
            reservation_dt,
            input_data.guests,
            sanitized_notes,
            config
        )
        result.errors.extend(cross_result.errors)
        result.warnings.extend(cross_result.warnings)
        if cross_result.requires_manual_confirmation:
            result.requires_manual_confirmation = True
        if cross_result.requires_escalation:
            result.requires_escalation = True
            result.escalation_reason = cross_result.escalation_reason

    # -------------------------------------------------------------------------
    # 8. Idempotency check
    # -------------------------------------------------------------------------
    if normalized_phone and result.is_valid:
        is_duplicate, dup_hash = check_idempotency(
            normalized_phone,
            reservation_dt,
            input_data.guests,
            existing_hashes
        )
        if is_duplicate:
            result.add_error(ValidationError(
                category=ValidationCategory.IDEMPOTENCY,
                severity=ValidationSeverity.ERROR,
                message="A similar reservation already exists (duplicate detected)",
                field="phone",
                code="DUPLICATE_RESERVATION",
                details={"hash": dup_hash}
            ))

    # -------------------------------------------------------------------------
    # Build validated reservation if valid
    # -------------------------------------------------------------------------
    if not result.is_valid:
        return None, result

    idempotency_hash = generate_reservation_hash(
        normalized_phone,
        reservation_dt,
        input_data.guests
    )

    validated = ValidatedReservation(
        name=sanitized_name,
        phone_normalized=normalized_phone,
        phone_raw=raw_phone,
        datetime=reservation_dt,
        guests=input_data.guests,
        notes=sanitized_notes,
        duration_minutes=final_duration,
        idempotency_hash=idempotency_hash,
        requires_manual_confirmation=result.requires_manual_confirmation,
        requires_escalation=result.requires_escalation,
        escalation_reason=result.escalation_reason,
    )

    # Store normalized data in result
    result.normalized_data = {
        "name": sanitized_name,
        "phone": normalized_phone,
        "phone_raw": raw_phone,
        "datetime": reservation_dt.isoformat(),
        "guests": input_data.guests,
        "notes": sanitized_notes,
        "duration_minutes": final_duration,
        "idempotency_hash": idempotency_hash,
    }

    return validated, result


# ============================================================================
# Service-Layer Hooks
# ============================================================================

class ReservationValidationService:
    """
    Service-layer interface for reservation validation.
    Provides hooks for availability checking and idempotency.
    """

    def __init__(self, config: Optional[RestaurantConfig] = None):
        """Initialize the validation service."""
        self.config = config or get_restaurant_config()
        self._reservation_hashes: Set[str] = set()

    def register_existing_reservation(
        self,
        phone: str,
        reservation_dt: datetime,
        party_size: int
    ) -> str:
        """
        Register an existing reservation for duplicate detection.

        Returns:
            The idempotency hash
        """
        hash_value = generate_reservation_hash(phone, reservation_dt, party_size)
        self._reservation_hashes.add(hash_value)
        return hash_value

    def unregister_reservation(self, hash_value: str):
        """Remove a reservation hash (e.g., when cancelled)."""
        self._reservation_hashes.discard(hash_value)

    def validate_and_normalize(
        self,
        input_data: ReservationInput,
        check_availability_callback: Optional[callable] = None
    ) -> Tuple[Optional[ValidatedReservation], ValidationResult]:
        """
        Validate and normalize a reservation with optional availability check.

        Args:
            input_data: Raw reservation input
            check_availability_callback: Optional callback(datetime, party_size, duration) -> (available, message)

        Returns:
            Tuple of (ValidatedReservation or None, ValidationResult)
        """
        # Perform validation
        validated, result = validate_reservation(
            input_data,
            self._reservation_hashes,
            self.config
        )

        # If valid and callback provided, check availability
        if validated and check_availability_callback:
            try:
                is_available, availability_message = check_availability_callback(
                    validated.datetime,
                    validated.guests,
                    validated.duration_minutes
                )

                if not is_available:
                    result.add_error(ValidationError(
                        category=ValidationCategory.AVAILABILITY,
                        severity=ValidationSeverity.ERROR,
                        message=availability_message or "Time slot is not available",
                        field="datetime",
                        code="NOT_AVAILABLE"
                    ))
                    return None, result

            except Exception as e:
                logger.error(f"Availability check failed: {e}")
                result.add_error(ValidationError(
                    category=ValidationCategory.AVAILABILITY,
                    severity=ValidationSeverity.WARNING,
                    message="Could not verify availability - proceeding with caution",
                    field="datetime",
                    code="AVAILABILITY_CHECK_FAILED"
                ))

        return validated, result

    def confirm_reservation(
        self,
        validated: ValidatedReservation
    ) -> str:
        """
        Confirm a validated reservation and register for idempotency.

        Args:
            validated: Validated reservation data

        Returns:
            The idempotency hash
        """
        self._reservation_hashes.add(validated.idempotency_hash)
        logger.info(f"Registered reservation hash: {validated.idempotency_hash}")
        return validated.idempotency_hash

    def cancel_reservation(self, idempotency_hash: str):
        """
        Cancel a reservation and unregister from idempotency tracking.

        Args:
            idempotency_hash: The reservation's idempotency hash
        """
        self.unregister_reservation(idempotency_hash)
        logger.info(f"Unregistered reservation hash: {idempotency_hash}")


# Singleton instance
_validation_service_instance: Optional[ReservationValidationService] = None


def get_validation_service() -> ReservationValidationService:
    """Get or create the validation service singleton."""
    global _validation_service_instance
    if _validation_service_instance is None:
        _validation_service_instance = ReservationValidationService()
    return _validation_service_instance
