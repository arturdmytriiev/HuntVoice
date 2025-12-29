"""State management for the restaurant bot conversation graph."""
from datetime import datetime
from typing import List, Optional, Literal
from pydantic import BaseModel, Field


class ConversationState(BaseModel):
    """State for the restaurant bot conversation."""

    # Conversation tracking
    messages: List[str] = Field(default_factory=list, description="Conversation history")
    current_intent: Optional[str] = Field(None, description="Current user intent")
    last_bot_message: Optional[str] = Field(None, description="Last message from bot")

    # Reservation data
    customer_name: Optional[str] = None
    phone_number: Optional[str] = None
    party_size: Optional[int] = None
    reservation_date: Optional[str] = None  # ISO format date string
    reservation_time: Optional[str] = None  # ISO format datetime string
    reservation_id: Optional[int] = None
    notes: Optional[str] = None

    # Flow control
    stage: str = Field(default="greeting", description="Current conversation stage")
    needs_disambiguation: bool = Field(default=False, description="Whether user input needs clarification")
    disambiguation_field: Optional[str] = Field(None, description="Which field needs disambiguation")
    available_slots: List[str] = Field(default_factory=list, description="Available time slots")

    # Error handling
    error_message: Optional[str] = None
    retry_count: int = Field(default=0, description="Number of retries for current step")

    class Config:
        """Pydantic config."""
        arbitrary_types_allowed = True


class Intent(BaseModel):
    """User intent classification."""

    intent_type: Literal[
        "make_reservation",
        "cancel_reservation",
        "modify_reservation",
        "query_menu",
        "query_hours",
        "greeting",
        "farewell",
        "unclear",
    ]
    confidence: float = Field(ge=0.0, le=1.0)
    extracted_entities: dict = Field(default_factory=dict)
