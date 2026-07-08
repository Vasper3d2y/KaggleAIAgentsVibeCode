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
    PROCESSED_TRANSACTIONS,
    REGISTERED_USERS,
    USER_POINTS,
    award_loyalty_points,
)


@pytest.fixture(autouse=True)
def setup_state():
    # Clear state between tests
    USER_POINTS.clear()
    PROCESSED_TRANSACTIONS.clear()
    REGISTERED_USERS.clear()
    # Add a mock registered user
    REGISTERED_USERS.add("shopper_1")


def test_award_points_success():
    res = award_loyalty_points(
        user_id="shopper_1", transaction_id="TX123", transaction_amount=150.50
    )
    assert res["status"] == "success"
    assert "150" in res["message"]
    assert USER_POINTS["shopper_1"] == 150
    assert "TX123" in PROCESSED_TRANSACTIONS


def test_award_points_unregistered_user():
    res = award_loyalty_points(
        user_id="shopper_unregistered",
        transaction_id="TX123",
        transaction_amount=150.50,
    )
    assert res["status"] == "error"
    assert "not registered" in res["message"]
    assert "shopper_unregistered" not in USER_POINTS


def test_award_points_duplicate_transaction():
    res1 = award_loyalty_points(
        user_id="shopper_1", transaction_id="TX123", transaction_amount=150.50
    )
    assert res1["status"] == "success"

    # Try again with same transaction ID
    res2 = award_loyalty_points(
        user_id="shopper_1", transaction_id="TX123", transaction_amount=100.00
    )
    assert res2["status"] == "error"
    assert "already" in res2["message"] and "processed" in res2["message"]
    assert USER_POINTS["shopper_1"] == 150  # Points shouldn't be added twice


def test_award_points_validation_errors():
    # Test negative amount
    with pytest.raises(ValidationError):
        award_loyalty_points(
            user_id="shopper_1", transaction_id="TX123", transaction_amount=-10.0
        )

    # Test zero amount
    with pytest.raises(ValidationError):
        award_loyalty_points(
            user_id="shopper_1", transaction_id="TX123", transaction_amount=0.0
        )

    # Test empty transaction ID
    with pytest.raises(ValidationError):
        award_loyalty_points(
            user_id="shopper_1", transaction_id="", transaction_amount=50.0
        )
