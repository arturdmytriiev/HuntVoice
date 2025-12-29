"""
DateTime utilities for parsing Russian date and time inputs.
Handles natural language date/time parsing with Europe/Bratislava timezone.
"""
from datetime import datetime, timedelta, date, time
from typing import Optional, Union
import re
import pytz


# Timezone configuration
TIMEZONE = pytz.timezone('Europe/Bratislava')


# Russian day names mapping
RUSSIAN_DAYS = {
    'понедельник': 0,  # Monday
    'вторник': 1,      # Tuesday
    'среда': 2,        # Wednesday
    'среду': 2,        # Wednesday (accusative)
    'четверг': 3,      # Thursday
    'пятница': 4,      # Friday
    'пятницу': 4,      # Friday (accusative)
    'суббота': 5,      # Saturday
    'субботу': 5,      # Saturday (accusative)
    'воскресенье': 6,  # Sunday
}


def get_current_datetime() -> datetime:
    """Get current datetime in Europe/Bratislava timezone."""
    return datetime.now(TIMEZONE)


def parse_russian_date(text: str) -> Optional[date]:
    """
    Parse Russian date text into a date object.

    Supports:
    - "сегодня" (today)
    - "завтра" (tomorrow)
    - "послезавтра" (day after tomorrow)
    - "в понедельник", "в пятницу", etc. (on Monday, on Friday, etc.)
    - Day names without preposition

    Args:
        text: Russian text containing date information

    Returns:
        date object or None if parsing fails
    """
    if not text:
        return None

    text = text.lower().strip()
    current = get_current_datetime()
    current_date = current.date()

    # Handle "today"
    if 'сегодня' in text:
        return current_date

    # Handle "tomorrow"
    if 'завтра' in text and 'послезавтра' not in text:
        return current_date + timedelta(days=1)

    # Handle "day after tomorrow"
    if 'послезавтра' in text:
        return current_date + timedelta(days=2)

    # Handle day names (with or without "в")
    for day_name, day_num in RUSSIAN_DAYS.items():
        if day_name in text:
            current_weekday = current_date.weekday()
            days_ahead = day_num - current_weekday

            # If the day has already passed this week, schedule for next week
            if days_ahead <= 0:
                days_ahead += 7

            return current_date + timedelta(days=days_ahead)

    # Try to parse explicit date format (DD.MM.YYYY or DD.MM)
    date_pattern = r'(\d{1,2})\.(\d{1,2})(?:\.(\d{4}|\d{2}))?'
    match = re.search(date_pattern, text)
    if match:
        day = int(match.group(1))
        month = int(match.group(2))
        year = int(match.group(3)) if match.group(3) else current_date.year

        # Handle 2-digit year
        if match.group(3) and len(match.group(3)) == 2:
            year = 2000 + year

        try:
            return date(year, month, day)
        except ValueError:
            return None

    return None


