from restaurant_order_agent import RestaurantOrderAgent


def test_tc1_unrelated_then_partial_then_reorder_then_unavailable_ends_due_to_retry():
    agent = RestaurantOrderAgent(
        menu={"burger": 10, "pizza": 30, "momos": 3, "colddrink": 2, "pasta": 1}
    )

    rejected = agent.process("What is the capital of France?")
    assert rejected["status"] == "rejected"
    assert "Food Ordering" in rejected["final_result"]

    partial = agent.process("I want 20 burgers")
    assert partial["status"] == "awaiting_user_decision"
    assert partial["available_quantity"] == 10

    unavailable = agent.process("I want 5 coffee")
    assert unavailable["status"] == "awaiting_user_decision"
    assert unavailable["order_retry_attempts"] == 1

    end_state = agent.process("I want 5 coffee")
    assert end_state["status"] == "apology"
    assert end_state["order_retry_attempts"] == 0


def test_tc2_available_order_then_cook_and_serve_retries_success():
    agent = RestaurantOrderAgent(
        menu={"burger": 10, "pizza": 30, "momos": 3, "colddrink": 2, "pasta": 1},
        cook_success_prob=0.6,
        serve_success_prob=0.6,
    )

    import random

    values = iter([0.9, 0.2, 0.9, 0.2])
    random.random = lambda: next(values)
    try:
        state = agent.process("I want 2 pizzas")
    finally:
        random.random = lambda: 0.5

    assert state["status"] == "completed"
    assert state["final_result"].lower().startswith("your order is complete")


def test_tc3_partial_then_available_then_cook_retry_then_serve_retry_then_failure():
    agent = RestaurantOrderAgent(
        menu={"burger": 10, "pizza": 30, "momos": 3, "colddrink": 2, "pasta": 1},
        cook_success_prob=0.6,
        serve_success_prob=0.6,
    )

    import random

    values = iter([0.9, 0.2, 0.9, 0.2, 0.9])
    random.random = lambda: next(values)
    try:
        partial = agent.process("I want 20 burgers")
        assert partial["status"] == "awaiting_user_decision"

        state = agent.process("I want 2 pizzas")
    finally:
        random.random = lambda: 0.5

    assert state["status"] == "apology"
    assert state["final_result"].lower().startswith("i am sorry")
