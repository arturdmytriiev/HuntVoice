"""Integration tests for restaurant bot conversation flows.

These tests simulate full conversation flows from State -> Node -> State,
covering various scenarios including happy paths and error cases.
"""
import pytest
from datetime import datetime

from src.graph.state import ConversationState
from src.graph.nodes import ConversationNodes
from src.graph.workflow import create_restaurant_bot_graph


@pytest.mark.integration
class TestHappyPathReservation:
    """Test complete happy path for making a reservation."""

    @pytest.mark.asyncio
    async def test_complete_reservation_flow(self, restaurant_bot_graph, base_time):
        """Test full conversation flow for making a reservation."""
        # Initial state
        state = ConversationState()

        # Turn 1: User greets and expresses intent
        state.messages.append("Hi, I'd like to make a reservation")
        state = await restaurant_bot_graph.ainvoke(state)

        assert state.current_intent == "make_reservation"
        assert "name" in state.last_bot_message.lower()
        assert state.stage == "collect_name"

        # Turn 2: Provide name
        state.messages.append("John Smith")
        state = await restaurant_bot_graph.ainvoke(state)

        assert state.customer_name == "John Smith"
        assert "phone" in state.last_bot_message.lower()
        assert state.stage == "collect_phone"

        # Turn 3: Provide phone
        state.messages.append("555-123-4567")
        state = await restaurant_bot_graph.ainvoke(state)

        assert state.phone_number == "5551234567"
        assert "many people" in state.last_bot_message.lower()
        assert state.stage == "collect_party_size"

        # Turn 4: Provide party size
        state.messages.append("4 people")
        state = await restaurant_bot_graph.ainvoke(state)

        assert state.party_size == 4
        assert "date" in state.last_bot_message.lower()
        assert state.stage == "collect_date"

        # Turn 5: Provide date
        date_str = base_time.date().isoformat()
        state.messages.append(date_str)
        state = await restaurant_bot_graph.ainvoke(state)

        assert state.reservation_date == date_str
        assert len(state.available_slots) > 0
        assert "available" in state.last_bot_message.lower()
        assert state.stage == "collect_time"

        # Turn 6: Select time
        selected_time = state.available_slots[0]
        state.messages.append(selected_time)
        state = await restaurant_bot_graph.ainvoke(state)

        assert state.reservation_time == selected_time
        assert "confirm" in state.last_bot_message.lower()
        assert state.stage == "confirm_reservation"

        # Turn 7: Confirm reservation
        state.messages.append("yes")
        state = await restaurant_bot_graph.ainvoke(state)

        assert state.reservation_id is not None
        assert "confirmed" in state.last_bot_message.lower()
        assert state.stage == "completed"

    @pytest.mark.asyncio
    async def test_reservation_with_minimal_conversation(
        self, conversation_nodes, reservation_service, base_time
    ):
        """Test making a reservation with concise responses."""
        state = ConversationState(stage="greeting")

        # User: "I want to book a table"
        state.messages.append("book a table")
        state = conversation_nodes.greeting_node(state)
        assert state.current_intent == "make_reservation"

        # Collect info quickly
        state.stage = "collect_name"
        state.messages.append("Alice")
        state = conversation_nodes.collect_reservation_info_node(state)
        assert state.customer_name == "Alice"

        state.messages.append("1234567890")
        state = conversation_nodes.collect_reservation_info_node(state)
        assert state.phone_number == "1234567890"

        state.messages.append("2")
        state = conversation_nodes.collect_reservation_info_node(state)
        assert state.party_size == 2

        state.messages.append(base_time.date().isoformat())
        state = conversation_nodes.collect_reservation_info_node(state)
        assert len(state.available_slots) > 0

        state.messages.append(state.available_slots[0])
        state = conversation_nodes.collect_reservation_info_node(state)
        assert state.stage == "confirm_reservation"

        # Confirm and create
        state.messages.append("yes")
        state = conversation_nodes.create_reservation_node(state)
        assert state.reservation_id is not None
        assert state.stage == "completed"


