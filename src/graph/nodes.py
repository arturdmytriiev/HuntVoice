"""
Node functions for the restaurant bot LangGraph orchestration.
Includes intent detection, menu queries, recommendations, reservations, and cancellations.
"""
import re
from datetime import datetime, timedelta
from typing import Dict, Any
import logging

from src.graph.state import CallState
from services.reservation_service import ReservationService, get_reservation_service
from services.menu_service import MenuService, get_menu_service
from services.recommender_service import RecommenderService, get_recommender_service
from core.utils_datetime import TIMEZONE

logger = logging.getLogger(__name__)


# ==================== Intent Detection ====================

def detect_intent_node(state: CallState) -> CallState:
    """
    Detect user intent using rule-based regex logic.

    Classifies intent into: MENU, RECOMMEND, RESERVE, CANCEL, HANDOFF, UNKNOWN

    Args:
        state: Current call state

    Returns:
        Updated state with detected intent
    """
    if not state.messages:
        state.current_intent = "UNKNOWN"
        state.last_bot_message = "Добро пожаловать в ресторан HuntVoice! Как я могу вам помочь?"
        state.current_step = "detect_intent"
        return state

    # Get the last user message
    user_message = state.messages[-1].lower()

    # Intent patterns (regex-based)
    patterns = {
        "RESERVE": [
            r"\b(забронировать|бронь|бронирование|резерв|столик|reserve|book|table)\b",
            r"\b(хочу|нужен|можно)\s+(столик|стол|место)\b",
        ],
        "CANCEL": [
            r"\b(отменить|отмена|cancel|remove|delete)\b",
            r"\b(удалить|убрать)\s+(бронь|бронирование|reservation)\b",
        ],
        "MENU": [
            r"\b(меню|menu|что\s+есть|блюда|еда|food|dishes)\b",
            r"\b(что\s+у\s+вас|какие\s+блюда|что\s+можно)\b",
        ],
        "RECOMMEND": [
            r"\b(посоветуй|посоветовать|рекомендуй|рекомендовать|recommend|suggest)\b",
            r"\b(что\s+лучше|что\s+взять|что\s+заказать)\b",
            r"\b(специальное|special|chef|шеф)\b",
        ],
        "HANDOFF": [
            r"\b(оператор|человек|сотрудник|operator|human|person|agent)\b",
            r"\b(не\s+понимаю|не\s+работает|проблема|complaint)\b",
        ],
    }

    # Check each intent pattern
    detected_intent = "UNKNOWN"
    for intent, pattern_list in patterns.items():
        for pattern in pattern_list:
            if re.search(pattern, user_message):
                detected_intent = intent
                break
        if detected_intent != "UNKNOWN":
            break

    state.current_intent = detected_intent

    # Set appropriate next step based on intent
    if detected_intent == "MENU":
        state.current_step = "menu_answer"
        state.last_bot_message = None  # Will be set by menu_answer_node
    elif detected_intent == "RECOMMEND":
        state.current_step = "recommend"
        state.last_bot_message = None  # Will be set by recommend_node
    elif detected_intent == "RESERVE":
        state.current_step = "reserve_collect"
        state.last_bot_message = "Отлично! Давайте забронируем столик. Как вас зовут?"
    elif detected_intent == "CANCEL":
        state.current_step = "cancel_collect_name"
        state.last_bot_message = "Я помогу отменить бронирование. Скажите, пожалуйста, на чье имя бронь?"
    elif detected_intent == "HANDOFF":
        state.current_step = "handoff"
        state.handoff_reason = "User requested human operator"
    else:
        state.current_step = "detect_intent"
        state.last_bot_message = (
            "Извините, я не совсем понял. Вы хотите забронировать столик, отменить бронь, "
            "узнать о меню или получить рекомендации?"
        )
        state.error_count += 1

    logger.info(f"Detected intent: {detected_intent}")
    return state


# ==================== Menu ====================

