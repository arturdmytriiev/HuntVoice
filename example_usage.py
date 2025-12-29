"""
Example usage of the Voice AI Restaurant Bot LangGraph orchestration.

This demonstrates how to use the compiled graph for various conversation flows.
"""

from graph import build_graph, CallState


def run_example_conversation(user_inputs: list[str]):
    """
    Run a sample conversation through the graph.

    Args:
        user_inputs: List of user messages to process
    """
    # Build the graph
    app = build_graph()

    # Initialize state
    state = CallState()

    print("=" * 60)
    print("Starting conversation...")
    print("=" * 60)

    # Process each user input
    for user_input in user_inputs:
        print(f"\nUser: {user_input}")

        # Add user message to state
        state.messages.append({"role": "user", "content": user_input})

        # Run the graph
        result = app.invoke(state)

        # Update state with result
        state = CallState(**result)

        # Print assistant responses
        assistant_messages = [
            msg for msg in state.messages
            if msg.get("role") == "assistant"
        ]
        if assistant_messages:
            latest = assistant_messages[-1]
            print(f"Assistant: {latest['content']}")

        # Check if completed
        if state.completed:
            print("\n[Conversation completed]")
            break

    print("=" * 60)
    return state


if __name__ == "__main__":
    # Example 1: Menu inquiry
    print("\n### EXAMPLE 1: Menu Inquiry ###")
    run_example_conversation([
        "What's on the menu?"
    ])

    # Example 2: Recommendation
    print("\n\n### EXAMPLE 2: Recommendation ###")
    run_example_conversation([
        "What do you recommend?"
    ])

    # Example 3: Make a reservation
    print("\n\n### EXAMPLE 3: Make Reservation ###")
    run_example_conversation([
        "I'd like to make a reservation for tomorrow at 7pm",
        "John Smith",
        "4 people",
        "555-1234",
        "Yes, that's correct"
    ])

    # Example 4: Cancel a reservation
    print("\n\n### EXAMPLE 4: Cancel Reservation ###")
    run_example_conversation([
        "I need to cancel my reservation",
        "John Smith",
        "Tomorrow",
        "7:00pm",
        "Yes, cancel it"
    ])