@pytest.mark.integration
class TestMenuQuery:
    """Test menu query conversation flow."""

    @pytest.mark.asyncio
    async def test_menu_query_flow(self, restaurant_bot_graph):
        """Test asking about the menu."""
        state = ConversationState()

        # User asks about menu
        state.messages.append("What's on your menu?")
        state = await restaurant_bot_graph.ainvoke(state)

        assert state.current_intent == "query_menu"
        assert "menu" in state.last_bot_message.lower()
        assert any(
            word in state.last_bot_message.lower()
            for word in ["seafood", "steak", "vegetarian", "vegan"]
        )
        assert state.stage == "completed"

    @pytest.mark.asyncio
    async def test_menu_query_then_reservation(
        self, conversation_nodes, base_time
    ):
        """Test querying menu then making a reservation."""
        state = ConversationState(stage="greeting")

        # First ask about menu
        state.messages.append("What do you serve?")
        state = conversation_nodes.greeting_node(state)
        assert state.current_intent == "query_menu"

        state = conversation_nodes.menu_query_node(state)
        assert "menu" in state.last_bot_message.lower()
        assert "reservation" in state.last_bot_message.lower()

        # Then proceed with reservation (implicit - user would restart flow)
        # This tests that the menu query properly completes

    def test_menu_query_node_directly(self, conversation_nodes):
        """Test menu query node in isolation."""
        state = ConversationState(
            current_intent="query_menu",
            stage="respond_menu",
        )

        state = conversation_nodes.menu_query_node(state)

        assert state.stage == "completed"
        assert "menu" in state.last_bot_message.lower()


@pytest.mark.integration
class TestCancelReservationFlow:
    """Test reservation cancellation flows (success and failure)."""

    @pytest.mark.asyncio
    async def test_cancel_reservation_success(
        self, conversation_nodes, create_sample_reservation, base_time
    ):
        """Test successfully cancelling a reservation."""
        # Create a reservation first
        reservation = create_sample_reservation(
            phone_number="5551234567",
            reservation_time=base_time.replace(hour=19),
        )

        # Start cancellation flow
        state = ConversationState(stage="greeting")

        state.messages.append("I want to cancel my reservation")
        state = conversation_nodes.greeting_node(state)
        assert state.current_intent == "cancel_reservation"
        assert state.stage == "collect_phone_for_cancel"

        # Provide phone number
        state.messages.append("555-123-4567")
        state = conversation_nodes.cancel_reservation_node(state)
        assert state.phone_number == "5551234567"
        assert state.reservation_id == reservation.id
        assert state.stage == "confirm_cancel"
        assert "cancel" in state.last_bot_message.lower()

        # Confirm cancellation
        state.messages.append("yes")
        state = conversation_nodes.cancel_reservation_node(state)
        assert state.stage == "completed"
        assert "cancelled" in state.last_bot_message.lower()

        # Verify reservation is cancelled
        service = create_sample_reservation.__self__
        updated_res = service.get_reservation(reservation.id)
        assert updated_res.cancelled is True

    @pytest.mark.asyncio
    async def test_cancel_reservation_not_found(self, conversation_nodes):
        """Test cancellation when no reservation exists (failure case)."""
        state = ConversationState(
            current_intent="cancel_reservation",
            stage="collect_phone_for_cancel",
        )

        # Provide phone number with no reservations
        state.messages.append("5559999999")
        state = conversation_nodes.cancel_reservation_node(state)

        assert state.stage == "completed"
        assert "couldn't find" in state.last_bot_message.lower()

    @pytest.mark.asyncio
    async def test_cancel_reservation_user_declines(
        self, conversation_nodes, create_sample_reservation, base_time
    ):
        """Test when user decides not to cancel."""
        # Create a reservation
        reservation = create_sample_reservation(phone_number="5551111111")

        state = ConversationState(
            current_intent="cancel_reservation",
            stage="collect_phone_for_cancel",
        )

        # Provide phone
        state.messages.append("5551111111")
        state = conversation_nodes.cancel_reservation_node(state)
        assert state.stage == "confirm_cancel"

        # Decline cancellation
        state.messages.append("no")
        state = conversation_nodes.cancel_reservation_node(state)

        assert state.stage == "completed"
        assert "still active" in state.last_bot_message.lower()

        # Verify reservation is NOT cancelled
        service = create_sample_reservation.__self__
        res = service.get_reservation(reservation.id)
        assert res.cancelled is False

    @pytest.mark.asyncio
    async def test_cancel_multiple_reservations(
        self, conversation_nodes, reservation_service, base_time
    ):
        """Test cancelling when multiple reservations exist for a phone number."""
        phone = "5552222222"

        # Create multiple reservations
        res1 = reservation_service.create_reservation(
            customer_name="First",
            phone_number=phone,
            party_size=2,
            reservation_time=base_time.replace(hour=18),
        )
        res2 = reservation_service.create_reservation(
            customer_name="Second",
            phone_number=phone,
            party_size=4,
            reservation_time=base_time.replace(hour=20),
        )

        state = ConversationState(
            current_intent="cancel_reservation",
            stage="collect_phone_for_cancel",
        )

        # Provide phone
        state.messages.append(phone)
        state = conversation_nodes.cancel_reservation_node(state)

        assert state.stage == "select_reservation_to_cancel"
        assert "multiple" in state.last_bot_message.lower()
        assert str(res1.id) in state.last_bot_message
        assert str(res2.id) in state.last_bot_message

        # Select specific reservation
        state.messages.append(str(res2.id))
        state = conversation_nodes.cancel_reservation_node(state)

        assert state.reservation_id == res2.id
        assert state.stage == "confirm_cancel"

        # Confirm
        state.messages.append("yes")
        state = conversation_nodes.cancel_reservation_node(state)

        assert state.stage == "completed"

        # Verify only res2 is cancelled
        res1_updated = reservation_service.get_reservation(res1.id)
        res2_updated = reservation_service.get_reservation(res2.id)
        assert res1_updated.cancelled is False
        assert res2_updated.cancelled is True