def menu_answer_node(state: CallState) -> CallState:
    """
    Answer menu-related queries.

    Args:
        state: Current call state

    Returns:
        Updated state with menu information
    """
    menu_service = get_menu_service()

    try:
        # Get menu summary
        summary = menu_service.get_menu_summary()
        categories = menu_service.get_categories()

        category_names = ", ".join([cat['name'] for cat in categories])

        state.last_bot_message = (
            f"В нашем меню {summary['total_items']} блюд в категориях: {category_names}. "
            f"Цены от {summary['price_range']['min']:.0f} до {summary['price_range']['max']:.0f} рублей. "
            f"Хотите узнать подробнее о какой-то категории или получить рекомендации?"
        )
        state.current_step = "menu_answered"
        state.is_complete = True

    except Exception as e:
        logger.error(f"Error in menu_answer_node: {e}")
        state.last_bot_message = "Извините, произошла ошибка при получении меню. Могу я помочь вам с чем-то еще?"
        state.error_count += 1
        state.current_step = "error"

    return state


# ==================== Recommendations ====================

def recommend_node(state: CallState) -> CallState:
    """
    Provide menu recommendations based on user preferences.

    Args:
        state: Current call state

    Returns:
        Updated state with recommendations
    """
    recommender_service = get_recommender_service()

    try:
        # Get recommendations based on any collected preferences
        recommendations = recommender_service.recommend_chef_specials(limit=3)

        if recommendations:
            state.recommended_items = [
                {
                    'name': item['name'],
                    'price': item['price'],
                    'description': item.get('description', '')
                }
                for item in recommendations
            ]

            items_text = "\n".join([
                f"- {item['name']} ({item['price']:.0f} руб)"
                for item in recommendations
            ])

            state.last_bot_message = (
                f"Рекомендую попробовать наши специальные блюда:\n{items_text}\n"
                f"Хотите забронировать столик?"
            )
        else:
            state.last_bot_message = "К сожалению, сейчас нет доступных рекомендаций. Могу помочь с бронированием?"

        state.current_step = "recommend_done"
        state.is_complete = True

    except Exception as e:
        logger.error(f"Error in recommend_node: {e}")
        state.last_bot_message = "Извините, произошла ошибка. Могу помочь с бронированием столика?"
        state.error_count += 1
        state.current_step = "error"

    return state


# ==================== Make Reservation ====================

