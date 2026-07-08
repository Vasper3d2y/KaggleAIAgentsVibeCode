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

import pytest
from pydantic import ValidationError

from app.agent import (
    ADMIN_USERS,
    CARTS,
    DISCOUNT_CODES,
    REGISTERED_USERS,
    process_cart_checkout,
    redeem_discount_code,
    update_discount_status,
)


@pytest.fixture(autouse=True)
def setup_state():
    # Setup test state
    REGISTERED_USERS.clear()
    REGISTERED_USERS.update({"shopper_1", "shopper_2"})

    ADMIN_USERS.clear()
    ADMIN_USERS.update({"admin_1", "admin_2"})

    DISCOUNT_CODES.clear()
    DISCOUNT_CODES.update(
        {
            "WELCOME50": {"redeemed": False, "redeemed_by": None, "active": True},
            "SUMMER20": {"redeemed": False, "redeemed_by": None, "active": True},
        }
    )

    CARTS.clear()
    CARTS.update(
        {
            "cart_1": {
                "items": [{"name": "Laptop", "price": 1000.0}],
                "checked_out": False,
                "user_id": "shopper_1",
            }
        }
    )


def test_update_status_success_deactivate():
    # Admin deactivates
    res = update_discount_status(
        user_id="admin_1", discount_code="WELCOME50", active=False
    )
    assert res["status"] == "success"
    assert DISCOUNT_CODES["WELCOME50"]["active"] is False

    # Try to redeem deactivated code -> should fail
    res_redeem = redeem_discount_code(discount_code="WELCOME50", user_id="shopper_1")
    assert res_redeem["status"] == "error"
    assert "deactivated" in res_redeem["message"]

    # Try to checkout with deactivated code -> should fail
    res_checkout = process_cart_checkout(
        user_id="shopper_1", cart_id="cart_1", discount_code="WELCOME50"
    )
    assert res_checkout["status"] == "error"
    assert "deactivated" in res_checkout["message"]


def test_update_status_success_activate():
    # First deactivate
    DISCOUNT_CODES["WELCOME50"]["active"] = False

    # Admin activates
    res = update_discount_status(
        user_id="admin_2", discount_code="WELCOME50", active=True
    )
    assert res["status"] == "success"
    assert DISCOUNT_CODES["WELCOME50"]["active"] is True

    # Try to redeem activated code -> should succeed
    res_redeem = redeem_discount_code(discount_code="WELCOME50", user_id="shopper_1")
    assert res_redeem["status"] == "success"


def test_update_status_unauthorized_user():
    # Standard user shopper_1 tries to update status -> should fail with Security Violation
    res = update_discount_status(
        user_id="shopper_1", discount_code="WELCOME50", active=False
    )
    assert res["status"] == "error"
    assert "Security Violation" in res["message"]
    assert DISCOUNT_CODES["WELCOME50"]["active"] is True  # unchanged


def test_update_status_nonexistent_code():
    res = update_discount_status(
        user_id="admin_1", discount_code="INVALID_CODE", active=False
    )
    assert res["status"] == "error"
    assert "does not exist" in res["message"]


def test_update_status_validation_errors():
    with pytest.raises(ValidationError):
        update_discount_status(user_id="", discount_code="WELCOME50", active=False)

    with pytest.raises(ValidationError):
        update_discount_status(user_id="admin_1", discount_code="", active=False)
