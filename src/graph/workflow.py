"""Workflow definition for the restaurant bot conversation graph."""
from typing import Literal
from langgraph.graph import StateGraph, END

from src.graph.state import ConversationState
from src.graph.nodes import ConversationNodes
from src.reservation_service import ReservationService


def create_restaurant_bot_graph(reservation_service: ReservationService) -> StateGraph:
    """
    Create the conversation graph for the restaurant bot.

    Args:
        reservation_service: Service for managing reservations

    Returns:
        Compiled StateGraph
    """
    # Initialize nodes
    nodes = ConversationNodes(reservation_service)

    # Create graph
    workflow = StateGraph(ConversationState)

    # Add nodes
    workflow.add_node("greeting", nodes.greeting_node)
    workflow.add_node("collect_info", nodes.collect_reservation_info_node)
    workflow.add_node("create_reservation", nodes.create_reservation_node)
    workflow.add_node("cancel_reservation", nodes.cancel_reservation_node)
    workflow.add_node("menu_query", nodes.menu_query_node)
    workflow.add_node("disambiguation", nodes.disambiguation_node)

    # Set entry point
    workflow.set_entry_point("greeting")

    # Add edges based on state
    def route_from_greeting(state: ConversationState) -> str:
        """Route from greeting based on intent."""
        if state.current_intent == "make_reservation":
            return "collect_info"
        elif state.current_intent == "cancel_reservation":
            return "cancel_reservation"
        elif state.current_intent == "query_menu":
            return "menu_query"
        elif state.needs_disambiguation:
            return "disambiguation"
        return END

    def route_from_collect_info(state: ConversationState) -> str:
        """Route from info collection."""
        if state.stage == "confirm_reservation":
            # Check if user confirmed
            if state.messages and state.messages[-1].lower() in ["yes", "y", "confirm", "ok"]:
                return "create_reservation"
            elif state.messages and state.messages[-1].lower() in ["no", "n"]:
                return "greeting"
            # Still need confirmation
            return "collect_info"
        elif state.needs_disambiguation:
            return "disambiguation"
        elif state.stage == "completed":
            return END
        return "collect_info"

    def route_from_cancel(state: ConversationState) -> str:
        """Route from cancellation flow."""
        if state.stage == "completed":
            return END
        elif state.needs_disambiguation:
            return "disambiguation"
        return "cancel_reservation"

    def route_from_disambiguation(state: ConversationState) -> str:
        """Route from disambiguation."""
        if state.stage == "escalate":
            return END
        # Return to appropriate flow based on intent
        if state.current_intent == "make_reservation":
            return "collect_info"
        elif state.current_intent == "cancel_reservation":
            return "cancel_reservation"
        return "greeting"

    # Add conditional edges
    workflow.add_conditional_edges("greeting", route_from_greeting)
    workflow.add_conditional_edges("collect_info", route_from_collect_info)
    workflow.add_conditional_edges("cancel_reservation", route_from_cancel)
    workflow.add_conditional_edges("disambiguation", route_from_disambiguation)

    # Simple edges
    workflow.add_edge("create_reservation", END)
    workflow.add_edge("menu_query", END)

    return workflow.compile()


async def run_conversation_turn(
    graph: StateGraph,
    state: ConversationState,
    user_message: str,
) -> ConversationState:
    """
    Run a single turn of the conversation.

    Args:
        graph: Compiled conversation graph
        state: Current conversation state
        user_message: User's message

    Returns:
        Updated conversation state
    """
    # Add user message to state
    state.messages.append(user_message)

    # Run graph
    result = await graph.ainvoke(state)

    return result