def make_reservation_collect_node(state: CallState) -> CallState:
    """
    Collect reservation information step-by-step.

    Collects: name, phone, party_size, date, time

    Args:
        state: Current call state

    Returns:
        Updated state with collected slot data
    """
    if not state.messages:
        return state

    user_message = state.messages[-1]

    # Collect name
    if state.current_step == "reserve_collect" and not state.customer_name:
        state.customer_name = user_message.strip()
        state.last_bot_message = f"Приятно познакомиться, {state.customer_name}! Какой у вас номер телефона?"
        state.current_step = "reserve_collect_phone"
        return state

    # Collect phone
    if state.current_step == "reserve_collect_phone" and not state.phone_number:
        phone = re.sub(r'[^0-9+]', '', user_message)
        if len(phone) >= 10:
            state.phone_number = phone
            state.last_bot_message = "Спасибо! Сколько человек будет?"
            state.current_step = "reserve_collect_party"
        else:
            attempts = state.increment_attempt("phone")
            if state.should_handoff("phone"):
                state.current_step = "handoff"
                state.handoff_reason = "Failed to collect phone number"
            else:
                state.last_bot_message = "Пожалуйста, укажите корректный номер телефона (минимум 10 цифр)."
        return state

    # Collect party size
    if state.current_step == "reserve_collect_party" and not state.party_size:
        try:
            match = re.search(r'\d+', user_message)
            if match:
                party_size = int(match.group())
                if 1 <= party_size <= 20:
                    state.party_size = party_size
                    state.last_bot_message = "Отлично! На какую дату бронируем? (например, 2024-12-30 или завтра)"
                    state.current_step = "reserve_collect_date"
                else:
                    state.last_bot_message = "Мы можем принять группы от 1 до 20 человек. Сколько вас будет?"
            else:
                raise ValueError("No number found")
        except (ValueError, AttributeError):
            attempts = state.increment_attempt("party_size")
            if state.should_handoff("party_size"):
                state.current_step = "handoff"
                state.handoff_reason = "Failed to collect party size"
            else:
                state.last_bot_message = "Пожалуйста, укажите количество гостей числом."
        return state

    # Collect date
    if state.current_step == "reserve_collect_date" and not state.reservation_date:
        try:
            # Parse date from user input
            date_str = user_message.strip().lower()

            if "завтра" in date_str or "tomorrow" in date_str:
                target_date = datetime.now(TIMEZONE) + timedelta(days=1)
            elif "сегодня" in date_str or "today" in date_str:
                target_date = datetime.now(TIMEZONE)
            else:
                # Try to parse ISO format
                target_date = datetime.fromisoformat(date_str.split()[0])
                if target_date.tzinfo is None:
                    target_date = TIMEZONE.localize(target_date)

            state.reservation_date = target_date.date().isoformat()

            # Find available slots
            reservation_service = get_reservation_service()
            available = reservation_service.find_availability(target_date, state.party_size)

            if available:
                state.available_slots = available[:5]  # Top 5 slots
                times = ", ".join([slot['time'] for slot in state.available_slots])
                state.last_bot_message = (
                    f"На {state.reservation_date} есть свободные места в: {times}. "
                    f"Какое время вам удобно?"
                )
                state.current_step = "reserve_collect_time"
            else:
                state.last_bot_message = (
                    f"К сожалению, на {state.reservation_date} нет свободных мест. "
                    f"Попробуйте другую дату?"
                )
                state.reservation_date = None

        except Exception as e:
            logger.error(f"Date parsing error: {e}")
            attempts = state.increment_attempt("date")
            if state.should_handoff("date"):
                state.current_step = "handoff"
                state.handoff_reason = "Failed to collect date"
            else:
                state.last_bot_message = "Пожалуйста, укажите дату в формате YYYY-MM-DD или скажите 'завтра'."
        return state

    # Collect time
    if state.current_step == "reserve_collect_time" and not state.reservation_time:
        try:
            time_str = user_message.strip()

            # Try to find time in HH:MM format
            time_match = re.search(r'(\d{1,2})[:\.](\d{2})', time_str)
            if time_match:
                hour = int(time_match.group(1))
                minute = int(time_match.group(2))
                state.reservation_time = f"{hour:02d}:{minute:02d}"
            else:
                # Check if it matches one of the available slots
                for slot in state.available_slots:
                    if slot['time'] in time_str:
                        state.reservation_time = slot['time']
                        break

            if state.reservation_time:
                state.current_step = "reserve_confirm"
                state.needs_confirmation = True
                state.confirmation_pending_for = "reservation"
                # Will be handled by confirm node
            else:
                raise ValueError("Time not found")

        except (ValueError, AttributeError):
            attempts = state.increment_attempt("time")
            if state.should_handoff("time"):
                state.current_step = "handoff"
                state.handoff_reason = "Failed to collect time"
            else:
                state.last_bot_message = "Пожалуйста, укажите время в формате ЧЧ:ММ или выберите из предложенных."
        return state

    return state


def make_reservation_confirm_node(state: CallState) -> CallState:
    """
    Confirm reservation details with user before executing.

    BUSINESS RULE: Never create without Yes/No confirmation.

    Args:
        state: Current call state

    Returns:
        Updated state after confirmation
    """
    if state.current_step == "reserve_confirm" and state.needs_confirmation:
        # First time in confirm - ask for confirmation
        if state.last_bot_message is None or "подтвердить" not in state.last_bot_message.lower():
            state.last_bot_message = (
                f"Давайте подтверждаю: бронь на имя {state.customer_name}, "
                f"{state.party_size} человек, {state.reservation_date} в {state.reservation_time}. "
                f"Всё верно? (да/нет)"
            )
            return state

        # Check user's confirmation response
        if state.messages:
            user_response = state.messages[-1].lower()

            if any(word in user_response for word in ["да", "yes", "верно", "правильно", "подтверждаю"]):
                state.needs_confirmation = False
                state.current_step = "reserve_execute"
            elif any(word in user_response for word in ["нет", "no", "не верно", "неправильно"]):
                state.needs_confirmation = False
                state.reset_for_new_intent()
                state.current_intent = "RESERVE"
                state.current_step = "reserve_collect"
                state.last_bot_message = "Хорошо, давайте начнем заново. Как вас зовут?"
            else:
                state.last_bot_message = "Пожалуйста, ответьте 'да' или 'нет'."

    return state


