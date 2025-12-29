"""Node functions for the restaurant bot conversation graph."""
from datetime import datetime
from typing import Optional
import re

from src.graph.state import ConversationState
from src.reservation_service import ReservationService, ReservationConflictError, ReservationNotFoundError


class ConversationNodes:
    """Collection of node functions for the conversation graph."""

    def __init__(self, reservation_service: ReservationService):
        """
        Initialize conversation nodes.

        Args:
            reservation_service: Service for managing reservations
        """
        self.reservation_service = reservation_service

    def greeting_node(self, state: ConversationState) -> ConversationState:
        """
        Handle greeting and determine initial intent.

        Args:
            state: Current conversation state

        Returns:
            Updated conversation state
        """
        if not state.messages:
            state.last_bot_message = "Welcome to HuntVoice Restaurant! How can I help you today?"
            state.stage = "intent_classification"
            return state

        user_message = state.messages[-1].lower()

        # Simple intent detection
        if any(word in user_message for word in ["reservation", "book", "table", "reserve"]):
            state.current_intent = "make_reservation"
            state.last_bot_message = "I'd be happy to help you make a reservation. May I have your name please?"
            state.stage = "collect_name"
        elif any(word in user_message for word in ["cancel", "delete", "remove"]):
            state.current_intent = "cancel_reservation"
            state.last_bot_message = "I can help you cancel a reservation. What's your phone number?"
            state.stage = "collect_phone_for_cancel"
        elif any(word in user_message for word in ["menu", "food", "eat", "serve"]):
            state.current_intent = "query_menu"
            state.stage = "respond_menu"
        else:
            state.last_bot_message = "I can help you make a reservation, cancel one, or answer questions about our menu. What would you like to do?"
            state.stage = "intent_classification"
            state.needs_disambiguation = True

        return state

    def collect_reservation_info_node(self, state: ConversationState) -> ConversationState:
        """
        Collect information needed for a reservation.

        Args:
            state: Current conversation state

        Returns:
            Updated conversation state
        """
        if not state.messages:
            return state

        user_message = state.messages[-1]

        # Collect name
        if state.stage == "collect_name":
            state.customer_name = user_message.strip()
            state.last_bot_message = "Thank you! What's the best phone number to reach you?"
            state.stage = "collect_phone"
            return state

        # Collect phone
        if state.stage == "collect_phone":
            # Simple phone validation
            phone = re.sub(r'[^0-9]', '', user_message)
            if len(phone) >= 10:
                state.phone_number = phone
                state.last_bot_message = "Great! How many people will be dining with us?"
                state.stage = "collect_party_size"
            else:
                state.last_bot_message = "I need a valid phone number. Please provide a 10-digit phone number."
                state.needs_disambiguation = True
            return state

        # Collect party size
        if state.stage == "collect_party_size":
            try:
                party_size = int(re.search(r'\d+', user_message).group())
                if party_size > 0 and party_size <= 20:
                    state.party_size = party_size
                    state.last_bot_message = "Perfect! What date would you like to make the reservation for? (e.g., 2024-03-15)"
                    state.stage = "collect_date"
                else:
                    state.last_bot_message = "We can accommodate parties of 1-20 people. How many guests?"
                    state.needs_disambiguation = True
            except (AttributeError, ValueError):
                state.last_bot_message = "I didn't catch that. How many people will be in your party?"
                state.needs_disambiguation = True
            return state

        # Collect date
        if state.stage == "collect_date":
            try:
                # Try to parse date
                date_str = user_message.strip()
                parsed_date = datetime.fromisoformat(date_str)
                state.reservation_date = parsed_date.date().isoformat()

                # Find available slots
                available_slots = self.reservation_service.find_available_slots(
                    parsed_date, state.party_size
                )

                if available_slots:
                    state.available_slots = [slot.isoformat() for slot in available_slots]
                    slots_str = ", ".join([slot.strftime("%I:%M %p") for slot in available_slots[:5]])
                    state.last_bot_message = (
                        f"Here are some available times for {state.reservation_date}: {slots_str}. "
                        f"Which time works best for you?"
                    )
                    state.stage = "collect_time"
                else:
                    state.last_bot_message = f"I'm sorry, we're fully booked on {state.reservation_date}. Can you try a different date?"
                    state.needs_disambiguation = True
            except (ValueError, AttributeError):
                state.last_bot_message = "Please provide a valid date in YYYY-MM-DD format (e.g., 2024-03-15)."
                state.needs_disambiguation = True
            return state

        # Collect time
        if state.stage == "collect_time":
            try:
                time_str = user_message.strip()
                # Try to parse as ISO format or find matching slot
                if time_str in state.available_slots:
                    state.reservation_time = time_str
                else:
                    # Try to parse as time and combine with date
                    parsed_time = datetime.fromisoformat(time_str)
                    state.reservation_time = parsed_time.isoformat()

                state.stage = "confirm_reservation"
                state.last_bot_message = self._format_confirmation_message(state)
            except (ValueError, AttributeError):
                state.last_bot_message = "Please select one of the available times or provide a time in HH:MM format."
                state.needs_disambiguation = True
            return state

        return state

    def create_reservation_node(self, state: ConversationState) -> ConversationState:
        """
        Create the reservation in the database.

        Args:
            state: Current conversation state

        Returns:
            Updated conversation state
        """
        try:
            reservation_time = datetime.fromisoformat(state.reservation_time)

            reservation = self.reservation_service.create_reservation(
                customer_name=state.customer_name,
                phone_number=state.phone_number,
                party_size=state.party_size,
                reservation_time=reservation_time,
                notes=state.notes,
            )

            state.reservation_id = reservation.id
            state.last_bot_message = (
                f"Perfect! Your reservation has been confirmed. "
                f"Reservation ID: {reservation.id}. "
                f"We'll see {state.customer_name} and {state.party_size} guests on "
                f"{reservation_time.strftime('%B %d at %I:%M %p')}. "
                f"If you need to make any changes, just let us know!"
            )
            state.stage = "completed"

        except ReservationConflictError as e:
            state.error_message = str(e)
            state.last_bot_message = f"I'm sorry, but {e} Would you like to choose a different time?"
            state.stage = "collect_time"
            state.needs_disambiguation = True

        except Exception as e:
            state.error_message = f"Unexpected error: {str(e)}"
            state.last_bot_message = "I apologize, but something went wrong. Let's try again."
            state.stage = "greeting"

        return state

    def cancel_reservation_node(self, state: ConversationState) -> ConversationState:
        """
        Handle reservation cancellation.

        Args:
            state: Current conversation state

        Returns:
            Updated conversation state
        """
        user_message = state.messages[-1] if state.messages else ""

        # Collect phone number
        if state.stage == "collect_phone_for_cancel":
            phone = re.sub(r'[^0-9]', '', user_message)
            if len(phone) >= 10:
                state.phone_number = phone

                # Search for reservations
                reservations = self.reservation_service.search_by_phone(phone)
                active_reservations = [r for r in reservations if not r.cancelled]

                if not active_reservations:
                    state.last_bot_message = "I couldn't find any active reservations with that phone number."
                    state.stage = "completed"
                elif len(active_reservations) == 1:
                    state.reservation_id = active_reservations[0].id
                    state.stage = "confirm_cancel"
                    res = active_reservations[0]
                    state.last_bot_message = (
                        f"I found a reservation for {res.customer_name} on "
                        f"{res.reservation_time.strftime('%B %d at %I:%M %p')} "
                        f"for {res.party_size} guests. Would you like to cancel this? (yes/no)"
                    )
                else:
                    res_list = "\n".join([
                        f"{i+1}. {r.customer_name} on {r.reservation_time.strftime('%B %d at %I:%M %p')} - ID: {r.id}"
                        for i, r in enumerate(active_reservations)
                    ])
                    state.last_bot_message = f"I found multiple reservations:\n{res_list}\nWhich ID would you like to cancel?"
                    state.stage = "select_reservation_to_cancel"
            else:
                state.last_bot_message = "Please provide a valid 10-digit phone number."
                state.needs_disambiguation = True
            return state

        # Confirm cancellation
        if state.stage == "confirm_cancel":
            if user_message.lower() in ["yes", "y", "confirm", "ok"]:
                try:
                    self.reservation_service.cancel_reservation(state.reservation_id)
                    state.last_bot_message = "Your reservation has been cancelled. We hope to see you another time!"
                    state.stage = "completed"
                except ReservationNotFoundError:
                    state.last_bot_message = "I couldn't find that reservation. It may have already been cancelled."
                    state.stage = "completed"
            else:
                state.last_bot_message = "No problem! Your reservation is still active. Is there anything else I can help with?"
                state.stage = "completed"
            return state

        # Select from multiple reservations
        if state.stage == "select_reservation_to_cancel":
            try:
                res_id = int(re.search(r'\d+', user_message).group())
                state.reservation_id = res_id

                reservation = self.reservation_service.get_reservation(res_id)
                state.last_bot_message = (
                    f"Cancel reservation for {reservation.customer_name} on "
                    f"{reservation.reservation_time.strftime('%B %d at %I:%M %p')}? (yes/no)"
                )
                state.stage = "confirm_cancel"
            except (AttributeError, ValueError, ReservationNotFoundError):
                state.last_bot_message = "Please provide a valid reservation ID number."
                state.needs_disambiguation = True
            return state

        return state

    def menu_query_node(self, state: ConversationState) -> ConversationState:
        """
        Respond to menu queries.

        Args:
            state: Current conversation state

        Returns:
            Updated conversation state
        """
        state.last_bot_message = (
            "We offer a diverse menu featuring:\n"
            "- Fresh seafood and steaks\n"
            "- Vegetarian and vegan options\n"
            "- Seasonal specialties\n"
            "- Full bar with craft cocktails\n\n"
            "Would you like to make a reservation?"
        )
        state.stage = "completed"
        return state

    def disambiguation_node(self, state: ConversationState) -> ConversationState:
        """
        Handle ambiguous or unclear inputs.

        Args:
            state: Current conversation state

        Returns:
            Updated conversation state
        """
        if state.retry_count >= 3:
            state.last_bot_message = (
                "I'm having trouble understanding. Let me transfer you to a team member "
                "who can better assist you. Or would you like to start over?"
            )
            state.stage = "escalate"
        else:
            state.retry_count += 1
            # Keep the same stage and last message to retry

        state.needs_disambiguation = False
        return state

    def _format_confirmation_message(self, state: ConversationState) -> str:
        """Format a confirmation message for the reservation."""
        time = datetime.fromisoformat(state.reservation_time)
        return (
            f"Let me confirm: Reservation for {state.customer_name}, "
            f"party of {state.party_size}, on {time.strftime('%B %d at %I:%M %p')}. "
            f"Is this correct? (yes/no)"
        )
