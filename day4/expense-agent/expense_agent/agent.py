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

import base64
import json
import re
from typing import Any

from google.adk.workflow import Workflow, node
from google.adk.agents import LlmAgent
from google.adk.apps import App
from google.adk.events.event import Event
from google.adk.events.request_input import RequestInput
from google.adk.agents.context import Context
from google.genai import types
from pydantic import BaseModel, Field

from expense_agent.config import ExpenseConfig

# Regex patterns for SSN and Credit Card numbers
SSN_REGEX = re.compile(r'\b\d{3}-\d{2}-\d{4}\b')
CC_REGEX = re.compile(r'\b(?:\d[ -]*?){13,19}\b')

# Keyword patterns to detect prompt injection attempts in descriptions
INJECTION_KEYWORDS = [
    "ignore previous instructions",
    "ignore all instructions",
    "bypass",
    "override",
    "system override",
    "auto-approve",
    "auto approve",
    "approve this expense",
    "do not review",
    "bypass verification",
    "you must approve",
    "set status to approved",
    "assistant:",
    "system:",
    "user:"
]


class ExpenseDetails(BaseModel):
    amount: float = Field(description="The numeric amount of the expense")
    currency: str = Field(description="The currency of the expense, e.g. USD, EUR, INR")
    merchant: str = Field(description="The vendor/merchant name")
    category: str = Field(description="The category, e.g. Meals, Travel, Software, Office Supplies")
    description: str = Field(description="Brief description of the expense")


class RiskReviewResult(BaseModel):
    risk_score: int = Field(description="Risk score from 1 (lowest risk) to 5 (highest risk)")
    risk_factors: list[str] = Field(description="Key risk factors or anomalies identified in the expense report")
    alert_raised: bool = Field(description="True if a security or policy alert is raised due to high risk")
    reasoning: str = Field(description="Reasoning and justification for the risk score and judgment")


def scrub_pii(text: str) -> tuple[str, list[str]]:
    """Scrubs SSNs and Credit Card numbers from the text and returns scrubbed text & redacted categories."""
    redacted_categories = []
    scrubbed, count_ssn = SSN_REGEX.subn("[REDACTED SSN]", text)
    if count_ssn > 0:
        redacted_categories.append("SSN")

    scrubbed, count_cc = CC_REGEX.subn("[REDACTED CREDIT CARD]", scrubbed)
    if count_cc > 0:
        redacted_categories.append("Credit Card")

    return scrubbed, redacted_categories


def detect_injection(text: str) -> bool:
    """Detects simple instruction override/prompt injection keywords."""
    normalized = text.lower()
    return any(kw in normalized for kw in INJECTION_KEYWORDS)


def parse_input(node_input: Any) -> Event:
    """Parses raw Pub/Sub or testing JSON events, decoding base64 data key if needed."""
    raw_data = None
    if isinstance(node_input, dict):
        raw_data = node_input
    elif hasattr(node_input, "parts") and node_input.parts:
        text = "".join(p.text for p in node_input.parts if hasattr(p, "text"))
        try:
            raw_data = json.loads(text)
        except Exception:
            raw_data = {"data": text}
    elif isinstance(node_input, str):
        try:
            raw_data = json.loads(node_input)
        except Exception:
            raw_data = {"data": node_input}
    else:
        raw_data = str(node_input)

    if isinstance(raw_data, dict):
        if "data" in raw_data:
            data_val = raw_data["data"]
        else:
            data_val = raw_data
    else:
        data_val = raw_data

    # Decode base64 if it is a string representing base64 data
    if isinstance(data_val, str):
        try:
            decoded_bytes = base64.b64decode(data_val, validate=True)
            decoded_text = decoded_bytes.decode('utf-8')
            try:
                data_val = json.loads(decoded_text)
            except Exception:
                try:
                    # Fallback for backslash-escaped JSON strings
                    data_val = json.loads(decoded_text.replace('\\"', '"'))
                except Exception:
                    data_val = {"description": decoded_text}
        except Exception:
            try:
                data_val = json.loads(data_val)
            except Exception:
                try:
                    data_val = json.loads(data_val.replace('\\"', '"'))
                except Exception:
                    data_val = {"description": data_val}

    if not isinstance(data_val, dict):
        raise ValueError(f"Expense details must be a JSON object, got: {type(data_val)}")

    expense_data = {
        "amount": float(data_val.get("amount", 0.0)),
        "submitter": str(data_val.get("submitter", "Unknown")),
        "category": str(data_val.get("category", "General")),
        "description": str(data_val.get("description", "No description")),
        "date": str(data_val.get("date", "")),
    }

    return Event(output=expense_data, state={"expense_details": expense_data})


def security_checkpoint(node_input: dict) -> Event:
    """Security node that scrubs PII and checks for prompt injection."""
    description = node_input.get("description", "")

    # 1. Scrub PII
    scrubbed_desc, redacted_cats = scrub_pii(description)

    # Update description in a copy of the expense data
    clean_expense = dict(node_input)
    clean_expense["description"] = scrubbed_desc

    # 2. Check for prompt injection
    is_injection = detect_injection(description)

    state_updates = {
        "expense_details": clean_expense,
        "redacted_categories": redacted_cats,
    }

    if is_injection:
        state_updates["security_event"] = True
        return Event(output=clean_expense, route="security_alert", state=state_updates)
    else:
        return Event(output=clean_expense, route="clean", state=state_updates)