def make_reservation_execute_node(state: CallState) -> CallState:
    """
    Execute the reservation creation in the database.

    Args:
        state: Current call state

    Returns:
        Updated state with reservation result
    """
    reservation_service = get_reservation_service()

    try:
        # Combine date and time
        reservation_datetime = datetime.fromisoformat(
            f"{state.reservation_date} {state.reservation_time}"
        )
        if reservation_datetime.tzinfo is None:
            reservation_datetime = TIMEZONE.localize(reservation_datetime)

        # Create reservation
        success, reservation, error = reservation_service.create_reservation(
            customer_name=state.customer_name,
            customer_phone=state.phone_number,
            reservation_datetime=reservation_datetime,
            party_size=state.party_size,
            special_requests=state.special_requests
        )

        if success:
            state.reservation_id = reservation.id
            state.last_bot_message = (
                f"Отлично! Ваш столик забронирован. Номер брони: {reservation.id}. "
                f"Ждем вас {state.reservation_date} в {state.reservation_time}. "
                f"Если нужно что-то изменить, позвоните нам!"
            )
            state.current_step = "reserve_complete"
            state.is_complete = True
            logger.info(f"Reservation created: {reservation.id}")
        else:
            state.last_bot_message = f"К сожалению, не удалось создать бронь: {error}. Попробуем другое время?"
            state.reservation_date = None
            state.reservation_time = None
            state.available_slots = []
            state.current_step = "reserve_collect_date"

    except Exception as e:
        logger.error(f"Error executing reservation: {e}")
        state.last_bot_message = "Извините, произошла ошибка. Давайте попробуем еще раз или я переведу вас на оператора."
        state.error_count += 1
        state.current_step = "error"

    return state


# ==================== Cancel Reservation ====================

def cancel_collect_3q_node(state: CallState) -> CallState:
    """
    Collect cancellation info using 3 questions: Name -> Date -> Phone/Time.

    BUSINESS RULE: Cancel flow MUST ask Name -> Date -> Phone/Time.

    Args:
        state: Current call state

    Returns:
        Updated state with cancellation search criteria
    """
    if not state.messages:
        return state

    user_message = state.messages[-1]

    # Question 1: Collect Name
    if state.current_step == "cancel_collect_name" and not state.cancel_name:
        state.cancel_name = user_message.strip()
        state.last_bot_message = "На какую дату было бронирование?"
        state.current_step = "cancel_collect_date"
        return state

    # Question 2: Collect Date
    if state.current_step == "cancel_collect_date" and not state.cancel_date:
        try:
            date_str = user_message.strip().lower()

            if "завтра" in date_str:
                target_date = datetime.now(TIMEZONE) + timedelta(days=1)
            elif "сегодня" in date_str:
                target_date = datetime.now(TIMEZONE)
            else:
                target_date = datetime.fromisoformat(date_str.split()[0])
                if target_date.tzinfo is None:
                    target_date = TIMEZONE.localize(target_date)

            state.cancel_date = target_date.date().isoformat()
            state.last_bot_message = "И последний вопрос: какой номер телефона или время бронирования?"
            state.current_step = "cancel_collect_phone_time"

        except Exception as e:
            logger.error(f"Date parsing error: {e}")
            attempts = state.increment_attempt("cancel_date")
            if state.should_handoff("cancel_date"):
                state.current_step = "handoff"
                state.handoff_reason = "Failed to collect cancellation date"
            else:
                state.last_bot_message = "Пожалуйста, укажите дату в формате YYYY-MM-DD."
        return state

    # Question 3: Collect Phone or Time
    if state.current_step == "cancel_collect_phone_time" and not state.cancel_phone_time:
        state.cancel_phone_time = user_message.strip()
        state.current_step = "cancel_search"
        return state

    return state


