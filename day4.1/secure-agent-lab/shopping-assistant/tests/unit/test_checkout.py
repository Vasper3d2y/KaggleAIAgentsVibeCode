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
    CARTS,
    DISCOUNT_CODES,
    REGISTERED_USERS,
    process_cart_checkout,
)


@pytest.fixture(autouse=True)
def setup_state():
    # Clear and setup test state
    REGISTERED_USERS.clear()
    REGISTERED_USERS.update({"shopper_1", "shopper_2"})

    DISCOUNT_CODES.clear()
    DISCOUNT_CODES.update(
        {
            "WELCOME50": {"redeemed": False, "redeemed_by": None},
            "SUMMER20": {"redeemed": False, "redeemed_by": None},
        }
    )

    CARTS.clear()
    CARTS.update(
        {
            "cart_1": {
                "items": [
                    {"name": "Laptop", "price": 1000.0},
                    {"name": "Mouse", "price": 50.0},
                ],
                "checked_out": False,
                "user_id": "shopper_1",
            },
            "cart_empty": {"items": [], "checked_out": False, "user_id": "shopper_1"},
            "cart_checked_out": {
                "items": [{"name": "Book", "price": 20.0}],
                "checked_out": True,
                "user_id": "shopper_1",
            },
        }
    )


def test_checkout_success_no_discount():
    res = process_cart_checkout(user_id="shopper_1", cart_id="cart_1")
    assert res["status"] == "success"
    assert res["total_price"] == 1050.0
    assert CARTS["cart_1"]["checked_out"] is True


def test_checkout_success_with_discount():
    res = process_cart_checkout(
        user_id="shopper_1", cart_id="cart_1", discount_code="WELCOME50"
    )
    assert res["status"] == "success"
    assert res["total_price"] == 525.0
    assert CARTS["cart_1"]["checked_out"] is True
    assert DISCOUNT_CODES["WELCOME50"]["redeemed"] is True
    assert DISCOUNT_CODES["WELCOME50"]["redeemed_by"] == "shopper_1"


def test_checkout_unregistered_user():
    res = process_cart_checkout(user_id="shopper_unregistered", cart_id="cart_1")
    assert res["status"] == "error"
    assert "not registered" in res["message"]
    assert CARTS["cart_1"]["checked_out"] is False


def test_checkout_nonexistent_cart():
    res = process_cart_checkout(user_id="shopper_1", cart_id="cart_missing")
    assert res["status"] == "error"
    assert "does not exist" in res["message"]


def test_checkout_unauthorized_user():
    # shopper_2 attempts to check out shopper_1's cart
    res = process_cart_checkout(user_id="shopper_2", cart_id="cart_1")
    assert res["status"] == "error"
    assert "does not own" in res["message"]
    assert CARTS["cart_1"]["checked_out"] is False


def test_checkout_already_checked_out():
    res = process_cart_checkout(user_id="shopper_1", cart_id="cart_checked_out")
    assert res["status"] == "error"
    assert "already checked out" in res["message"]


def test_checkout_empty_cart():
    res = process_cart_checkout(user_id="shopper_1", cart_id="cart_empty")
    assert res["status"] == "error"
    assert "empty" in res["message"]
    assert CARTS["cart_empty"]["checked_out"] is False


def test_checkout_invalid_discount():
    res = process_cart_checkout(
        user_id="shopper_1", cart_id="cart_1", discount_code="INVALID_CODE"
    )
    assert res["status"] == "error"
    assert "invalid" in res["message"]
    assert CARTS["cart_1"]["checked_out"] is False


def test_checkout_already_redeemed_discount():
    DISCOUNT_CODES["WELCOME50"]["redeemed"] = True
    DISCOUNT_CODES["WELCOME50"]["redeemed_by"] = "shopper_2"

    res = process_cart_checkout(
        user_id="shopper_1", cart_id="cart_1", discount_code="WELCOME50"
    )
    assert res["status"] == "error"
    assert "already been redeemed" in res["message"]
    assert CARTS["cart_1"]["checked_out"] is False


def test_checkout_validation_errors():
    with pytest.raises(ValidationError):
        process_cart_checkout(user_id="", cart_id="cart_1")

    with pytest.raises(ValidationError):
        process_cart_checkout(user_id="shopper_1", cart_id="")