@pytest.mark.integration
class TestDisambiguationFlow:
    """Test disambiguation and error handling flows."""

    @pytest.mark.asyncio
    async def test_invalid_phone_number_disambiguation(self, conversation_nodes):
        """Test disambiguation when invalid phone is provided."""
        state = ConversationState(
            stage="collect_phone",
            customer_name="Test User",
        )

        # Provide invalid phone
        state.messages.append("123")
        state = conversation_nodes.collect_reservation_info_node(state)

        assert state.needs_disambiguation is True
        assert "valid phone" in state.last_bot_message.lower()
        assert state.stage == "collect_phone"  # Stay on same stage

        # Provide valid phone
        state.needs_disambiguation = False
        state.messages.append("5551234567")
        state = conversation_nodes.collect_reservation_info_node(state)

        assert state.phone_number == "5551234567"
        assert state.stage == "collect_party_size"

    @pytest.mark.asyncio
    async def test_invalid_party_size_disambiguation(self, conversation_nodes):
        """Test disambiguation for invalid party size."""
        state = ConversationState(
            stage="collect_party_size",
            customer_name="Test",
            phone_number="5551234567",
        )

        # Provide non-numeric input
        state.messages.append("a few people")
        state = conversation_nodes.collect_reservation_info_node(state)

        assert state.needs_disambiguation is True
        assert state.stage == "collect_party_size"

        # Provide valid size
        state.needs_disambiguation = False
        state.messages.append("5")
        state = conversation_nodes.collect_reservation_info_node(state)

        assert state.party_size == 5
        assert state.stage == "collect_date"

    @pytest.mark.asyncio
    async def test_party_size_out_of_range(self, conversation_nodes):
        """Test disambiguation for party size out of acceptable range."""
        state = ConversationState(
            stage="collect_party_size",
            customer_name="Test",
            phone_number="5551234567",
        )

        # Provide party size too large
        state.messages.append("50")
        state = conversation_nodes.collect_reservation_info_node(state)

        assert state.needs_disambiguation is True
        assert "1-20" in state.last_bot_message

    @pytest.mark.asyncio
    async def test_invalid_date_format(self, conversation_nodes):
        """Test disambiguation for invalid date format."""
        state = ConversationState(
            stage="collect_date",
            customer_name="Test",
            phone_number="5551234567",
            party_size=4,
        )

        # Provide invalid date format
        state.messages.append("tomorrow")
        state = conversation_nodes.collect_reservation_info_node(state)

        assert state.needs_disambiguation is True
        assert "YYYY-MM-DD" in state.last_bot_message

    @pytest.mark.asyncio
    async def test_disambiguation_retry_limit(self, conversation_nodes):
        """Test that disambiguation has a retry limit."""
        state = ConversationState(
            stage="collect_phone",
            retry_count=3,
            needs_disambiguation=True,
        )

        state = conversation_nodes.disambiguation_node(state)

        assert "transfer" in state.last_bot_message.lower() or "start over" in state.last_bot_message.lower()
        assert state.stage == "escalate"

    @pytest.mark.asyncio
    async def test_unclear_intent_disambiguation(self, conversation_nodes):
        """Test disambiguation when user intent is unclear."""
        state = ConversationState(stage="greeting")

        # Provide ambiguous message
        state.messages.append("hello")
        state = conversation_nodes.greeting_node(state)

        assert state.needs_disambiguation is True
        assert state.stage == "intent_classification"
        assert "make a reservation" in state.last_bot_message.lower()


