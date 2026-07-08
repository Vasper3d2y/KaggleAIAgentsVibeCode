# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
from functools import cached_property
from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.models import Gemini
from google.adk.workflow import Workflow, START
from google.genai import types
from google.genai import Client
from pydantic import BaseModel, Field, ValidationError

load_dotenv()

# In-memory store for discount codes
DISCOUNT_CODES = {
    "WELCOME50": {"redeemed": False, "redeemed_by": None, "active": True},
    "SUMMER20": {"redeemed": False, "redeemed_by": None, "active": True},
}

# Registered user IDs
REGISTERED_USERS = {"user123", "user_kaggle", "student_id", "shopper_1"}

# Administrator user IDs
ADMIN_USERS = {"admin_user", "manager_kaggle"}

# In-memory store for user loyalty points
USER_POINTS = {}

# In-memory store for processed transactions to prevent duplicate point awards
PROCESSED_TRANSACTIONS = set()

# In-memory store for user shopping carts
CARTS = {
    "cart_1": {
        "items": [
            {"name": "Laptop", "price": 1000.0},
            {"name": "Mouse", "price": 50.0},
        ],
        "checked_out": False,
        "user_id": "shopper_1",
    },
    "cart_empty": {
        "items": [],
        "checked_out": False,
        "user_id": "shopper_1",
    },
}


class CartCheckoutInput(BaseModel):
    user_id: str = Field(..., min_length=1)
    cart_id: str = Field(..., min_length=1)
    discount_code: str | None = Field(default=None)


def process_cart_checkout(
    user_id: str,
    cart_id: str,
    discount_code: str | None = None,
) -> dict:
    """Processes checkout for a shopping cart, applying an optional discount code.

    Args:
        user_id: The registered user ID checking out.
        cart_id: The identifier of the cart to check out.
        discount_code: Optional discount code to apply.

    Returns:
        A dict indicating success or error status, including total price if successful.
    """
    try:
        inputs = CartCheckoutInput(
            user_id=user_id,
            cart_id=cart_id,
            discount_code=discount_code,
        )
    except ValidationError as e:
        raise e

    uid = inputs.user_id.strip()
    cid = inputs.cart_id.strip()
    code = inputs.discount_code.strip() if inputs.discount_code else None

    if uid not in REGISTERED_USERS:
        return {
            "status": "error",
            "message": f"User ID '{uid}' is not registered. Only registered users can checkout.",
        }

    if cid not in CARTS:
        return {
            "status": "error",
            "message": f"Cart '{cid}' does not exist.",
        }

    cart = CARTS[cid]

    if cart.get("user_id") != uid:
        return {
            "status": "error",
            "message": f"Security Violation: User '{uid}' does not own cart '{cid}'.",
        }

    if cart.get("checked_out"):
        return {
            "status": "error",
            "message": f"Cart '{cid}' is already checked out.",
        }

    items = cart.get("items", [])
    if not isinstance(items, list) or not items:
        return {
            "status": "error",
            "message": f"Cart '{cid}' is empty or invalid. Cannot checkout.",
        }

    # Calculate total price
    total = 0.0
    for item in items:
        if isinstance(item, dict) and "price" in item:
            total += float(item["price"])

    # Apply discount code if provided
    if code:
        code_upper = code.upper()
        if code_upper not in DISCOUNT_CODES:
            return {
                "status": "error",
                "message": f"Discount code '{code_upper}' is invalid.",
            }

        code_info = DISCOUNT_CODES[code_upper]
        if not code_info.get("active", True):
            return {
                "status": "error",
                "message": f"Discount code '{code_upper}' has been deactivated.",
            }

        if code_info.get("redeemed"):
            return {
                "status": "error",
                "message": f"Discount code '{code_upper}' has already been redeemed by user '{code_info.get('redeemed_by')}'.",
            }

        # Apply percentage discounts: WELCOME50 (50%), SUMMER20 (20%)
        discount_pct = 0.0
        if code_upper == "WELCOME50":
            discount_pct = 0.50
        elif code_upper == "SUMMER20":
            discount_pct = 0.20

        total -= total * discount_pct
        if total < 0.0:
            total = 0.0

        # Mark code as redeemed
        code_info["redeemed"] = True
        code_info["redeemed_by"] = uid

    # Mark cart as checked out
    cart["checked_out"] = True

    return {
        "status": "success",
        "message": f"Cart '{cid}' successfully checked out for user '{uid}'. Total charged: ${total:.2f}.",
        "total_price": total,
    }


class UpdateDiscountStatusInput(BaseModel):
    user_id: str = Field(..., min_length=1)
    discount_code: str = Field(..., min_length=1)
    active: bool


def update_discount_status(
    user_id: str,
    discount_code: str,
    active: bool,
) -> dict:
    """Updates the active status of a discount code (admin only).

    Args:
        user_id: The user ID making the update (must be an admin).
        discount_code: The code to activate or deactivate.
        active: The active status to set.

    Returns:
        A dict indicating success or error status.
    """
    try:
        inputs = UpdateDiscountStatusInput(
            user_id=user_id,
            discount_code=discount_code,
            active=active,
        )
    except ValidationError as e:
        raise e

    uid = inputs.user_id.strip()
    code = inputs.discount_code.strip().upper()
    is_active = inputs.active

    if uid not in ADMIN_USERS:
        return {
            "status": "error",
            "message": f"Security Violation: User '{uid}' is not authorized to update discount code status.",
        }

    if code not in DISCOUNT_CODES:
        return {
            "status": "error",
            "message": f"Discount code '{code}' does not exist.",
        }

    DISCOUNT_CODES[code]["active"] = is_active
    status_str = "activated" if is_active else "deactivated"
    return {
        "status": "success",
        "message": f"Discount code '{code}' successfully {status_str} by administrator '{uid}'.",
    }