def cancel_search_node(state: CallState) -> CallState:
    """
    Search for reservations matching cancellation criteria.

    Args:
        state: Current call state

    Returns:
        Updated state with found reservations
    """
    reservation_service = get_reservation_service()

    try:
        # Parse the date
        search_date = datetime.fromisoformat(state.cancel_date)
        if search_date.tzinfo is None:
            search_date = TIMEZONE.localize(search_date)

        # Search by name and date first
        found = reservation_service.find_reservations(
            customer_name=state.cancel_name,
            date=search_date
        )

        # Filter by phone or time if provided
        phone_time = state.cancel_phone_time
        filtered = []

        for res in found:
            if res.status == "cancelled":
                continue

            # Check if phone or time matches
            phone_match = re.sub(r'[^0-9+]', '', phone_time)
            if phone_match and phone_match in res.customer_phone:
                filtered.append(res)
            else:
                # Try to match time
                time_match = re.search(r'(\d{1,2})[:\.](\d{2})', phone_time)
                if time_match:
                    target_time = f"{int(time_match.group(1)):02d}:{int(time_match.group(2)):02d}"
                    res_time = res.datetime.strftime("%H:%M")
                    if target_time == res_time:
                        filtered.append(res)

        if not filtered:
            # If no match with phone/time filter, use all from name+date
            filtered = [r for r in found if r.status != "cancelled"]

        state.found_reservations = [
            {
                'id': res.id,
                'name': res.customer_name,
                'datetime': res.datetime.isoformat(),
                'party_size': res.party_size,
                'phone': res.customer_phone
            }
            for res in filtered
        ]

        if not state.found_reservations:
            state.last_bot_message = "Не нашел бронирований с такими данными. Проверьте информацию и попробуйте еще раз."
            state.current_step = "cancel_not_found"
            state.is_complete = True
        elif len(state.found_reservations) == 1:
            # Exactly one found - proceed to confirm
            state.current_step = "cancel_confirm"
        else:
            # Multiple found - need disambiguation
            state.current_step = "cancel_disambiguate"

        logger.info(f"Found {len(state.found_reservations)} reservations for cancellation")

    except Exception as e:
        logger.error(f"Error searching reservations: {e}")
        state.last_bot_message = "Произошла ошибка при поиске бронирования. Попробуйте еще раз."
        state.error_count += 1
        state.current_step = "error"

    return state


def cancel_disambiguate_node(state: CallState) -> CallState:
    """
    Handle disambiguation when multiple reservations are found.

    Args:
        state: Current call state

    Returns:
        Updated state after user selects reservation
    """
    if not state.found_reservations:
        state.current_step = "error"
        return state

    # First time - present options
    if "выберите" not in (state.last_bot_message or "").lower():
        options = []
        for i, res in enumerate(state.found_reservations, 1):
            dt = datetime.fromisoformat(res['datetime'])
            options.append(
                f"{i}. {res['name']}, {dt.strftime('%d.%m.%Y %H:%M')}, {res['party_size']} чел."
            )

        state.last_bot_message = (
            f"Нашел несколько бронирований:\n" + "\n".join(options) +
            f"\nКакое нужно отменить? Назовите номер."
        )
        return state

    # User has responded - parse selection
    if state.messages:
        user_message = state.messages[-1]
        try:
            # Try to extract number
            match = re.search(r'\d+', user_message)
            if match:
                selection = int(match.group()) - 1  # 0-indexed
                if 0 <= selection < len(state.found_reservations):
                    # Keep only the selected reservation
                    selected = state.found_reservations[selection]
                    state.found_reservations = [selected]
                    state.current_step = "cancel_confirm"
                else:
                    state.last_bot_message = f"Пожалуйста, выберите номер от 1 до {len(state.found_reservations)}."
            else:
                raise ValueError("No number found")
        except (ValueError, IndexError):
            attempts = state.increment_attempt("disambiguate")
            if state.should_handoff("disambiguate"):
                state.current_step = "handoff"
                state.handoff_reason = "Failed to disambiguate reservation"
            else:
                state.last_bot_message = "Пожалуйста, укажите номер бронирования."

    return state