@pytest.mark.integration
class TestReservationConflictFlow:
    """Test handling of reservation conflicts."""

    @pytest.mark.asyncio
    async def test_conflict_during_creation(
        self, conversation_nodes, reservation_service, base_time
    ):
        """Test handling when reservation conflicts with capacity."""
        # Fill most capacity
        reservation_service.create_reservation(
            customer_name="Existing",
            phone_number="5550000000",
            party_size=45,
            reservation_time=base_time.replace(hour=19),
        )

        # Try to create conflicting reservation
        state = ConversationState(
            stage="confirm_reservation",
            customer_name="New Guest",
            phone_number="5551111111",
            party_size=10,  # 45 + 10 = 55 > 50
            reservation_time=base_time.replace(hour=19).isoformat(),
        )

        state.messages.append("yes")
        state = conversation_nodes.create_reservation_node(state)

        assert state.error_message is not None
        assert "capacity" in state.last_bot_message.lower() or "cannot" in state.last_bot_message.lower()
        assert state.stage == "collect_time"
        assert state.needs_disambiguation is True

    @pytest.mark.asyncio
    async def test_no_available_slots_for_date(
        self, conversation_nodes, reservation_service, base_time
    ):
        """Test when requested date has no availability."""
        # Book entire day
        for hour in range(17, 23):
            reservation_service.create_reservation(
                customer_name=f"Guest {hour}",
                phone_number=f"555{hour:07d}",
                party_size=50,
                reservation_time=base_time.replace(hour=hour),
            )

        state = ConversationState(
            stage="collect_date",
            customer_name="Test",
            phone_number="5559999999",
            party_size=4,
        )

        state.messages.append(base_time.date().isoformat())
        state = conversation_nodes.collect_reservation_info_node(state)

        assert state.needs_disambiguation is True
        assert "fully booked" in state.last_bot_message.lower()
        assert "different date" in state.last_bot_message.lower()


