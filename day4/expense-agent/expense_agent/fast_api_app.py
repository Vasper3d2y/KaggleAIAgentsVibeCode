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

import contextlib
import json
import logging
import os
from collections.abc import AsyncIterator

from a2a.server.tasks import InMemoryTaskStore
from dotenv import load_dotenv
from fastapi import FastAPI
from google.adk.cli.fast_api import get_fast_api_app
from google.adk.runners import Runner
from google.genai import types

from expense_agent.app_utils import services
from expense_agent.app_utils.a2a import attach_a2a_routes
from expense_agent.app_utils.reasoning_engine_adapter import (
    attach_reasoning_engine_routes,
)
from expense_agent.app_utils.telemetry import (
    setup_agent_engine_telemetry,
    setup_telemetry,
)
from expense_agent.app_utils.typing import Feedback

# Setup standard python logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

load_dotenv()

# Force agent engine telemetry to false for local no-cloud runs
os.environ["GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY"] = "false"

setup_telemetry()
setup_agent_engine_telemetry()

allow_origins = (
    os.getenv("ALLOW_ORIGINS", "").split(",") if os.getenv("ALLOW_ORIGINS") else None
)

AGENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Runner for the A2A path, sharing the same session/artifact services
    from expense_agent.agent import app as adk_app
    from expense_agent.agent import root_agent

    runner = Runner(
        app=adk_app,
        session_service=services.get_session_service(),
        artifact_service=services.get_artifact_service(),
        auto_create_session=True,
    )
    # Shared by the A2A path and the reasoning_engine adapter routes.
    app.state.runner = runner
    app.state.agent_app_name = adk_app.name
    await attach_a2a_routes(
        app,
        agent=root_agent,
        runner=runner,
        task_store=InMemoryTaskStore(),
        rpc_path=f"/a2a/{adk_app.name}",
    )
    yield


app: FastAPI = get_fast_api_app(
    agents_dir=AGENT_DIR,
    web=True,
    artifact_service_uri=services.ARTIFACT_SERVICE_URI,
    allow_origins=allow_origins,
    session_service_uri=services.SESSION_SERVICE_URI,
    otel_to_cloud=False,
    lifespan=lifespan,
)
app.title = "expense-agent"
app.description = "API for interacting with the Agent expense-agent"

# Proxy routes so the Vertex AI Console Playground can talk to this agent
attach_reasoning_engine_routes(app)


@app.post("/pubsub")
@app.post("/apps/expense_agent/trigger/pubsub")
async def handle_pubsub(payload: dict):
    """Webhook endpoint accepting Pub/Sub push messages and driving the workflow."""
    logger.info(f"Received Pub/Sub payload: {payload}")

    # Extract and normalize the subscription path to a short name
    sub_path = payload.get("subscription", "projects/local/subscriptions/default-sub")
    subscription_short_name = sub_path.split("/")[-1]
    
    # Auto-generate a unique suffix so every webhook trigger creates a fresh session
    import uuid
    session_id = f"{subscription_short_name}-{uuid.uuid4().hex[:6]}"

    # Extract base64 message data
    msg_dict = payload.get("message", {})
    base64_data = msg_dict.get("data")

    # Wrap in data key as expected by the agent's parse_input node
    input_payload = {"data": base64_data}

    runner = app.state.runner

    message = types.Content(
        role="user",
        parts=[types.Part.from_text(text=json.dumps(input_payload))]
    )

    # Run the workflow agent
    events = []
    async for event in runner.run_async(
        user_id="user",
        session_id=session_id,
        new_message=message,
    ):
        events.append(event)

    # Check if workflow paused at Human-in-the-Loop checkpoint
    request_input_event = None
    for e in events:
        if e.content and e.content.parts:
            for part in e.content.parts:
                if part.function_call and part.function_call.name == "adk_request_input":
                    request_input_event = e
                    break

    if request_input_event:
        fc = request_input_event.content.parts[0].function_call
        msg = fc.args.get("message", "")
        logger.info(f"Workflow paused for HITL approval. Session ID: {session_id}")
        return {
            "status": "paused",
            "message": "Workflow paused for human-in-the-loop review.",
            "session_id": session_id,
            "prompt": msg
        }

    # Find final outcome logging string
    outcome_event = next((e for e in events if isinstance(e.output, str) and e.output.startswith("Outcome:")), None)
    outcome_str = outcome_event.output if outcome_event else "No outcome"
    logger.info(f"Workflow completed successfully. Session ID: {session_id}. Outcome: {outcome_str}")

    return {
        "status": "completed",
        "outcome": outcome_str,
        "session_id": session_id
    }


@app.post("/feedback")
def collect_feedback(feedback: Feedback) -> dict[str, str]:
    """Collect and log feedback."""
    logger.info(f"Feedback received: {feedback.model_dump()}")
    return {"status": "success"}


# Main execution
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080)
