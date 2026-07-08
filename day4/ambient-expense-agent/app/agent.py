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

from google.adk.workflow import Workflow, node
from google.adk.agents import LlmAgent
from google.adk.apps import App
from google.adk.events.event import Event
from google.adk.events.request_input import RequestInput
from google.adk.agents.context import Context
from google.genai import types
from pydantic import BaseModel, Field


class ExpenseDetails(BaseModel):
    amount: float = Field(description="The numeric amount of the expense")
    currency: str = Field(description="The currency of the expense, e.g. USD, EUR, INR")
    merchant: str = Field(description="The vendor/merchant name")
    category: str = Field(description="The category, e.g. Meals, Travel, Software, Office Supplies")
    description: str = Field(description="Brief description of the expense")


expense_extractor = LlmAgent(
    name="expense_extractor",
    model="gemini-flash-latest",
    instruction="Extract structured expense details from the user's message. Identify the amount, currency, merchant, category, and description.",
    output_schema=ExpenseDetails,
    output_key="expense_details",
)


@node(rerun_on_resume=True)
async def verify_expense(ctx: Context, node_input: dict):
    """Confirm the expense with the user before saving."""
    if not ctx.resume_inputs or "approval" not in ctx.resume_inputs:
        msg = (
            f"Please confirm the following expense:\n"
            f"- Merchant: {node_input.get('merchant')}\n"
            f"- Amount: {node_input.get('amount')} {node_input.get('currency')}\n"
            f"- Category: {node_input.get('category')}\n"
            f"- Description: {node_input.get('description')}\n\n"
            f"Reply with 'approve' or 'reject' to proceed."
        )
        yield RequestInput(interrupt_id="approval", message=msg)
        return

    approval_resp = ctx.resume_inputs["approval"]
    # The response can be a string, or a structure containing text.
    # Convert response to string and check contents.
    resp_text = ""
    if isinstance(approval_resp, str):
        resp_text = approval_resp
    elif hasattr(approval_resp, "text"):
        resp_text = approval_resp.text
    elif hasattr(approval_resp, "parts") and approval_resp.parts:
        resp_text = "".join(p.text for p in approval_resp.parts if hasattr(p, "text"))
    else:
        resp_text = str(approval_resp)

    if "approve" in resp_text.lower():
        yield Event(output=node_input, route="approved")
    else:
        yield Event(output=node_input, route="rejected")


def save_expense(node_input: dict) -> str:
    """Save the approved expense details."""
    return f"Expense of {node_input.get('amount')} {node_input.get('currency')} for {node_input.get('merchant')} has been successfully recorded."


def reject_expense(node_input: dict) -> str:
    """Handle rejected expense."""
    return "Expense recording cancelled by user."


root_agent = Workflow(
    name="ambient_expense_workflow",
    edges=[
        ('START', expense_extractor),
        (expense_extractor, verify_expense),
        (verify_expense, {"approved": save_expense, "rejected": reject_expense}),
    ],
)

app = App(
    root_agent=root_agent,
    name="app",
)