def parse_russian_time(text: str) -> Optional[time]:
    """
    Parse Russian time text into a time object.

    Supports:
    - "19:00", "7:30" (24-hour format)
    - "семь вечера" (seven in the evening)
    - "девять утра" (nine in the morning)
    - "три часа дня" (three o'clock in the afternoon)
    - "полдень" (noon)
    - "полночь" (midnight)

    Args:
        text: Russian text containing time information

    Returns:
        time object or None if parsing fails
    """
    if not text:
        return None

    text = text.lower().strip()

    # Handle explicit time format (HH:MM or H:MM)
    time_pattern = r'(\d{1,2}):(\d{2})'
    match = re.search(time_pattern, text)
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2))
        try:
            return time(hour, minute)
        except ValueError:
            return None

    # Handle noon and midnight
    if 'полдень' in text or 'полдня' in text:
        return time(12, 0)
    if 'полночь' in text:
        return time(0, 0)

    # Russian number words
    russian_numbers = {
        'ноль': 0, 'нуль': 0,
        'один': 1, 'одного': 1, 'час': 1,
        'два': 2, 'двух': 2,
        'три': 3, 'трех': 3, 'трёх': 3,
        'четыре': 4, 'четырех': 4, 'четырёх': 4,
        'пять': 5, 'пяти': 5,
        'шесть': 6, 'шести': 6,
        'семь': 7, 'семи': 7,
        'восемь': 8, 'восьми': 8,
        'девять': 9, 'девяти': 9,
        'десять': 10, 'десяти': 10,
        'одиннадцать': 11, 'одиннадцати': 11,
        'двенадцать': 12, 'двенадцати': 12,
    }

    # Time of day modifiers
    hour = None

    # Find the number
    for word, num in russian_numbers.items():
        if word in text:
            hour = num
            break

    if hour is None:
        return None

    # Adjust based on time of day
    if 'вечера' in text or 'вечеру' in text:
        # Evening (PM) - add 12 if hour < 12
        if hour < 12:
            hour += 12
    elif 'утра' in text:
        # Morning (AM) - keep as is, but handle midnight
        if hour == 12:
            hour = 0
    elif 'дня' in text or 'днём' in text or 'дня' in text:
        # Afternoon - add 12 if hour < 12 and not exactly 12
        if hour < 12 and hour != 12:
            hour += 12
    elif 'ночи' in text:
        # Night - keep as is for small hours
        if hour == 12:
            hour = 0

    # Check for minutes (half past, quarter past, etc.)
    minute = 0
    if 'половин' in text or 'тридцать' in text:
        minute = 30
    elif 'пятнадцать' in text or 'четверть' in text:
        minute = 15
    elif 'сорок пять' in text:
        minute = 45

    try:
        return time(hour, minute)
    except ValueError:
        return None


def parse_russian_datetime(date_text: str, time_text: Optional[str] = None) -> Optional[datetime]:
    """
    Parse Russian date and time text into a datetime object.

    Args:
        date_text: Russian text containing date information
        time_text: Optional Russian text containing time information

    Returns:
        datetime object with Europe/Bratislava timezone or None if parsing fails
    """
    parsed_date = parse_russian_date(date_text)

    if parsed_date is None:
        return None

    # Default to noon if no time specified
    parsed_time = time(12, 0)

    if time_text:
        parsed_time_result = parse_russian_time(time_text)
        if parsed_time_result:
            parsed_time = parsed_time_result

    # Combine date and time
    naive_dt = datetime.combine(parsed_date, parsed_time)

    # Localize to Europe/Bratislava timezone
    localized_dt = TIMEZONE.localize(naive_dt)

    return localized_dt


def format_datetime_russian(dt: datetime) -> str:
    """
    Format datetime object to Russian-friendly string.

    Args:
        dt: datetime object

    Returns:
        Formatted string like "пятница, 29 декабря в 19:00"
    """
    # Ensure datetime is in correct timezone
    if dt.tzinfo is None:
        dt = TIMEZONE.localize(dt)
    else:
        dt = dt.astimezone(TIMEZONE)

    day_names = [
        'понедельник', 'вторник', 'среда', 'четверг',
        'пятница', 'суббота', 'воскресенье'
    ]

    month_names = [
        'января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
        'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря'
    ]

    day_name = day_names[dt.weekday()]
    month_name = month_names[dt.month - 1]

    return f"{day_name}, {dt.day} {month_name} в {dt.hour:02d}:{dt.minute:02d}"


def is_valid_reservation_time(dt: datetime) -> bool:
    """
    Check if datetime is valid for restaurant reservation.

    Args:
        dt: datetime object

    Returns:
        True if valid reservation time, False otherwise
    """
    # Ensure datetime is in correct timezone
    if dt.tzinfo is None:
        dt = TIMEZONE.localize(dt)
    else:
        dt = dt.astimezone(TIMEZONE)

    # Check if date is in the future
    if dt <= get_current_datetime():
        return False

    # Check if date is not too far in the future (e.g., 3 months)
    max_advance = get_current_datetime() + timedelta(days=90)
    if dt > max_advance:
        return False

    # Restaurant hours: 11:00 - 23:00
    if dt.hour < 11 or dt.hour >= 23:
        return False

    return True
