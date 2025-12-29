"""Build the LangGraph workflow for Voice AI Restaurant Bot."""

from typing import Literal
from langgraph.graph import StateGraph, END

from .state import CallState
from .nodes import (
    detect_intent_node,
    menu_answer_node,
    recommend_node,
    make_reservation_collect_node,
    make_reservation_confirm_node,
    make_reservation_execute_node,
    cancel_collect_3q_node,
    cancel_search_node,
    cancel_disambiguate_node,
    cancel_confirm_node,
    cancel_execute_node,
    handoff_node,
)


# ============================================================================
# ROUTING FUNCTIONS (for conditional edges)
# ============================================================================

def route_after_intent(state: CallState) -> str:
    """Route to appropriate handler based on detected intent."""
    if state.needs_handoff:
        return "handoff"

    intent = state.intent

    if intent == "MENU":
        return "menu_answer"
    elif intent == "RECOMMEND":
        return "recommend"
    elif intent == "RESERVE":
        return "make_reservation_collect"
    elif intent == "CANCEL":
        return "cancel_collect_3q"
    else:
        # Unknown intent - try to help or handoff
        return "handoff"


def route_after_reservation_collect(state: CallState) -> str:
    """Route after collecting reservation slots."""
    if state.needs_handoff:
        return "handoff"

    # Check if all required slots are filled
    slots = state.reservation_slots
    all_filled = all(v is not None for v in slots.values())

    if all_filled:
        return "make_reservation_confirm"
    else:
        # Need more info, loop back to collect
        return "make_reservation_collect"


def route_after_reservation_confirm(state: CallState) -> str:
    """Route after reservation confirmation."""
    if state.needs_handoff:
        return "handoff"

    if state.user_confirmed is True:
        return "make_reservation_execute"
    elif state.user_confirmed is False:
        # User said no, go back to collect
        return "make_reservation_collect"
    else:
        # Still waiting for confirmation, loop back
        return "make_reservation_confirm"


def route_after_cancel_collect(state: CallState) -> str:
    """Route after collecting cancellation info (3-question flow)."""
    if state.needs_handoff:
        return "handoff"

    slots = state.cancellation_slots

    # Check if we have minimum required info (name, date, and phone or time)
    has_required = (
        slots["name"] is not None and
        slots["date"] is not None and
        (slots["phone"] is not None or slots["time"] is not None)
    )

    if has_required:
        return "cancel_search"
    else:
        # Need more info, loop back
        return "cancel_collect_3q"


def route_after_cancel_search(state: CallState) -> str:
    """Route after searching for reservations to cancel."""
    if state.needs_handoff:
        return "handoff"

    matches = state.cancellation_matches

    if len(matches) == 0:
        # No matches - go to disambiguate which will handle this
        return "cancel_disambiguate"
    elif len(matches) == 1:
        # Single match - go straight to confirmation
        return "cancel_confirm"
    else:
        # Multiple matches - need disambiguation
        return "cancel_disambiguate"


def route_after_cancel_disambiguate(state: CallState) -> str:
    """Route after disambiguation."""
    if state.needs_handoff:
        return "handoff"

    matches = state.cancellation_matches

    if len(matches) == 0:
        # No matches found, already handled in disambiguate
        return "handoff"
    elif len(matches) == 1:
        # User selected one, proceed to confirm
        return "cancel_confirm"
    else:
        # Still multiple matches, loop back
        return "cancel_disambiguate"


def route_after_cancel_confirm(state: CallState) -> str:
    """Route after cancellation confirmation."""
    if state.needs_handoff:
        return "handoff"

    if state.user_confirmed is True:
        return "cancel_execute"
    elif state.user_confirmed is False:
        # User said no, exit
        return END
    else:
        # Still waiting for confirmation, loop back
        return "cancel_confirm"


def route_to_end(state: CallState) -> str:
    """Check if conversation should end or continue."""
    if state.completed:
        return END
    if state.needs_handoff:
        return "handoff"
    return END


# ============================================================================
# GRAPH BUILDER
# ============================================================================