def cancel_confirm_node(state: CallState) -> CallState:
    """
    Confirm cancellation with user before executing.

    BUSINESS RULE: Never cancel without Yes/No confirmation.

    Args:
        state: Current call state

    Returns:
        Updated state after confirmation
    """
    if not state.found_reservations:
        state.current_step = "error"
        return state

    reservation = state.found_reservations[0]

    # First time in confirm - ask for confirmation
    if state.current_step == "cancel_confirm" and not state.needs_confirmation:
        dt = datetime.fromisoformat(reservation['datetime'])
        state.last_bot_message = (
            f"Подтвердите отмену бронирования: {reservation['name']}, "
            f"{dt.strftime('%d.%m.%Y в %H:%M')}, {reservation['party_size']} человек. "
            f"Отменить? (да/нет)"
        )
        state.needs_confirmation = True
        state.confirmation_pending_for = "cancellation"
        return state

    # Check user's confirmation response
    if state.needs_confirmation and state.messages:
        user_response = state.messages[-1].lower()

        if any(word in user_response for word in ["да", "yes", "отменить", "подтверждаю"]):
            state.needs_confirmation = False
            state.current_step = "cancel_execute"
        elif any(word in user_response for word in ["нет", "no", "не надо"]):
            state.needs_confirmation = False
            state.last_bot_message = "Хорошо, бронирование сохранено. Могу я помочь с чем-то еще?"
            state.current_step = "cancel_declined"
            state.is_complete = True
        else:
            state.last_bot_message = "Пожалуйста, ответьте 'да' или 'нет'."

    return state


def cancel_execute_node(state: CallState) -> CallState:
    """
    Execute the reservation cancellation in the database.

    Args:
        state: Current call state

    Returns:
        Updated state with cancellation result
    """
    reservation_service = get_reservation_service()

    if not state.found_reservations:
        state.current_step = "error"
        return state

    try:
        reservation_id = state.found_reservations[0]['id']

        success, error = reservation_service.cancel_reservation(
            reservation_id=reservation_id,
            reason="Cancelled via voice bot"
        )

        if success:
            state.cancellation_result = "success"
            state.last_bot_message = (
                f"Бронирование {reservation_id} успешно отменено. "
                f"Будем рады видеть вас в другой раз!"
            )
            state.current_step = "cancel_complete"
            state.is_complete = True
            logger.info(f"Reservation cancelled: {reservation_id}")
        else:
            state.cancellation_result = "failed"
            state.last_bot_message = f"Не удалось отменить бронирование: {error}"
            state.current_step = "cancel_error"
            state.is_complete = True

    except Exception as e:
        logger.error(f"Error executing cancellation: {e}")
        state.last_bot_message = "Произошла ошибка при отмене бронирования. Свяжитесь с нами напрямую."
        state.error_count += 1
        state.current_step = "error"

    return state


# ==================== Handoff ====================

def handoff_node(state: CallState) -> CallState:
    """
    Handoff to human operator when bot cannot proceed.

    Args:
        state: Current call state

    Returns:
        Updated state for handoff
    """
    state.last_bot_message = (
        "Сейчас я переведу вас на нашего сотрудника, который сможет лучше помочь. "
        "Пожалуйста, подождите..."
    )
    state.current_step = "handoff_complete"
    state.is_complete = True

    logger.info(f"Handoff initiated. Reason: {state.handoff_reason or 'unknown'}")
    return state