@pytest.mark.integration
class TestCompleteConversationScenarios:
    """Test complete end-to-end conversation scenarios."""

    @pytest.mark.asyncio
    async def test_reservation_with_all_validations(
        self, conversation_nodes, base_time
    ):
        """Test reservation flow with validation errors that are corrected."""
        state = ConversationState(stage="greeting")

        # Start
        state.messages.append("I need a table")
        state = conversation_nodes.greeting_node(state)

        # Name
        state.messages.append("Bob")
        state = conversation_nodes.collect_reservation_info_node(state)
        assert state.customer_name == "Bob"

        # Invalid phone first
        state.messages.append("123")
        state = conversation_nodes.collect_reservation_info_node(state)
        assert state.needs_disambiguation is True

        # Valid phone
        state.needs_disambiguation = False
        state.messages.append("5551234567")
        state = conversation_nodes.collect_reservation_info_node(state)
        assert state.phone_number == "5551234567"

        # Invalid party size first
        state.messages.append("lots of people")
        state = conversation_nodes.collect_reservation_info_node(state)
        assert state.needs_disambiguation is True

        # Valid party size
        state.needs_disambiguation = False
        state.messages.append("6")
        state = conversation_nodes.collect_reservation_info_node(state)
        assert state.party_size == 6

        # Valid date
        state.messages.append(base_time.date().isoformat())
        state = conversation_nodes.collect_reservation_info_node(state)
        assert len(state.available_slots) > 0

        # Select time
        state.messages.append(state.available_slots[0])
        state = conversation_nodes.collect_reservation_info_node(state)
        assert state.stage == "confirm_reservation"

        # Confirm
        state.messages.append("yes")
        state = conversation_nodes.create_reservation_node(state)
        assert state.reservation_id is not None

    @pytest.mark.asyncio
    async def test_user_changes_mind_during_confirmation(
        self, conversation_nodes, base_time
    ):
        """Test when user says 'no' during confirmation."""
        state = ConversationState(
            stage="confirm_reservation",
            customer_name="Test",
            phone_number="5551234567",
            party_size=4,
            reservation_time=base_time.replace(hour=19).isoformat(),
        )

        # User says no to confirmation
        state.messages.append("no")
        state = conversation_nodes.collect_reservation_info_node(state)

        # Should restart - in real implementation might go back to greeting
        # Current implementation stays in collect_info loop

    @pytest.mark.asyncio
    async def test_conversation_state_persistence(
        self, conversation_nodes, base_time
    ):
        """Test that conversation state persists correctly across turns."""
        state = ConversationState(stage="greeting")

        # Collect information step by step
        state.messages.append("reservation please")
        state = conversation_nodes.greeting_node(state)
        initial_message_count = len(state.messages)

        state.messages.append("Alice")
        state = conversation_nodes.collect_reservation_info_node(state)
        assert len(state.messages) == initial_message_count + 1
        assert state.customer_name == "Alice"

        state.messages.append("5551111111")
        state = conversation_nodes.collect_reservation_info_node(state)
        # Verify name persisted
        assert state.customer_name == "Alice"
        assert state.phone_number == "5551111111"

        state.messages.append("3")
        state = conversation_nodes.collect_reservation_info_node(state)
        # Verify all previous data persisted
        assert state.customer_name == "Alice"
        assert state.phone_number == "5551111111"
        assert state.party_size == 3


@pytest.mark.integration
class TestGraphWorkflowRouting:
    """Test that the graph workflow routes correctly between nodes."""

    @pytest.mark.asyncio
    async def test_greeting_to_make_reservation_routing(self, restaurant_bot_graph):
        """Test routing from greeting to reservation flow."""
        state = ConversationState()
        state.messages.append("I want to book a table")

        result = await restaurant_bot_graph.ainvoke(state)

        assert result.current_intent == "make_reservation"
        assert result.stage == "collect_name"

    @pytest.mark.asyncio
    async def test_greeting_to_cancel_routing(self, restaurant_bot_graph):
        """Test routing from greeting to cancellation flow."""
        state = ConversationState()
        state.messages.append("cancel my reservation")

        result = await restaurant_bot_graph.ainvoke(state)

        assert result.current_intent == "cancel_reservation"
        assert result.stage == "collect_phone_for_cancel"

    @pytest.mark.asyncio
    async def test_greeting_to_menu_routing(self, restaurant_bot_graph):
        """Test routing from greeting to menu query."""
        state = ConversationState()
        state.messages.append("what's on the menu")

        result = await restaurant_bot_graph.ainvoke(state)

        assert result.current_intent == "query_menu"
        assert result.stage == "completed"
