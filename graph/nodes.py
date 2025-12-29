"""Node functions for the LangGraph orchestration."""

import re
from typing import Literal
from .state import CallState


# ============================================================================
# INTENT DETECTION
# ============================================================================

def detect_intent_node(state: CallState) -> dict:
    """
    Detect user intent using rule-based regex patterns.

    Classifies into: MENU, RECOMMEND, RESERVE, CANCEL, or UNKNOWN.
    """
    state.current_node = "detect_intent"

    # Get the last user message
    user_messages = [msg for msg in state.messages if msg.get("role") == "user"]
    if not user_messages:
        return {
            "intent": "UNKNOWN",
            "current_node": "detect_intent",
            "attempts": {**state.attempts, "intent_detection": state.attempts["intent_detection"] + 1}
        }

    last_message = user_messages[-1].get("content", "").lower()

    # Intent patterns (order matters - more specific first)
    patterns = {
        "CANCEL": r"\b(cancel|cancellation|remove|delete|cancel.*reservation)\b",
        "RESERVE": r"\b(book|reserve|reservation|table|make.*reservation)\b",
        "RECOMMEND": r"\b(recommend|suggest|what.*good|best|popular|favorite)\b",
        "MENU": r"\b(menu|what.*have|what.*serve|dish|food|price|cost)\b",
    }

    detected_intent = "UNKNOWN"
    for intent, pattern in patterns.items():
        if re.search(pattern, last_message):
            detected_intent = intent
            break

    return {
        "intent": detected_intent,
        "current_node": "detect_intent",
        "attempts": {**state.attempts, "intent_detection": state.attempts["intent_detection"] + 1}
    }


# ============================================================================
# MENU & RECOMMENDATIONS
# ============================================================================

def menu_answer_node(state: CallState) -> dict:
    """Handle menu-related queries."""
    state.current_node = "menu_answer"

    response = {
        "role": "assistant",
        "content": "Our menu includes appetizers like bruschetta and calamari, "
                   "main courses such as pasta carbonara, grilled salmon, and ribeye steak, "
                   "and desserts like tiramisu and panna cotta. "
                   "What would you like to know more about?"
    }

    return {
        "messages": [response],
        "current_node": "menu_answer",
        "completed": True
    }


def recommend_node(state: CallState) -> dict:
    """Provide recommendations."""
    state.current_node = "recommend"

    response = {
        "role": "assistant",
        "content": "I'd highly recommend our chef's special - the pan-seared salmon "
                   "with lemon butter sauce, served with seasonal vegetables. "
                   "It's our most popular dish! Would you like to make a reservation?"
    }

    return {
        "messages": [response],
        "current_node": "recommend",
        "completed": True
    }


# ============================================================================
# RESERVATION FLOW
# ============================================================================

