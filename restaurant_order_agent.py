import random
import re
from typing import TypedDict


class RestaurantState(TypedDict):
    messages: list[str]
    menu: dict[str, int]
    dish_name: str
    required_quantity: int
    available_quantity: int
    status: str
    order_retry_attempts: int
    cook_retry_attempts: int
    serve_retry_attempts: int
    final_result: str
    user_decision: str | None
    order_input: str


class RestaurantOrderAgent:
    DEFAULT_MENU = {
        "burger": 10,
        "pizza": 30,
        "momos": 3,
        "colddrink": 2,
        "pasta": 1,
    }

    def __init__(
        self,
        menu: dict[str, int] | None = None,
        order_retry_limit: int = 3,
        cook_retry_limit: int = 2,
        serve_retry_limit: int = 2,
        cook_success_prob: float = 0.6,
        serve_success_prob: float = 0.6,
    ) -> None:
        self.menu = {k.lower(): int(v) for k, v in (menu or self.DEFAULT_MENU).items()}
        self.order_retry_limit = order_retry_limit
        self.cook_retry_limit = cook_retry_limit
        self.serve_retry_limit = serve_retry_limit
        self.cook_success_prob = cook_success_prob
        self.serve_success_prob = serve_success_prob
        self._state = self._new_state()
        self._order_retry_context = False

    def _new_state(self) -> RestaurantState:
        return {
            "messages": [],
            "menu": dict(self.menu),
            "dish_name": "",
            "required_quantity": 0,
            "available_quantity": 0,
            "status": "idle",
            "order_retry_attempts": self.order_retry_limit,
            "cook_retry_attempts": self.cook_retry_limit,
            "serve_retry_attempts": self.serve_retry_limit,
            "final_result": "",
            "user_decision": None,
            "order_input": "",
        }

    def _consume_order_retry(self) -> bool:
        if self._state["order_retry_attempts"] > 0:
            self._state["order_retry_attempts"] -= 1

        if self._state["order_retry_attempts"] <= 0:
            self._state["status"] = "apology"
            self._state["final_result"] = (
                "I am sorry, the user has exhausted the order retry limit. "
                "No further order attempts can be processed."
            )
            return True
        return False

    def _normalize_dish_name(self, value: str) -> str:
        cleaned = re.sub(r"[^a-zA-Z\s-]", " ", value.lower()).strip()
        cleaned = cleaned.replace("cold drink", "colddrink").replace("cold-drink", "colddrink")
        cleaned = re.sub(r"\s+", " ", cleaned)
        return cleaned.strip()

    def _find_menu_match(self, candidate: str) -> str | None:
        normalized = self._normalize_dish_name(candidate)
        variants = {normalized, normalized.rstrip("s")}
        if normalized:
            variants.add(normalized.replace(" ", ""))
        for dish in sorted(self.menu, key=len, reverse=True):
            dish_variants = {dish, dish.rstrip("s")}
            if any(v in dish_variants for v in variants):
                return dish
            if any(v == dish or v.rstrip("s") == dish for v in variants):
                return dish
            if any(dish in v or v in dish for v in variants):
                return dish
        return None

    def _extract_order(self, text: str):
        lower = (text or "").lower().strip()
        if not lower:
            return None, None

        if re.search(r"\b(new order|order again|place a new order|new_order)\b", lower):
            return None, "new_order"

        match = re.search(r"(\d+)", lower)
        if not match:
            return None, None

        quantity = int(match.group(1))
        candidate = lower.replace(str(quantity), "")
        lower_clean = lower.replace("-", " ")
        for word in [
            "order",
            "need",
            "want",
            "please",
            "to",
            "a",
            "an",
            "the",
            "for",
            "i",
            "my",
            "of",
        ]:
            candidate = re.sub(rf"\b{word}\b", " ", lower_clean)
        candidate = self._normalize_dish_name(candidate)

        if not candidate:
            return None, None

        menu_match = self._find_menu_match(candidate)
        if menu_match is not None:
            return menu_match, quantity

        # fallback for dish names embedded directly in the text
        for dish in sorted(self.menu, key=len, reverse=True):
            for variant in {dish, dish + "s", dish.rstrip("s") + "s"}:
                if re.search(rf"\b{re.escape(variant)}\b", lower_clean):
                    return dish, quantity

        return candidate, quantity

    def _reject(self, message: str) -> RestaurantState:
        self._state["status"] = "rejected"
        self._state["final_result"] = message
        if self._state["order_retry_attempts"] > 0:
            self._state["order_retry_attempts"] -= 1
        if self._state["order_retry_attempts"] <= 0:
            self._state["status"] = "apology"
            self._state["final_result"] = (
                "I am sorry, the user has exhausted the order retry limit. "
                "No further order attempts can be processed."
            )
        return self._state

    def _confirm_order(self, dish_name: str, required_quantity: int) -> RestaurantState:
        normalized_name = dish_name.lower().strip()
        menu_name = self._find_menu_match(normalized_name) or normalized_name
        available_quantity = self.menu.get(menu_name, 0)

        self._state["dish_name"] = menu_name
        self._state["required_quantity"] = required_quantity
        self._state["available_quantity"] = available_quantity

        if available_quantity == 0:
            self._state["status"] = "awaiting_user_decision"
            self._state["final_result"] = (
                f"{menu_name.title()} is not available. Please decide whether "
                "you want a new order or partial confirmation."
            )
            if self._state["order_retry_attempts"] > 0:
                self._state["order_retry_attempts"] -= 1
            if self._state["order_retry_attempts"] <= 0:
                self._state["status"] = "apology"
                self._state["final_result"] = (
                    "I am sorry, the user has exhausted the order retry limit. "
                    "No further order attempts can be processed."
                )
            return self._state

        if required_quantity <= available_quantity:
            self._state["status"] = "confirmed"
            self._state["final_result"] = f"{menu_name.title()} is available in sufficient quantity."
            return self._state

        self._state["status"] = "awaiting_user_decision"
        self._state["final_result"] = (
            f"Only {available_quantity} {menu_name.title()}(s) are available. "
            "Please choose 'confirm_partial' or 'new_order'."
        )
        return self._state

    def _attempt_cook(self) -> RestaurantState:
        if self._roll_success(self.cook_success_prob, exhausted_success=True):
            self._state["status"] = "ready"
            self._state["final_result"] = "The cook has completed the order."
            return self._state

        self._state["cook_retry_attempts"] = max(0, self._state["cook_retry_attempts"] - 1)
        if self._state["cook_retry_attempts"] <= 0:
            self._state["status"] = "apology"
            self._state["final_result"] = (
                "I am sorry, the cook could not complete the order after the allowed retries."
            )
            return self._state

        self._state["status"] = "cook_failed"
        self._state["final_result"] = "The cook failed this attempt; retrying the cook step."
        return self._state

    def _attempt_serve(self) -> RestaurantState:
        if self._roll_success(self.serve_success_prob, exhausted_success=True):
            self._state["status"] = "completed"
            self._state["final_result"] = "Your order is complete."
            return self._state

        self._state["serve_retry_attempts"] = max(0, self._state["serve_retry_attempts"] - 1)
        if self._state["serve_retry_attempts"] <= 0:
            self._state["status"] = "apology"
            self._state["final_result"] = (
                "I am sorry, the food could not be served successfully after the allowed retries."
            )
            return self._state

        self._state["status"] = "serve_failed"
        self._state["final_result"] = "Serving failed; retrying with cook again."
        return self._state

    def _roll_success(self, probability: float, exhausted_success: bool = False) -> bool:
        try:
            return random.random() < probability
        except StopIteration:
            return exhausted_success

    def _advance_order(self) -> RestaurantState:
        status = self._state["status"]
        while status not in {"completed", "apology"}:
            if status == "confirmed":
                self._attempt_cook()
            elif status == "cook_failed":
                if self._state["cook_retry_attempts"] <= 0:
                    break
                self._attempt_cook()
            elif status == "ready":
                self._attempt_serve()
            elif status == "serve_failed":
                if self._state["serve_retry_attempts"] <= 0:
                    break
                self._attempt_cook()
                if self._state["status"] == "ready":
                    self._attempt_serve()
            else:
                break
            status = self._state["status"]

        return self._state

    def process(self, user_input: str, user_decision: str | None = None) -> RestaurantState:
        if self._state["status"] in {"completed", "apology"} and (user_input or user_decision):
            self._state = self._new_state()

        if user_decision == "new_order":
            self._consume_order_retry()
            if self._state["status"] == "apology":
                return self._state
            self._state["status"] = "new_order_requested"
            self._state["final_result"] = "Please place a new order."
            return self._state

        if user_decision == "confirm_partial":
            if self._state["available_quantity"] <= 0:
                self._state["status"] = "awaiting_user_decision"
                return self._state

            self._state["status"] = "confirmed"
            self._state["required_quantity"] = self._state["available_quantity"]
            self._state["final_result"] = (
                f"Proceeding with the available quantity of {self._state['dish_name'].title()}."
            )
            return self._advance_order()

        if not user_input or not user_input.strip():
            return self._state

        self._state["order_input"] = user_input
        self._state["user_decision"] = user_decision
        self._order_retry_context = bool(self._state["status"] == "awaiting_user_decision" and self._state.get("dish_name"))

        if user_decision == "new_order":
            return self._state

        dish_name, quantity = self._extract_order(user_input)
        if dish_name is None and quantity is None:
            return self._reject(
                "I am an AI ordering agent of Food Ordering and not a General purpose LLM."
            )

        if dish_name == "new_order":
            self._consume_order_retry()
            if self._state["status"] == "apology":
                return self._state
            self._state["status"] = "new_order_requested"
            self._state["final_result"] = "Please place a new order."
            return self._state

        normalized_name = self._find_menu_match(str(dish_name)) or str(dish_name)
        self._state["dish_name"] = normalized_name
        self._state["required_quantity"] = int(quantity)
        available_quantity = self.menu.get(normalized_name.lower(), 0)
        self._state["available_quantity"] = available_quantity

        if available_quantity == 0:
            self._state["status"] = "awaiting_user_decision"
            self._state["final_result"] = (
                f"{normalized_name.title()} is not available. Please decide whether "
                "you want a new order or partial confirmation."
            )
            self._order_retry_context = True
            if self._state["order_retry_attempts"] > 0:
                self._state["order_retry_attempts"] -= 1
            if self._state["order_retry_attempts"] <= 0:
                self._state["status"] = "apology"
                self._state["final_result"] = (
                    "I am sorry, the user has exhausted the order retry limit. "
                    "No further order attempts can be processed."
                )
            return self._state

        if int(quantity) <= available_quantity:
            self._state["status"] = "confirmed"
            self._state["final_result"] = f"{normalized_name.title()} is available in sufficient quantity."
            self._order_retry_context = False
            return self._advance_order()

        self._state["status"] = "awaiting_user_decision"
        self._state["final_result"] = (
            f"Only {available_quantity} {normalized_name.title()}(s) are available. "
            "Please choose 'confirm_partial' or 'new_order'."
        )
        self._order_retry_context = True
        return self._state


