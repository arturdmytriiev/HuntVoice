"""State definition for LangGraph orchestration."""

from typing import Annotated, Literal, Optional
from pydantic import BaseModel, Field
from langgraph.graph import add_messages


class CallState(BaseModel):
    """
    State for the Voice AI Restaurant Bot conversation.

    Tracks all conversation context including user intent, slot values,
    messages, and flow control flags.
    """

    # Conversation messages (accumulated via add_messages reducer)
    messages: Annotated[list[dict], add_messages] = Field(
        default_factory=list,
        description="Full conversation history between user and bot"
    )

    # Intent classification
    intent: Optional[Literal["MENU", "RECOMMEND", "RESERVE", "CANCEL", "UNKNOWN"]] = Field(
        default=None,
        description="Detected user intent from the conversation"
    )

    # Slot tracking for reservations
    reservation_slots: dict[str, Optional[str]] = Field(
        default_factory=lambda: {
            "name": None,
            "date": None,
            "time": None,
            "party_size": None,
            "phone": None,
        },
        description="Slot values for making a reservation"
    )

    # Slot tracking for cancellations (3-question flow: Name -> Date -> Phone/Time)
    cancellation_slots: dict[str, Optional[str]] = Field(
        default_factory=lambda: {
            "name": None,
            "date": None,
            "phone": None,
            "time": None,
        },
        description="Slot values for canceling a reservation"
    )

    # Cancellation flow state
    cancellation_matches: list[dict] = Field(
        default_factory=list,
        description="List of matching reservations found for cancellation"
    )

    cancellation_search_attempted: bool = Field(
        default=False,
        description="Whether we've searched for reservations to cancel"
    )

    # Attempt counters for retry logic
    attempts: dict[str, int] = Field(
        default_factory=lambda: {
            "intent_detection": 0,
            "slot_collection": 0,
            "confirmation": 0,
            "execution": 0,
        },
        description="Retry attempt counters for various operations"
    )

    # Confirmation flags
    user_confirmed: Optional[bool] = Field(
        default=None,
        description="User's confirmation response (Yes/No)"
    )

    # Flow control
    current_node: Optional[str] = Field(
        default=None,
        description="Current node in the graph for debugging"
    )

    needs_handoff: bool = Field(
        default=False,
        description="Flag to trigger handoff to human agent"
    )

    # Completion flag
    completed: bool = Field(
        default=False,
        description="Whether the conversation flow is complete"
    )

    # Error tracking
    last_error: Optional[str] = Field(
        default=None,
        description="Last error message for debugging"
    )

    class Config:
        arbitrary_types_allowed = True