def make_reservation_collect_node(state: CallState) -> dict:
    """Collect reservation details (name, date, time, party size, phone)."""
    state.current_node = "make_reservation_collect"

    # Get last user message
    user_messages = [msg for msg in state.messages if msg.get("role") == "user"]
    last_message = user_messages[-1].get("content", "").lower() if user_messages else ""

    slots = state.reservation_slots.copy()

    # Extract slot values using simple regex patterns
    # Name pattern (e.g., "my name is John", "for John Smith")
    if not slots["name"]:
        name_match = re.search(r"(?:name is|for|under)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
                               user_messages[-1].get("content", ""))
        if name_match:
            slots["name"] = name_match.group(1)

    # Date pattern (e.g., "tomorrow", "Friday", "Dec 30")
    if not slots["date"]:
        date_patterns = [
            r"\b(today|tomorrow|tonight)\b",
            r"\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
            r"\b([A-Z][a-z]+\s+\d{1,2})\b",  # "Dec 30"
            r"\b(\d{1,2}/\d{1,2})\b",  # "12/30"
        ]
        for pattern in date_patterns:
            date_match = re.search(pattern, user_messages[-1].get("content", ""))
            if date_match:
                slots["date"] = date_match.group(1)
                break

    # Time pattern (e.g., "7pm", "7:00", "seven")
    if not slots["time"]:
        time_match = re.search(r"\b(\d{1,2}(?::\d{2})?\s*(?:am|pm)?|seven|eight|six)\b", last_message)
        if time_match:
            slots["time"] = time_match.group(1)

    # Party size (e.g., "2 people", "for 4", "party of 3")
    if not slots["party_size"]:
        party_match = re.search(r"\b(?:for|party of|table for)\s*(\d+)\b", last_message)
        if party_match:
            slots["party_size"] = party_match.group(1)
        elif re.search(r"\b(\d+)\s*(?:people|person|guests?)\b", last_message):
            party_match = re.search(r"\b(\d+)\s*(?:people|person|guests?)\b", last_message)
            slots["party_size"] = party_match.group(1)

    # Phone pattern
    if not slots["phone"]:
        phone_match = re.search(r"\b(\d{3}[-.]?\d{3}[-.]?\d{4})\b", last_message)
        if phone_match:
            slots["phone"] = phone_match.group(1)

    # Check which slots are still missing
    missing_slots = [k for k, v in slots.items() if v is None]

    if missing_slots:
        # Ask for the first missing slot
        prompts = {
            "name": "May I have your name for the reservation?",
            "date": "What date would you like to reserve for?",
            "time": "What time would you prefer?",
            "party_size": "How many people will be dining?",
            "phone": "Can I get a phone number for the reservation?"
        }
        response = {
            "role": "assistant",
            "content": prompts[missing_slots[0]]
        }

        return {
            "messages": [response],
            "reservation_slots": slots,
            "current_node": "make_reservation_collect",
            "attempts": {**state.attempts, "slot_collection": state.attempts["slot_collection"] + 1}
        }

    # All slots collected, move to confirmation
    return {
        "reservation_slots": slots,
        "current_node": "make_reservation_collect"
    }


def make_reservation_confirm_node(state: CallState) -> dict:
    """Confirm reservation details with user."""
    state.current_node = "make_reservation_confirm"

    slots = state.reservation_slots

    # Check if user already confirmed
    user_messages = [msg for msg in state.messages if msg.get("role") == "user"]
    if user_messages and state.user_confirmed is None:
        last_message = user_messages[-1].get("content", "").lower()

        # Check for yes/no confirmation
        if re.search(r"\b(yes|yeah|yep|correct|confirm|that's right)\b", last_message):
            return {
                "user_confirmed": True,
                "current_node": "make_reservation_confirm"
            }
        elif re.search(r"\b(no|nope|incorrect|wrong|change)\b", last_message):
            return {
                "user_confirmed": False,
                "current_node": "make_reservation_confirm",
                "messages": [{
                    "role": "assistant",
                    "content": "I understand. Let's start over. What would you like to change?"
                }],
                "reservation_slots": {
                    "name": None,
                    "date": None,
                    "time": None,
                    "party_size": None,
                    "phone": None,
                }
            }

    # Ask for confirmation
    confirmation_msg = (
        f"Let me confirm your reservation: "
        f"{slots['name']} for {slots['party_size']} people "
        f"on {slots['date']} at {slots['time']}. "
        f"Contact: {slots['phone']}. "
        f"Is this correct?"
    )

    return {
        "messages": [{"role": "assistant", "content": confirmation_msg}],
        "current_node": "make_reservation_confirm",
        "attempts": {**state.attempts, "confirmation": state.attempts["confirmation"] + 1}
    }


def make_reservation_execute_node(state: CallState) -> dict:
    """Execute the reservation (simulate DB write)."""
    state.current_node = "make_reservation_execute"

    slots = state.reservation_slots

    # Simulate reservation creation
    # In production, this would call a database/API
    success = True  # Simulate successful booking

    if success:
        response = {
            "role": "assistant",
            "content": f"Perfect! Your reservation for {slots['party_size']} people "
                      f"on {slots['date']} at {slots['time']} has been confirmed. "
                      f"We'll see you soon, {slots['name']}!"
        }
    else:
        response = {
            "role": "assistant",
            "content": "I'm sorry, but I encountered an issue creating your reservation. "
                      "Let me transfer you to a team member who can help."
        }
        return {
            "messages": [response],
            "current_node": "make_reservation_execute",
            "needs_handoff": True,
            "completed": True
        }

    return {
        "messages": [response],
        "current_node": "make_reservation_execute",
        "completed": True
    }