class AwardPointsInput(BaseModel):
    user_id: str = Field(..., min_length=1)
    transaction_id: str = Field(..., min_length=1)
    transaction_amount: float = Field(..., gt=0.0)


def award_loyalty_points(
    user_id: str,
    transaction_id: str,
    transaction_amount: float,
) -> dict:
    """Awards loyalty points to a registered user for a successful purchase transaction.

    Args:
        user_id: The registered user ID to receive the points.
        transaction_id: The unique transaction identifier.
        transaction_amount: The transaction purchase amount in dollars.

    Returns:
        A dict with 'status' and a descriptive 'message'.
    """
    try:
        inputs = AwardPointsInput(
            user_id=user_id,
            transaction_id=transaction_id,
            transaction_amount=transaction_amount,
        )
    except ValidationError as e:
        raise e

    uid = inputs.user_id.strip()
    tx_id = inputs.transaction_id.strip()
    amount = inputs.transaction_amount

    if uid not in REGISTERED_USERS:
        return {
            "status": "error",
            "message": f"User ID '{uid}' is not registered. Loyalty points can only be awarded to registered users.",
        }

    if tx_id in PROCESSED_TRANSACTIONS:
        return {
            "status": "error",
            "message": f"Transaction '{tx_id}' has already been processed. Points cannot be awarded multiple times.",
        }

    # Calculate points: 1 point per $1 spent, capped at 1000 points
    points = int(amount)
    if points > 1000:
        points = 1000

    USER_POINTS[uid] = USER_POINTS.get(uid, 0) + points
    PROCESSED_TRANSACTIONS.add(tx_id)

    return {
        "status": "success",
        "message": f"Successfully awarded {points} loyalty points to user '{uid}' for transaction '{tx_id}'.",
    }


def redeem_discount_code(
    discount_code: str,
    user_id: str,
) -> dict:
    """Redeems a single-use discount code for a registered user.

    Args:
        discount_code: The discount code to redeem (e.g., WELCOME50, SUMMER20).
        user_id: The registered user ID redeeming the code.

    Returns:
        A dict with 'status' and a descriptive 'message'.
    """
    code = discount_code.strip().upper()
    uid = user_id.strip()

    if uid not in REGISTERED_USERS:
        return {
            "status": "error",
            "message": f"User ID '{uid}' is not registered. Discount codes can only be redeemed by registered users.",
        }

    if code not in DISCOUNT_CODES:
        return {"status": "error", "message": f"Discount code '{code}' is invalid."}

    code_info = DISCOUNT_CODES[code]
    if not code_info.get("active", True):
        return {
            "status": "error",
            "message": f"Discount code '{code}' has been deactivated.",
        }

    if code_info["redeemed"]:
        return {
            "status": "error",
            "message": f"Discount code '{code}' has already been redeemed by user '{code_info['redeemed_by']}'.",
        }

    # Mark as redeemed
    code_info["redeemed"] = True
    code_info["redeemed_by"] = uid
    return {
        "status": "success",
        "message": f"Discount code '{code}' successfully redeemed for user '{uid}'.",
    }


def register_user(user_id: str) -> dict:
    """Registers a new user ID so they can redeem discount codes.

    Args:
        user_id: The unique identifier for the user to register.

    Returns:
        A dict indicating success or error.
    """
    uid = user_id.strip()
    if not uid:
        return {"status": "error", "message": "User ID cannot be empty."}
    if uid in REGISTERED_USERS:
        return {"status": "success", "message": f"User '{uid}' is already registered."}
    REGISTERED_USERS.add(uid)
    return {"status": "success", "message": f"User '{uid}' successfully registered."}


# Custom Gemini subclass to inject the mock API key
class HardcodedApiKeyGemini(Gemini):
    @cached_property
    def api_client(self) -> Client:
        api_key = os.getenv("GEMINI_API_KEY", "MOCK_API_KEY")
        return Client(api_key=api_key)


# LlmAgent configuration
shopping_agent = Agent(
    name="shopping_agent",
    model=HardcodedApiKeyGemini(
        model="gemini-3.5-flash",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=(
        "You are an AI shopping assistant for a retail store. "
        "Help customers check products, redeem discount codes, award loyalty points for successful purchases, "
        "process cart checkouts, and manage discount code statuses. "
        "To redeem a discount code, award loyalty points, process cart checkouts, or update discount statuses, you MUST require the user's registered/admin user ID. "
        "If they are not registered, you can register them using the register_user tool. "
        "To process cart checkouts, you require a cart ID. "
        "To update discount status, you require a discount code and the active boolean status (admin only)."
    ),
    tools=[
        redeem_discount_code,
        register_user,
        award_loyalty_points,
        process_cart_checkout,
        update_discount_status,
    ],
)

# Root Workflow configuration
root_agent = Workflow(
    name="shopping_assistant_workflow",
    edges=[(START, shopping_agent)],
)

# App configuration
app = App(
    root_agent=root_agent,
    name="app",
)
