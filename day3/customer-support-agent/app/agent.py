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

from typing import Any
from google.adk.agents import Context, LlmAgent
from google.adk.apps import App
from google.adk.models import Gemini
from google.adk.workflow import Workflow, START
from google.adk.events.event import Event
from google.genai import types
from pydantic import BaseModel, Field


# 1. Classification Output schema
class QueryClassification(BaseModel):
    is_shipping_related: bool = Field(
        description="True if the query is related to shipping (rates, tracking, delivery, returns), False otherwise."
    )


# 2. Classifier Agent
classifier_agent = LlmAgent(
    name="classifier_agent",
    model=Gemini(
        model="gemini-2.5-flash",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction="Classify the user's query. Determine if it is related to shipping (rates, tracking, delivery, returns) or unrelated.",
    output_schema=QueryClassification,
)


# 3. Router Node
def route_query(ctx: Context, node_input: QueryClassification) -> Event:
    user_text = ""
    if ctx.user_content and ctx.user_content.parts:
        user_text = "".join(part.text for part in ctx.user_content.parts if part.text)

    if node_input.is_shipping_related:
        return Event(output=user_text, route="shipping")  # type: ignore
    return Event(output=user_text, route="unrelated")  # type: ignore


# 4. Shipping FAQ Agent
shipping_faq_agent = LlmAgent(
    name="shipping_faq_agent",
    model=Gemini(
        model="gemini-2.5-flash",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=(
        "You are a customer support shipping FAQ representative. "
        "Politely and accurately answer the user's shipping-related questions "
        "(e.g., shipping rates, package tracking, delivery estimates, return policies). "
        "Make your responses about shipping rates extra playful, enthusiastic, and full of fun emojis (🚚, 📦, 🎉, ✨)! "
        "Be sure to highlight that we offer free shipping on orders over $50! "
        "If you do not have specific real-time information (like a tracking status), "
        "provide helpful mock details or request clarification."
    ),
)


# 5. Decline Node (Function Node)
def decline_node(node_input: Any) -> Event:
    text = (
        "I'm sorry, I can only help with shipping-related inquiries (rates, tracking, delivery, or returns). "
        "Please let me know if you have a shipping question!"
    )
    return Event(
        content=types.Content(role="model", parts=[types.Part.from_text(text=text)]),
        output=text,
    )


# 6. Workflow and App definition
root_agent = Workflow(
    name="customer_support_workflow",
    edges=[
        (START, classifier_agent),
        (classifier_agent, route_query),
        (route_query, {"shipping": shipping_faq_agent, "unrelated": decline_node}),
    ],
)

app = App(
    root_agent=root_agent,
    name="app",
)