# ============================================================================
# CANCELLATION FLOW (3-question: Name -> Date -> Phone/Time)
# ============================================================================

def cancel_collect_3q_node(state: CallState) -> dict:
    """
    Collect cancellation info in 3-question flow: Name -> Date -> Phone/Time.

    Business rule: MUST ask in this order.
    """
    state.current_node = "cancel_collect_3q"

    # Get last user message
    user_messages = [msg for msg in state.messages if msg.get("role") == "user"]
    last_message = user_messages[-1].get("content", "") if user_messages else ""

    slots = state.cancellation_slots.copy()

    # Extract values from the latest message
    # Name
    if not slots["name"]:
        name_match = re.search(r"(?:name is|under|for)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)", last_message)
        if name_match:
            slots["name"] = name_match.group(1)

    # Date
    if slots["name"] and not slots["date"]:
        date_patterns = [
            r"\b(today|tomorrow|tonight)\b",
            r"\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
            r"\b([A-Z][a-z]+\s+\d{1,2})\b",
            r"\b(\d{1,2}/\d{1,2})\b",
        ]
        for pattern in date_patterns:
            date_match = re.search(pattern, last_message, re.IGNORECASE)
            if date_match:
                slots["date"] = date_match.group(1)
                break

    # Phone or Time (after name and date are collected)
    if slots["name"] and slots["date"]:
        # Try phone first
        if not slots["phone"]:
            phone_match = re.search(r"\b(\d{3}[-.]?\d{3}[-.]?\d{4})\b", last_message)
            if phone_match:
                slots["phone"] = phone_match.group(1)

        # Try time if no phone
        if not slots["phone"] and not slots["time"]:
            time_match = re.search(r"\b(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\b", last_message.lower())
            if time_match:
                slots["time"] = time_match.group(1)

    # Determine which question to ask next (strict order: Name -> Date -> Phone/Time)
    if not slots["name"]:
        response = {
            "role": "assistant",
            "content": "I can help you cancel your reservation. May I have the name on the reservation?"
        }
        return {
            "messages": [response],
            "cancellation_slots": slots,
            "current_node": "cancel_collect_3q"
        }

    if not slots["date"]:
        response = {
            "role": "assistant",
            "content": "Thank you. What date was your reservation for?"
        }
        return {
            "messages": [response],
            "cancellation_slots": slots,
            "current_node": "cancel_collect_3q"
        }

    if not slots["phone"] and not slots["time"]:
        response = {
            "role": "assistant",
            "content": "Got it. Can you provide either the phone number or the time of your reservation?"
        }
        return {
            "messages": [response],
            "cancellation_slots": slots,
            "current_node": "cancel_collect_3q"
        }

    # All required info collected
    return {
        "cancellation_slots": slots,
        "current_node": "cancel_collect_3q"
    }


def cancel_search_node(state: CallState) -> dict:
    """Search for matching reservations to cancel."""
    state.current_node = "cancel_search"

    slots = state.cancellation_slots

    # Simulate database search
    # In production, this would query a real database
    # For now, simulate finding matching reservations

    # Example: simulate finding matches
    mock_matches = [
        {
            "id": "res_001",
            "name": slots["name"],
            "date": slots["date"],
            "time": slots.get("time") or "7:00pm",
            "phone": slots.get("phone") or "555-0100",
            "party_size": "4"
        }
    ]

    # Filter based on provided criteria
    matches = []
    for res in mock_matches:
        if slots.get("phone") and res["phone"] != slots["phone"]:
            continue
        if slots.get("time") and res["time"] != slots["time"]:
            continue
        matches.append(res)

    return {
        "cancellation_matches": matches,
        "cancellation_search_attempted": True,
        "current_node": "cancel_search"
    }


