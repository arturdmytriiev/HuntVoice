"""Graph-based conversation workflow service."""

import json
from typing import Dict, Any, Optional, Callable
from datetime import datetime
from enum import Enum


class ConversationStep(str, Enum):
    """Conversation step enumeration."""
    GREETING = "greeting"
    MAIN_MENU = "main_menu"
    MENU_INQUIRY = "menu_inquiry"
    RESERVATION_START = "reservation_start"
    RESERVATION_NAME = "reservation_name"
    RESERVATION_PARTY_SIZE = "reservation_party_size"
    RESERVATION_DATE = "reservation_date"
    RESERVATION_TIME = "reservation_time"
    RESERVATION_CONFIRM = "reservation_confirm"
    GOODBYE = "goodbye"


class ConversationGraph:
    """Graph-based conversation flow management."""

    def __init__(self):
        self.handlers: Dict[str, Callable] = {}
        self.state: Dict[str, Any] = {}

    def register_handler(self, step: str, handler: Callable) -> None:
        """
        Register a handler for a conversation step.

        Args:
            step: Step name
            handler: Handler function
        """
        self.handlers[step] = handler

    def process(self, current_step: str, user_input: str, state_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Process user input and determine next step.

        Args:
            current_step: Current conversation step
            user_input: User's speech input
            state_data: Current state data

        Returns:
            Dict containing next_step, message, and updated state
        """
        if state_data:
            self.state = state_data
        else:
            self.state = {}

        if current_step in self.handlers:
            return self.handlers[current_step](user_input, self.state)

        return self.default_handler(user_input, current_step)

    def default_handler(self, user_input: str, current_step: str) -> Dict[str, Any]:
        """Default handler for unregistered steps."""
        return {
            "next_step": ConversationStep.MAIN_MENU,
            "message": "I'm sorry, I didn't understand that. Let's start over.",
            "state": self.state
        }


class RestaurantBotGraph:
    """Restaurant bot conversation graph."""

    def __init__(self, menu_service):
        self.graph = ConversationGraph()
        self.menu_service = menu_service
        self._register_handlers()

    def _register_handlers(self) -> None:
        """Register all conversation handlers."""
        self.graph.register_handler(ConversationStep.GREETING, self.handle_greeting)
        self.graph.register_handler(ConversationStep.MAIN_MENU, self.handle_main_menu)
        self.graph.register_handler(ConversationStep.MENU_INQUIRY, self.handle_menu_inquiry)
        self.graph.register_handler(ConversationStep.RESERVATION_START, self.handle_reservation_start)
        self.graph.register_handler(ConversationStep.RESERVATION_NAME, self.handle_reservation_name)
        self.graph.register_handler(ConversationStep.RESERVATION_PARTY_SIZE, self.handle_reservation_party_size)
        self.graph.register_handler(ConversationStep.RESERVATION_DATE, self.handle_reservation_date)
        self.graph.register_handler(ConversationStep.RESERVATION_TIME, self.handle_reservation_time)
        self.graph.register_handler(ConversationStep.RESERVATION_CONFIRM, self.handle_reservation_confirm)

    def handle_greeting(self, user_input: str, state: Dict[str, Any]) -> Dict[str, Any]:
        """Handle greeting step."""
        message = (
            "Welcome to Hunt Restaurant! "
            "I can help you with menu information or make a reservation. "
            "What would you like to do today?"
        )
        return {
            "next_step": ConversationStep.MAIN_MENU,
            "message": message,
            "state": state
        }

    def handle_main_menu(self, user_input: str, state: Dict[str, Any]) -> Dict[str, Any]:
        """Handle main menu selection."""
        user_input_lower = user_input.lower()

        if any(word in user_input_lower for word in ["menu", "food", "eat", "dish", "meal"]):
            message = (
                "Great! I can tell you about our menu. "
                "We have appetizers, entrees, pasta, pizza, salads, and desserts. "
                "Which category would you like to hear about?"
            )
            return {
                "next_step": ConversationStep.MENU_INQUIRY,
                "message": message,
                "state": state
            }

        elif any(word in user_input_lower for word in ["reservation", "book", "table", "reserve"]):
            message = "Excellent! I'll help you make a reservation. May I have your name, please?"
            return {
                "next_step": ConversationStep.RESERVATION_NAME,
                "message": message,
                "state": state
            }

        else:
            message = (
                "I can help you with our menu or make a reservation. "
                "Would you like to hear about our menu or make a reservation?"
            )
            return {
                "next_step": ConversationStep.MAIN_MENU,
                "message": message,
                "state": state
            }

    def handle_menu_inquiry(self, user_input: str, state: Dict[str, Any]) -> Dict[str, Any]:
        """Handle menu inquiry."""
        user_input_lower = user_input.lower()
        categories = self.menu_service.get_categories()

        for category in categories:
            if category.lower() in user_input_lower:
                items = self.menu_service.get_items_by_category(category)
                items_description = ", ".join([f"{item.name} for ${item.price}" for item in items])
                message = f"In our {category} category, we have: {items_description}. Would you like to hear about another category or make a reservation?"
                return {
                    "next_step": ConversationStep.MAIN_MENU,
                    "message": message,
                    "state": state
                }

        message = "I didn't catch that category. We have appetizers, entrees, pasta, pizza, salads, and desserts. Which would you like to hear about?"
        return {
            "next_step": ConversationStep.MENU_INQUIRY,
            "message": message,
            "state": state
        }

    def handle_reservation_start(self, user_input: str, state: Dict[str, Any]) -> Dict[str, Any]:
        """Handle reservation start."""
        message = "Great! Let's make a reservation. May I have your name, please?"
        return {
            "next_step": ConversationStep.RESERVATION_NAME,
            "message": message,
            "state": state
        }

    def handle_reservation_name(self, user_input: str, state: Dict[str, Any]) -> Dict[str, Any]:
        """Handle reservation name collection."""
        state['customer_name'] = user_input
        message = f"Thank you, {user_input}. How many people will be dining with us?"
        return {
            "next_step": ConversationStep.RESERVATION_PARTY_SIZE,
            "message": message,
            "state": state
        }

    def handle_reservation_party_size(self, user_input: str, state: Dict[str, Any]) -> Dict[str, Any]:
        """Handle party size collection."""
        try:
            party_size = self._extract_number(user_input)
            if party_size and 1 <= party_size <= 50:
                state['party_size'] = party_size
                message = "Perfect! What date would you like to make the reservation? Please say the month and day."
                return {
                    "next_step": ConversationStep.RESERVATION_DATE,
                    "message": message,
                    "state": state
                }
        except:
            pass

        message = "I'm sorry, I didn't catch that. How many people will be dining?"
        return {
            "next_step": ConversationStep.RESERVATION_PARTY_SIZE,
            "message": message,
            "state": state
        }

    def handle_reservation_date(self, user_input: str, state: Dict[str, Any]) -> Dict[str, Any]:
        """Handle reservation date collection."""
        state['reservation_date'] = user_input
        message = "Great! And what time would you like to dine? Please say the hour and AM or PM."
        return {
            "next_step": ConversationStep.RESERVATION_TIME,
            "message": message,
            "state": state
        }

    def handle_reservation_time(self, user_input: str, state: Dict[str, Any]) -> Dict[str, Any]:
        """Handle reservation time collection."""
        state['reservation_time'] = user_input

        name = state.get('customer_name', 'there')
        party_size = state.get('party_size', 'your party')
        date = state.get('reservation_date', 'the requested date')
        time = state.get('reservation_time', 'the requested time')

        message = (
            f"Let me confirm your reservation. {name}, party of {party_size}, "
            f"on {date} at {time}. Is this correct? Say yes to confirm or no to cancel."
        )
        return {
            "next_step": ConversationStep.RESERVATION_CONFIRM,
            "message": message,
            "state": state
        }

    def handle_reservation_confirm(self, user_input: str, state: Dict[str, Any]) -> Dict[str, Any]:
        """Handle reservation confirmation."""
        user_input_lower = user_input.lower()

        if "yes" in user_input_lower or "correct" in user_input_lower or "confirm" in user_input_lower:
            state['confirmed'] = True
            message = (
                "Excellent! Your reservation has been confirmed. "
                "We'll send you a confirmation via text message. "
                "Thank you for choosing Hunt Restaurant. We look forward to seeing you!"
            )
            return {
                "next_step": ConversationStep.GOODBYE,
                "message": message,
                "state": state,
                "should_hangup": True
            }
        else:
            message = "No problem. Your reservation has been cancelled. Is there anything else I can help you with?"
            state['confirmed'] = False
            return {
                "next_step": ConversationStep.MAIN_MENU,
                "message": message,
                "state": state
            }

    def _extract_number(self, text: str) -> Optional[int]:
        """Extract number from text."""
        number_words = {
            'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
            'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10
        }

        text_lower = text.lower()
        for word, num in number_words.items():
            if word in text_lower:
                return num

        words = text.split()
        for word in words:
            try:
                return int(word)
            except ValueError:
                continue

        return None

    def run(self, current_step: str, user_input: str, state_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Run the conversation graph.

        Args:
            current_step: Current conversation step
            user_input: User's speech input
            state_data: Current state data

        Returns:
            Dict containing next_step, message, and updated state
        """
        return self.graph.process(current_step, user_input, state_data)
