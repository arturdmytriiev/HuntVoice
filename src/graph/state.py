"""
CallState definition for the restaurant bot LangGraph orchestration.
Matches the spec with slots, messages, attempts, and other required fields.
"""
from datetime import datetime
from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field


# Intent types for the voice AI bot
IntentType = Literal["MENU", "RECOMMEND", "RESERVE", "CANCEL", "HANDOFF", "UNKNOWN"]


class CallState(BaseModel):
    """
    State management for restaurant bot conversation using LangGraph.

    This state tracks the entire conversation flow including intent detection,
    slot collection, and execution of reservations/cancellations.
    """

    # ==================== Core Conversation Tracking ====================
    call_id: str = Field(default="", description="Unique call identifier")
    messages: List[str] = Field(default_factory=list, description="Full conversation history")
    current_intent: Optional[IntentType] = Field(None, description="Detected user intent")

    # ==================== Slot Collection ====================
    # Reservation slots
    customer_name: Optional[str] = None
    phone_number: Optional[str] = None
    party_size: Optional[int] = None
    reservation_date: Optional[str] = None  # ISO format date string (YYYY-MM-DD)
    reservation_time: Optional[str] = None  # Time string (HH:MM)
    special_requests: Optional[str] = None

    # Cancellation slots (3 questions: Name -> Date -> Phone/Time)
    cancel_name: Optional[str] = None
    cancel_date: Optional[str] = None
    cancel_phone_time: Optional[str] = None  # Phone number or time

    # Recommendation slots
    dietary_preferences: List[str] = Field(default_factory=list, description="Dietary restrictions")
    allergens_to_exclude: List[str] = Field(default_factory=list, description="Allergens to avoid")

    # ==================== Flow Control ====================
    current_step: str = Field(default="greeting", description="Current step in the flow")
    needs_confirmation: bool = Field(default=False, description="Whether waiting for yes/no confirmation")
    confirmation_pending_for: Optional[str] = Field(None, description="What action needs confirmation")

    # ==================== Attempts and Error Handling ====================
    attempts: Dict[str, int] = Field(
        default_factory=dict,
        description="Number of attempts per slot (e.g., {'name': 1, 'date': 2})"
    )
    max_attempts: int = Field(default=3, description="Max attempts before handoff")
    error_count: int = Field(default=0, description="Total error count")

    # ==================== Available Data ====================
    available_slots: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Available time slots for reservations"
    )
    found_reservations: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Reservations found during cancellation search"
    )
    recommended_items: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Menu items recommended to user"
    )

    # ==================== Result Tracking ====================
    reservation_id: Optional[str] = None
    cancellation_result: Optional[str] = None
    last_bot_message: Optional[str] = Field(None, description="Last message sent to user")

    # ==================== Session Metadata ====================
    session_start: Optional[datetime] = Field(
        default_factory=lambda: datetime.now(),
        description="When the call started"
    )
    is_complete: bool = Field(default=False, description="Whether the call is complete")
    handoff_reason: Optional[str] = None

    class Config:
        """Pydantic config."""
        arbitrary_types_allowed = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

    def add_message(self, message: str) -> None:
        """Add a message to conversation history."""
        self.messages.append(message)

    def increment_attempt(self, slot_name: str) -> int:
        """
        Increment attempt counter for a slot.

        Args:
            slot_name: Name of the slot (e.g., 'name', 'date')

        Returns:
            Current attempt count
        """
        if slot_name not in self.attempts:
            self.attempts[slot_name] = 0
        self.attempts[slot_name] += 1
        return self.attempts[slot_name]

    def get_attempt_count(self, slot_name: str) -> int:
        """Get attempt count for a slot."""
        return self.attempts.get(slot_name, 0)

    def should_handoff(self, slot_name: Optional[str] = None) -> bool:
        """
        Check if we should handoff to human operator.

        Args:
            slot_name: Optional specific slot to check

        Returns:
            True if should handoff
        """
        if slot_name:
            return self.get_attempt_count(slot_name) >= self.max_attempts
        return self.error_count >= self.max_attempts

    def reset_for_new_intent(self) -> None:
        """Reset state when user changes intent mid-conversation."""
        self.customer_name = None
        self.phone_number = None
        self.party_size = None
        self.reservation_date = None
        self.reservation_time = None
        self.special_requests = None
        self.cancel_name = None
        self.cancel_date = None
        self.cancel_phone_time = None
        self.dietary_preferences = []
        self.allergens_to_exclude = []
        self.attempts = {}
        self.needs_confirmation = False
        self.confirmation_pending_for = None
        self.available_slots = []
        self.found_reservations = []
        self.recommended_items = []