def cancel_disambiguate_node(state: CallState) -> dict:
    """Handle multiple or no matches found."""
    state.current_node = "cancel_disambiguate"

    matches = state.cancellation_matches

    if len(matches) == 0:
        response = {
            "role": "assistant",
            "content": "I couldn't find any reservations matching that information. "
                      "Would you like me to transfer you to someone who can help?"
        }
        return {
            "messages": [response],
            "current_node": "cancel_disambiguate",
            "needs_handoff": True
        }

    if len(matches) == 1:
        # Single match - proceed to confirmation
        return {
            "current_node": "cancel_disambiguate"
        }

    # Multiple matches - ask user to clarify
    match_list = "\n".join([
        f"{i+1}. {m['date']} at {m['time']} for {m['party_size']} people"
        for i, m in enumerate(matches)
    ])

    response = {
        "role": "assistant",
        "content": f"I found multiple reservations:\n{match_list}\n"
                  "Which one would you like to cancel?"
    }

    return {
        "messages": [response],
        "current_node": "cancel_disambiguate"
    }


def cancel_confirm_node(state: CallState) -> dict:
    """Confirm cancellation with user."""
    state.current_node = "cancel_confirm"

    matches = state.cancellation_matches

    if not matches:
        return {
            "current_node": "cancel_confirm",
            "needs_handoff": True
        }

    # Get user confirmation if they haven't confirmed yet
    user_messages = [msg for msg in state.messages if msg.get("role") == "user"]
    if user_messages and state.user_confirmed is None:
        last_message = user_messages[-1].get("content", "").lower()

        if re.search(r"\b(yes|yeah|yep|correct|confirm|cancel it)\b", last_message):
            return {
                "user_confirmed": True,
                "current_node": "cancel_confirm"
            }
        elif re.search(r"\b(no|nope|don't|keep)\b", last_message):
            return {
                "user_confirmed": False,
                "current_node": "cancel_confirm",
                "messages": [{
                    "role": "assistant",
                    "content": "No problem! Your reservation will remain as scheduled. Is there anything else I can help you with?"
                }],
                "completed": True
            }

    # Ask for confirmation
    reservation = matches[0]
    confirmation_msg = (
        f"Just to confirm, you'd like to cancel the reservation for "
        f"{reservation['name']} on {reservation['date']} at {reservation['time']} "
        f"for {reservation['party_size']} people? "
        f"Please say yes or no."
    )

    return {
        "messages": [{"role": "assistant", "content": confirmation_msg}],
        "current_node": "cancel_confirm"
    }


def cancel_execute_node(state: CallState) -> dict:
    """Execute the cancellation (simulate DB delete)."""
    state.current_node = "cancel_execute"

    matches = state.cancellation_matches

    if not matches:
        return {
            "current_node": "cancel_execute",
            "needs_handoff": True,
            "completed": True
        }

    reservation = matches[0]

    # Simulate cancellation
    # In production, this would delete from database
    success = True

    if success:
        response = {
            "role": "assistant",
            "content": f"Your reservation for {reservation['date']} at {reservation['time']} "
                      f"has been successfully cancelled. We hope to see you again soon!"
        }
    else:
        response = {
            "role": "assistant",
            "content": "I'm sorry, I encountered an issue canceling your reservation. "
                      "Let me transfer you to someone who can help."
        }
        return {
            "messages": [response],
            "current_node": "cancel_execute",
            "needs_handoff": True,
            "completed": True
        }

    return {
        "messages": [response],
        "current_node": "cancel_execute",
        "completed": True
    }


# ============================================================================
# HANDOFF
# ============================================================================

def handoff_node(state: CallState) -> dict:
    """Transfer to human agent."""
    state.current_node = "handoff"

    response = {
        "role": "assistant",
        "content": "I'm transferring you to one of our team members who can better assist you. "
                  "Please hold for just a moment."
    }

    return {
        "messages": [response],
        "current_node": "handoff",
        "needs_handoff": True,
        "completed": True
    }