def evaluate_expense(node_input: dict) -> Event:
    """Applies threshold rule in Python (no LLM involved)."""
    amount = node_input.get("amount", 0.0)
    if amount < ExpenseConfig.THRESHOLD:
        return Event(output=node_input, route="auto_approve")
    else:
        return Event(output=node_input, route="require_llm_review")


llm_risk_review = LlmAgent(
    name="llm_risk_review",
    model=ExpenseConfig.MODEL,
    instruction="""Review the provided expense details for potential risks, anomalies, or policy violations.
Identify:
1. Risk score (1 to 5)
2. Risk factors/violations (e.g. suspicious description, unusual category, weird amount)
3. Whether to raise an alert (True/False)
4. Your detailed reasoning.

You must output structured data matching the RiskReviewResult schema.""",
    output_schema=RiskReviewResult,
    output_key="risk_review",
)


@node(rerun_on_resume=True)
async def human_approval(ctx: Context, node_input: dict):
    """Presents LLM risk review output or security alert to user and requests approval/rejection."""
    expense = ctx.state.get("expense_details", {})
    is_security_event = ctx.state.get("security_event", False)
    redacted = ctx.state.get("redacted_categories", [])

    if not ctx.resume_inputs or "approval" not in ctx.resume_inputs:
        redaction_str = f" (Redacted: {', '.join(redacted)})" if redacted else ""

        if is_security_event:
            msg = (
                f"🚨 SECURITY ALERT: PROMPT INJECTION DETECTED!\n"
                f"The expense description contains suspected prompt injection. LLM review was bypassed.\n\n"
                f"Submitter: {expense.get('submitter')}\n"
                f"Amount: ${expense.get('amount')}\n"
                f"Category: {expense.get('category')}\n"
                f"Description: {expense.get('description')}{redaction_str}\n"
                f"Date: {expense.get('date')}\n\n"
                f"Reply with 'approve' or 'reject' to finalize."
            )
        else:
            msg = (
                f"🚨 EXPENSE REVIEW REQUIRED\n"
                f"Submitter: {expense.get('submitter')}\n"
                f"Amount: ${expense.get('amount')}\n"
                f"Category: {expense.get('category')}\n"
                f"Description: {expense.get('description')}{redaction_str}\n"
                f"Date: {expense.get('date')}\n\n"
                f"LLM Risk Report:\n"
                f"- Risk Score: {node_input.get('risk_score')}/5\n"
                f"- Alert Raised: {node_input.get('alert_raised')}\n"
                f"- Risk Factors: {', '.join(node_input.get('risk_factors', []))}\n"
                f"- Reasoning: {node_input.get('reasoning')}\n\n"
                f"Reply with 'approve' or 'reject' to finalize."
            )
        yield RequestInput(interrupt_id="approval", message=msg)
        return

    approval_resp = ctx.resume_inputs["approval"]
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
        yield Event(output=expense, route="approved")
    else:
        yield Event(output=expense, route="rejected")


def record_auto_approve(node_input: dict) -> Event:
    """Outcome logger for automatically approved expenses."""
    msg = f"Outcome: Auto-Approved (under ${ExpenseConfig.THRESHOLD}) for {node_input.get('submitter')} - ${node_input.get('amount')}"
    return Event(output=msg, state={"outcome": msg})


def record_human_approve(ctx: Context, node_input: dict) -> Event:
    """Outcome logger for manually approved expenses."""
    is_sec = ctx.state.get("security_event", False)
    sec_suffix = " (Security alert flagged)" if is_sec else ""
    msg = f"Outcome: Approved (Manually approved) for {node_input.get('submitter')} - ${node_input.get('amount')}{sec_suffix}"
    return Event(output=msg, state={"outcome": msg})


def record_human_reject(ctx: Context, node_input: dict) -> Event:
    """Outcome logger for manually rejected expenses."""
    is_sec = ctx.state.get("security_event", False)
    sec_suffix = " (Security alert flagged)" if is_sec else ""
    msg = f"Outcome: Rejected (Manually rejected) for {node_input.get('submitter')} - ${node_input.get('amount')}{sec_suffix}"
    return Event(output=msg, state={"outcome": msg})


root_agent = Workflow(
    name="expense_approval_workflow",
    edges=[
        ('START', parse_input),
        (parse_input, security_checkpoint),
        (security_checkpoint, {"clean": evaluate_expense, "security_alert": human_approval}),
        (evaluate_expense, {"auto_approve": record_auto_approve, "require_llm_review": llm_risk_review}),
        (llm_risk_review, human_approval),
        (human_approval, {"approved": record_human_approve, "rejected": record_human_reject}),
    ],
)

app = App(
    root_agent=root_agent,
    name="expense_agent",
)
