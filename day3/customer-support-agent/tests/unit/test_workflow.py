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
from google.adk.events.event import Event
from google.adk.runners import InMemoryRunner
from google.genai import types

from app.agent import app


async def mock_llm_agent_run_impl(self, *, ctx, node_input):
    # Retrieve the text from node_input or history
    text = ""
    if hasattr(node_input, "parts") and node_input.parts:
        text = "".join(part.text for part in node_input.parts if part.text)
    elif isinstance(node_input, str):
        text = node_input
    else:
        text = str(node_input)

    if self.name == "classifier_agent":
        # Simple shipping keyword routing logic for testing
        is_shipping = any(
            word in text.lower()
            for word in ["shipping", "rate", "track", "deliver", "return", "new york"]
        )
        yield Event(output={"is_shipping_related": is_shipping})
    elif self.name == "shipping_faq_agent":
        answer = f"Mock FAQ answer for query: {text}"
        yield Event(
            content=types.Content(
                role="model", parts=[types.Part.from_text(text=answer)]
            ),
            output=answer,
        )


@pytest.mark.asyncio
@patch("google.adk.agents.llm_agent.LlmAgent._run_impl", new=mock_llm_agent_run_impl)
async def test_shipping_related_flow():
    runner = InMemoryRunner(app=app)
    session = await runner.session_service.create_session(
        app_name="app", user_id="test_user"
    )

    events = []
    async for event in runner.run_async(
        user_id="test_user",
        session_id=session.id,
        new_message=types.Content(
            role="user",
            parts=[
                types.Part.from_text(
                    text="What are the rates for shipping to New York?"
                )
            ],
        ),
    ):
        events.append(event)

    # Verify that we got a mock FAQ answer
    outputs = [e.output for e in events if e.output is not None]
    assert any("Mock FAQ answer for query:" in str(o) for o in outputs)
    assert not any(
        "I'm sorry, I can only help with shipping-related" in str(o) for o in outputs
    )


@pytest.mark.asyncio
@patch("google.adk.agents.llm_agent.LlmAgent._run_impl", new=mock_llm_agent_run_impl)
async def test_unrelated_flow():
    runner = InMemoryRunner(app=app)
    session = await runner.session_service.create_session(
        app_name="app", user_id="test_user"
    )

    events = []
    async for event in runner.run_async(
        user_id="test_user",
        session_id=session.id,
        new_message=types.Content(
            role="user",
            parts=[types.Part.from_text(text="Who won the 2024 World Series?")],
        ),
    ):
        events.append(event)

    # Verify that the flow routed to decline_node
    outputs = [e.output for e in events if e.output is not None]
    assert any(
        "I'm sorry, I can only help with shipping-related" in str(o) for o in outputs
    )
    assert not any("Mock FAQ answer for query:" in str(o) for o in outputs)