def build_graph() -> StateGraph:
    """
    Build and compile the LangGraph workflow.

    Returns:
        Compiled StateGraph ready for execution.
    """
    # Initialize the graph
    workflow = StateGraph(CallState)

    # ========================================================================
    # ADD NODES
    # ========================================================================

    # Intent detection (entry point)
    workflow.add_node("detect_intent", detect_intent_node)

    # Menu & Recommendations
    workflow.add_node("menu_answer", menu_answer_node)
    workflow.add_node("recommend", recommend_node)

    # Reservation flow
    workflow.add_node("make_reservation_collect", make_reservation_collect_node)
    workflow.add_node("make_reservation_confirm", make_reservation_confirm_node)
    workflow.add_node("make_reservation_execute", make_reservation_execute_node)

    # Cancellation flow
    workflow.add_node("cancel_collect_3q", cancel_collect_3q_node)
    workflow.add_node("cancel_search", cancel_search_node)
    workflow.add_node("cancel_disambiguate", cancel_disambiguate_node)
    workflow.add_node("cancel_confirm", cancel_confirm_node)
    workflow.add_node("cancel_execute", cancel_execute_node)

    # Handoff
    workflow.add_node("handoff", handoff_node)

    # ========================================================================
    # SET ENTRY POINT
    # ========================================================================

    workflow.set_entry_point("detect_intent")

    # ========================================================================
    # ADD EDGES
    # ========================================================================

    # From intent detection, route to appropriate handler
    workflow.add_conditional_edges(
        "detect_intent",
        route_after_intent,
        {
            "menu_answer": "menu_answer",
            "recommend": "recommend",
            "make_reservation_collect": "make_reservation_collect",
            "cancel_collect_3q": "cancel_collect_3q",
            "handoff": "handoff",
        }
    )

    # Menu and recommendations end the conversation
    workflow.add_edge("menu_answer", END)
    workflow.add_edge("recommend", END)

    # Reservation flow edges
    workflow.add_conditional_edges(
        "make_reservation_collect",
        route_after_reservation_collect,
        {
            "make_reservation_collect": "make_reservation_collect",  # Loop if needed
            "make_reservation_confirm": "make_reservation_confirm",
            "handoff": "handoff",
        }
    )

    workflow.add_conditional_edges(
        "make_reservation_confirm",
        route_after_reservation_confirm,
        {
            "make_reservation_execute": "make_reservation_execute",
            "make_reservation_collect": "make_reservation_collect",  # Restart if user says no
            "make_reservation_confirm": "make_reservation_confirm",  # Loop if waiting
            "handoff": "handoff",
        }
    )

    workflow.add_edge("make_reservation_execute", END)

    # Cancellation flow edges
    workflow.add_conditional_edges(
        "cancel_collect_3q",
        route_after_cancel_collect,
        {
            "cancel_collect_3q": "cancel_collect_3q",  # Loop if needed
            "cancel_search": "cancel_search",
            "handoff": "handoff",
        }
    )

    workflow.add_conditional_edges(
        "cancel_search",
        route_after_cancel_search,
        {
            "cancel_confirm": "cancel_confirm",
            "cancel_disambiguate": "cancel_disambiguate",
            "handoff": "handoff",
        }
    )

    workflow.add_conditional_edges(
        "cancel_disambiguate",
        route_after_cancel_disambiguate,
        {
            "cancel_confirm": "cancel_confirm",
            "cancel_disambiguate": "cancel_disambiguate",  # Loop if needed
            "handoff": "handoff",
        }
    )

    workflow.add_conditional_edges(
        "cancel_confirm",
        route_after_cancel_confirm,
        {
            "cancel_execute": "cancel_execute",
            "cancel_confirm": "cancel_confirm",  # Loop if waiting
            "handoff": "handoff",
            END: END,  # If user says no to cancellation
        }
    )

    workflow.add_edge("cancel_execute", END)

    # Handoff always ends
    workflow.add_edge("handoff", END)

    # ========================================================================
    # COMPILE
    # ========================================================================

    app = workflow.compile()

    return app


# ============================================================================
# CONVENIENCE FUNCTION
# ============================================================================

def get_graph():
    """Get a compiled instance of the graph."""
    return build_graph()