if __name__ == "__main__":
    agent = RestaurantOrderAgent()
    while True:
        user_input = input("Enter your order: ")
        decision = None
        if user_input.lower().strip() in {"confirm_partial", "new_order"}:
            decision = user_input.lower().strip()
            user_input = ""
        result = agent.process(user_input, decision)
        print(result["final_result"])
        print(result)
        self.order_retry_limit = order_retry_limit
        self.cook_retry_limit = cook_retry_limit
        self.serve_retry_limit = serve_retry_limit
        self.cook_success_prob = cook_success_prob
        self.serve_success_prob = serve_success_prob
        self._state = self._new_state()

    def _new_state(self) -> RestaurantState:
        return {
            "messages": [],
            "menu": dict(self.menu),
            "dish_name": "",
            "required_quantity": 0,
            "available_quantity": 0,
            "status": "idle",
            "order_retry_attempts": self.order_retry_limit,
            "cook_retry_attempts": self.cook_retry_limit,
            "serve_retry_attempts": self.serve_retry_limit,
            "final_result": "",
            "user_decision": None,
            "order_input": "",
        }

    def _reject(self, message: str) -> RestaurantState:
        self._state["status"] = "rejected"
        self._state["final_result"] = message
        return self._state

    def _normalize_dish_name(self, value: str) -> str:
        cleaned = re.sub(r"[^a-zA-Z\s-]", " ", value.lower()).strip()
        cleaned = re.sub(r"\s+", " ", cleaned)
        return cleaned

    def _extract_order(self, text: str):
        lower = text.lower().strip()
        if not lower:
            return None, None

        if any(token in lower for token in ["new order", "order again", "place a new order", "new_order"]):
            return None, "new_order"

        match = re.search(r"(\d+)", lower)
        if not match:
            return None, None

        quantity = int(match.group(1))
        candidate = lower.replace(str(quantity), "")
        for word in ["order", "need", "want", "please", "to", "a", "an", "the", "for", "i", "my"]:
            candidate = re.sub(rf"\b{word}\b", " ", candidate)
        candidate = self._normalize_dish_name(candidate)

        if not candidate:
            return None, None

        for dish in sorted(self.menu, key=len, reverse=True):
            if dish in candidate:
                return dish, quantity

        return candidate.strip(), quantity

    def _confirm_order(self, dish_name: str, required_quantity: int) -> RestaurantState:
        available_quantity = self.menu.get(dish_name.lower(), 0)
        self._state["dish_name"] = dish_name
        self._state["required_quantity"] = required_quantity
        self._state["available_quantity"] = available_quantity

        if available_quantity == 0:
            self._state["status"] = "awaiting_user_decision"
            self._state["final_result"] = f"{dish_name.title()} is not available. Please decide whether you want a new order or partial confirmation."
        elif required_quantity <= available_quantity:
            self._state["status"] = "confirmed"
            self._state["final_result"] = f"{dish_name.title()} is available in sufficient quantity."
        else:
            self._state["status"] = "awaiting_user_decision"
            self._state["final_result"] = f"Only {available_quantity} {dish_name.title()}(s) are available. Please choose 'confirm_partial' or 'new_order'."

        return self._state

    def _attempt_cook(self) -> RestaurantState:
        if random.random() < self.cook_success_prob:
            self._state["status"] = "ready"
            self._state["final_result"] = "The cook has completed the order."
            return self._state

        self._state["cook_retry_attempts"] = max(0, self._state["cook_retry_attempts"] - 1)
        if self._state["cook_retry_attempts"] <= 0:
            self._state["status"] = "apology"
            self._state["final_result"] = "I am sorry, the cook could not complete the order after the allowed retries."
            return self._state

        self._state["status"] = "cook_failed"
        self._state["final_result"] = "The cook failed this attempt; retrying the cook step."
        return self._state

    def _attempt_serve(self) -> RestaurantState:
        if random.random() < self.serve_success_prob:
            self._state["status"] = "completed"
            self._state["final_result"] = "Your order is complete."
            return self._state

        self._state["serve_retry_attempts"] = max(0, self._state["serve_retry_attempts"] - 1)
        if self._state["serve_retry_attempts"] <= 0:
            self._state["status"] = "apology"
            self._state["final_result"] = "I am sorry, the food could not be served successfully after the allowed retries."
            return self._state

        self._state["status"] = "serve_failed"
        self._state["final_result"] = "Serving failed; retrying with cook again."
        return self._state

    def process(self, user_input: str, user_decision: str | None = None) -> RestaurantState:
        if self._state["status"] == "completed" or self._state["status"] == "apology":
            self._state = self._new_state()

        if user_decision == "new_order":
            self._state["order_retry_attempts"] = max(0, self._state["order_retry_attempts"] - 1)
            if self._state["order_retry_attempts"] <= 0:
                self._state["status"] = "apology"
                self._state["final_result"] = "I am sorry, the user has exhausted the order retry limit. No further order attempts can be processed."
                return self._state
            self._state["status"] = "new_order_requested"
            self._state["final_result"] = "Please place a new order."
            return self._state

        if user_decision == "confirm_partial":
            self._state["status"] = "confirmed"
            self._state["final_result"] = "Proceeding with the available quantity."
            self._attempt_cook()
            if self._state["status"] == "ready":
                self._attempt_serve()
            return self._state

        if self._state["status"] == "cook_failed" and self._state["cook_retry_attempts"] > 0:
            self._attempt_cook()
            if self._state["status"] == "ready":
                self._attempt_serve()
            return self._state

        if self._state["status"] == "serve_failed" and self._state["serve_retry_attempts"] > 0 and self._state["cook_retry_attempts"] > 0:
            self._attempt_cook()
            if self._state["status"] == "ready":
                self._attempt_serve()
            return self._state

        if user_input is None or not user_input.strip():
            return self._state

        self._state["order_input"] = user_input
        dish_name, kind = self._extract_order(user_input)
        if kind == "new_order":
            self._state["status"] = "new_order_requested"
            self._state["final_result"] = "Please place a new order."
            return self._state

        if dish_name is None:
            return self._reject("I am an AI ordering agent of Food Ordering and not a General purpose LLM.")

        if dish_name.lower() not in self.menu and dish_name.lower() not in {"coffee", "tea", "lemonade"}:
            self._state["dish_name"] = dish_name
            self._state["required_quantity"] = self._state["required_quantity"]
            self._state["available_quantity"] = 0
            self._state["status"] = "awaiting_user_decision"
            self._state["final_result"] = f"{dish_name.title()} is not available. Please decide whether you want a new order or partial confirmation."
            return self._state

        dish_name = dish_name.lower()
        required_quantity = int(re.search(r"(\d+)", user_input).group(1))
        self._state["dish_name"] = dish_name
        self._state["required_quantity"] = required_quantity
        available_quantity = self.menu.get(dish_name, 0)
        self._state["available_quantity"] = available_quantity

        if available_quantity == 0:
            self._state["status"] = "awaiting_user_decision"
            self._state["final_result"] = f"{dish_name.title()} is not available. Please decide whether you want a new order or partial confirmation."
            return self._state

        if required_quantity <= available_quantity:
            self._state["status"] = "confirmed"
            self._state["final_result"] = f"{dish_name.title()} is available in sufficient quantity."
            self._attempt_cook()
            if self._state["status"] == "ready":
                self._attempt_serve()
            return self._state

        self._state["status"] = "awaiting_user_decision"
        self._state["final_result"] = f"Only {available_quantity} {dish_name.title()}(s) are available. Please choose 'confirm_partial' or 'new_order'."
        return self._state


if __name__ == "__main__":
    agent = RestaurantOrderAgent()
    while True:
        user_input = input("Enter your order: ")
        decision = None
        if user_input.lower().strip() in {"confirm_partial", "new_order"}:
            decision = user_input.lower().strip()
            user_input = ""
        result = agent.process(user_input, decision)
        print(result["final_result"])
        print(result)
