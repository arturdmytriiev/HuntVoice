"""
Build and compile the LangGraph StateGraph for restaurant bot orchestration.
Defines the workflow with nodes and conditional edges for routing.
"""
from typing import Literal
from langgraph.graph import StateGraph, END
import logging

from src.graph.state import CallState
from src.graph.nodes import (
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

logger = logging.getLogger(__name__)


def route_from_detect_intent(state: CallState) -> str:
    """
    Route from intent detection to appropriate next node.

    Args:
        state: Current call state

    Returns:
        Next node name
    """
    if state.current_intent == "MENU":
        return "menu_answer"
    elif state.current_intent == "RECOMMEND":
        return "recommend"
    elif state.current_intent == "RESERVE":
        return "reserve_collect"
    elif state.current_intent == "CANCEL":
        return "cancel_collect"
    elif state.current_intent == "HANDOFF":
        return "handoff"
    else:
        # Unknown intent - stay in detect or handoff after max attempts
        if state.should_handoff():
            return "handoff"
        return "detect_intent"


def route_from_reserve_collect(state: CallState) -> str:
    """
    Route from reservation collection node.

    Args:
        state: Current call state

    Returns:
        Next node name
    """
    if state.current_step == "handoff":
        return "handoff"
    elif state.current_step == "reserve_confirm":
        return "reserve_confirm"
    else:
        # Stay in collect until all slots filled
        return "reserve_collect"


def route_from_reserve_confirm(state: CallState) -> str:
    """
    Route from reservation confirmation node.

    Args:
        state: Current call state

    Returns:
        Next node name
    """
    if state.current_step == "reserve_execute":
        return "reserve_execute"
    elif state.current_step == "reserve_collect":
        # User said no, restart collection
        return "reserve_collect"
    else:
        # Still waiting for confirmation
        return "reserve_confirm"


def route_from_reserve_execute(state: CallState) -> str:
    """
    Route from reservation execution node.

    Args:
        state: Current call state

    Returns:
        Next node name or END
    """
    if state.is_complete:
        return END
    elif state.current_step == "reserve_collect_date":
        # Need to retry date/time
        return "reserve_collect"
    elif state.current_step == "error":
        return "handoff"
    else:
        return END


def route_from_cancel_collect(state: CallState) -> str:
    """
    Route from cancellation collection node (3 questions).

    Args:
        state: Current call state

    Returns:
        Next node name
    """
    if state.current_step == "handoff":
        return "handoff"
    elif state.current_step == "cancel_search":
        return "cancel_search"
    else:
        # Stay in collect until all 3 questions answered
        return "cancel_collect"


def route_from_cancel_search(state: CallState) -> str:
    """
    Route from cancellation search node.

    Args:
        state: Current call state

    Returns:
        Next node name or END
    """
    if state.is_complete:
        # No reservations found
        return END
    elif state.current_step == "cancel_confirm":
        # Exactly one reservation found
        return "cancel_confirm"
    elif state.current_step == "cancel_disambiguate":
        # Multiple reservations found
        return "cancel_disambiguate"
    elif state.current_step == "error":
        return "handoff"
    else:
        return END


def route_from_cancel_disambiguate(state: CallState) -> str:
    """
    Route from cancellation disambiguation node.

    Args:
        state: Current call state

    Returns:
        Next node name
    """
    if state.current_step == "handoff":
        return "handoff"
    elif state.current_step == "cancel_confirm":
        return "cancel_confirm"
    else:
        # Stay in disambiguate until user selects
        return "cancel_disambiguate"


def route_from_cancel_confirm(state: CallState) -> str:
    """
    Route from cancellation confirmation node.

    Args:
        state: Current call state

    Returns:
        Next node name or END
    """
    if state.current_step == "cancel_execute":
        return "cancel_execute"
    elif state.is_complete:
        # User declined cancellation
        return END
    else:
        # Still waiting for confirmation
        return "cancel_confirm"


def route_from_cancel_execute(state: CallState) -> str:
    """
    Route from cancellation execution node.

    Args:
        state: Current call state

    Returns:
        END (cancellation complete)
    """
    return END


def build_restaurant_bot_graph() -> StateGraph:
    """
    Build and compile the restaurant bot conversation graph.

    This creates a StateGraph with all nodes and conditional edges
    that route conversation flow based on CallState.

    Returns:
        Compiled StateGraph ready to execute
    """
    # Create the graph with CallState schema
    workflow = StateGraph(CallState)

    # ==================== Add All Nodes ====================

    # Intent detection
    workflow.add_node("detect_intent", detect_intent_node)

    # Menu and recommendations
    workflow.add_node("menu_answer", menu_answer_node)
    workflow.add_node("recommend", recommend_node)

    # Reservation flow
    workflow.add_node("reserve_collect", make_reservation_collect_node)
    workflow.add_node("reserve_confirm", make_reservation_confirm_node)
    workflow.add_node("reserve_execute", make_reservation_execute_node)

    # Cancellation flow
    workflow.add_node("cancel_collect", cancel_collect_3q_node)
    workflow.add_node("cancel_search", cancel_search_node)
    workflow.add_node("cancel_disambiguate", cancel_disambiguate_node)
    workflow.add_node("cancel_confirm", cancel_confirm_node)
    workflow.add_node("cancel_execute", cancel_execute_node)

    # Handoff
    workflow.add_node("handoff", handoff_node)

    # ==================== Set Entry Point ====================
    workflow.set_entry_point("detect_intent")

    # ==================== Add Conditional Edges ====================

    # From intent detection - route to appropriate flow
    workflow.add_conditional_edges(
        "detect_intent",
        route_from_detect_intent,
        {
            "detect_intent": "detect_intent",
            "menu_answer": "menu_answer",
            "recommend": "recommend",
            "reserve_collect": "reserve_collect",
            "cancel_collect": "cancel_collect",
            "handoff": "handoff",
        }
    )

    # Menu and recommendations - simple end
    workflow.add_edge("menu_answer", END)
    workflow.add_edge("recommend", END)

    # Reservation flow routing
    workflow.add_conditional_edges(
        "reserve_collect",
        route_from_reserve_collect,
        {
            "reserve_collect": "reserve_collect",
            "reserve_confirm": "reserve_confirm",
            "handoff": "handoff",
        }
    )

    workflow.add_conditional_edges(
        "reserve_confirm",
        route_from_reserve_confirm,
        {
            "reserve_confirm": "reserve_confirm",
            "reserve_execute": "reserve_execute",
            "reserve_collect": "reserve_collect",
        }
    )

    workflow.add_conditional_edges(
        "reserve_execute",
        route_from_reserve_execute,
        {
            END: END,
            "reserve_collect": "reserve_collect",
            "handoff": "handoff",
        }
    )

    # Cancellation flow routing
    workflow.add_conditional_edges(
        "cancel_collect",
        route_from_cancel_collect,
        {
            "cancel_collect": "cancel_collect",
            "cancel_search": "cancel_search",
            "handoff": "handoff",
        }
    )

    workflow.add_conditional_edges(
        "cancel_search",
        route_from_cancel_search,
        {
            END: END,
            "cancel_confirm": "cancel_confirm",
            "cancel_disambiguate": "cancel_disambiguate",
            "handoff": "handoff",
        }
    )

    workflow.add_conditional_edges(
        "cancel_disambiguate",
        route_from_cancel_disambiguate,
        {
            "cancel_disambiguate": "cancel_disambiguate",
            "cancel_confirm": "cancel_confirm",
            "handoff": "handoff",
        }
    )

    workflow.add_conditional_edges(
        "cancel_confirm",
        route_from_cancel_confirm,
        {
            END: END,
            "cancel_confirm": "cancel_confirm",
            "cancel_execute": "cancel_execute",
        }
    )

    workflow.add_conditional_edges(
        "cancel_execute",
        route_from_cancel_execute,
        {
            END: END,
        }
    )

    # Handoff - always ends
    workflow.add_edge("handoff", END)

    # ==================== Compile and Return ====================
    compiled_graph = workflow.compile()

    logger.info("Restaurant bot graph compiled successfully")
    return compiled_graph


# Convenience function for getting a ready-to-use graph
def get_restaurant_bot_graph() -> StateGraph:
    """
    Get a compiled restaurant bot graph.

    Returns:
        Compiled StateGraph
    """
    return build_restaurant_bot_graph()
