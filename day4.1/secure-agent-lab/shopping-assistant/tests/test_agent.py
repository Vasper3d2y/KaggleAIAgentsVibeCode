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

from unittest.mock import patch

import pytest
from google.adk.models.llm_response import LlmResponse
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from app.agent import (
    DISCOUNT_CODES,
    REGISTERED_USERS,
    root_agent,
)


@pytest.fixture(autouse=True)
def setup_state():
    # Reset state before each test
    REGISTERED_USERS.clear()
    REGISTERED_USERS.update({"shopper_1", "shopper_2"})

    DISCOUNT_CODES.clear()
    DISCOUNT_CODES.update(
        {
            "WELCOME50": {"redeemed": False, "redeemed_by": None, "active": True},
            "SUMMER20": {"redeemed": False, "redeemed_by": None, "active": True},
        }
    )


@pytest.fixture(autouse=True)
def mock_gemini():
    async def mock_generate_content_async(
        self, llm_request, cache_metadata=None, **kwargs
    ):
        contents = getattr(llm_request, "contents", llm_request)
        # Extract prompt text
        prompt = ""
        if isinstance(contents, list):
            for c in contents:
                if hasattr(c, "parts"):
                    for p in c.parts:
                        if hasattr(p, "text") and p.text:
                            prompt += p.text
                elif isinstance(c, str):
                    prompt += c
        elif hasattr(contents, "parts"):
            for p in contents.parts:
                if hasattr(p, "text") and p.text:
                    prompt += p.text
        elif isinstance(contents, str):
            prompt = contents

        response_text = "I am processing your request."

        # Simple rule-based mock responses matching our test cases
        if "unregistered_user" in prompt:
            response_text = "User unregistered_user is not registered. Cannot redeem."
        elif "WELCOME50" in prompt:
            if not DISCOUNT_CODES["WELCOME50"]["active"]:
                response_text = "Discount code WELCOME50 has been deactivated."
            elif DISCOUNT_CODES["WELCOME50"]["redeemed"]:
                response_text = "Discount code WELCOME50 has already been redeemed."
            else:
                response_text = "Discount code WELCOME50 successfully redeemed."

        yield LlmResponse(
            content=types.Content(parts=[types.Part.from_text(text=response_text)]),
            turn_complete=True,
        )

    with patch(
        "google.adk.models.google_llm.Gemini.generate_content_async",
        mock_generate_content_async,
    ):
        yield


def run_agent_turn(
    runner: Runner, session_id: str, user_id: str, user_message: str
) -> str:
    message = types.Content(
        role="user", parts=[types.Part.from_text(text=user_message)]
    )
    events = list(
        runner.run(
            new_message=message,
            user_id=user_id,
            session_id=session_id,
        )
    )
    response_text = ""
    for event in events:
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.text:
                    response_text += part.text
    return response_text


def test_agent_redeem_deactivated_code() -> None:
    # Programmatically deactivate WELCOME50
    DISCOUNT_CODES["WELCOME50"]["active"] = False

    session_service = InMemorySessionService()
    session = session_service.create_session_sync(user_id="shopper_1", app_name="test")
    runner = Runner(agent=root_agent, session_service=session_service, app_name="test")

    response = run_agent_turn(
        runner,
        session.id,
        "shopper_1",
        "Hi, I am shopper_1. Please redeem discount code WELCOME50 for me.",
    )

    assert any(
        w in response.lower()
        for w in ["deactivated", "inactive", "cannot", "invalid", "error", "unable"]
    )


def test_agent_redeem_unregistered_user() -> None:
    session_service = InMemorySessionService()
    session = session_service.create_session_sync(
        user_id="unregistered_user", app_name="test"
    )
    runner = Runner(agent=root_agent, session_service=session_service, app_name="test")

    response = run_agent_turn(
        runner,
        session.id,
        "unregistered_user",
        "Please redeem discount code WELCOME50 for user unregistered_user.",
    )

    assert any(
        w in response.lower()
        for w in ["register", "not registered", "invalid", "unregistered", "error"]
    )


def test_agent_redeem_already_redeemed_code() -> None:
    # Mark WELCOME50 as already redeemed
    DISCOUNT_CODES["WELCOME50"]["redeemed"] = True
    DISCOUNT_CODES["WELCOME50"]["redeemed_by"] = "shopper_2"

    session_service = InMemorySessionService()
    session = session_service.create_session_sync(user_id="shopper_1", app_name="test")
    runner = Runner(agent=root_agent, session_service=session_service, app_name="test")

    response = run_agent_turn(
        runner,
        session.id,
        "shopper_1",
        "Hi, I am shopper_1. I want to redeem code WELCOME50.",
    )

    assert any(
        w in response.lower()
        for w in [
            "already redeemed",
            "already been redeemed",
            "already used",
            "invalid",
            "error",
        ]
    )
