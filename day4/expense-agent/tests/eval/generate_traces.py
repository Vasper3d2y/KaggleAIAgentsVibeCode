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

import asyncio
import base64
import json
import os
import sys
from unittest.mock import patch

from google.adk.runners import InMemoryRunner
from google.genai import types

# Add workspace directory to python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from expense_agent.agent import app


def get_request_input_event(events):
    for e in events:
        if e.content and e.content.parts:
            for part in e.content.parts:
                if part.function_call and part.function_call.name == "adk_request_input":
                    return e
    return None


def content_to_dict(content) -> dict:
    if not content:
        return None
    parts_list = []
    for part in content.parts:
        part_dict = {}
        if part.text:
            part_dict["text"] = part.text
        elif part.function_call:
            part_dict["function_call"] = {
                "name": part.function_call.name,
                "args": part.function_call.args
            }
        elif part.function_response:
            part_dict["function_response"] = {
                "name": part.function_response.name,
                "response": part.function_response.response
            }
        parts_list.append(part_dict)
    return {
        "role": content.role or "model",
        "parts": parts_list
    }


def event_to_turn_event(event) -> dict:
    author = event.agent_id if hasattr(event, "agent_id") and event.agent_id else "expense_agent"
    
    if event.content:
        content = content_to_dict(event.content)
    else:
        content = {
            "role": "model",
            "parts": [{"text": str(event.output)}]
        }
        
    return {
        "author": author,
        "content": content
    }


async def run_scenario(case: dict) -> dict:
    runner = InMemoryRunner(app=app)
    session = await runner.session_service.create_session(
        app_name="expense_agent", user_id="user"
    )
    
    case_id = case["eval_case_id"]
    prompt_content = case["prompt"]
    
    # Parse the prompt content from dataset
    user_prompt = types.Content(
        role="user",
        parts=[types.Part.from_text(text=p["text"]) for p in prompt_content["parts"]]
    )
    
    turns = []
    
    # Turn 0: User query
    turn0_events = [
        {
            "author": "user",
            "content": content_to_dict(user_prompt)
        }
    ]
    
    # Drive execution
    events = []
    async for event in runner.run_async(
        user_id="user",
        session_id=session.id,
        new_message=user_prompt,
    ):
        events.append(event)
        
    for e in events:
        turn0_events.append(event_to_turn_event(e))
        
    turns.append({
        "turn_index": 0,
        "events": turn0_events
    })
    
    # Intercept human-in-the-loop steps and automate approval decisions
    request_input_event = get_request_input_event(events)
    if request_input_event:
        # Determine choice based on security rules in case id
        decision = "reject" if "prompt_injection" in case_id else "approve"
        
        resume_message = types.Content(
            role="user",
            parts=[
                types.Part(
                    function_response=types.FunctionResponse(
                        name="adk_request_input",
                        id="approval",
                        response={"output": decision}
                    )
                )
            ]
        )
        
        turn1_events = [
            {
                "author": "user",
                "content": content_to_dict(resume_message)
            }
        ]
        
        invocation_id = events[0].invocation_id
        resume_events = []
        async for event in runner.run_async(
            user_id="user",
            session_id=session.id,
            invocation_id=invocation_id,
            new_message=resume_message,
        ):
            resume_events.append(event)
            
        for e in resume_events:
            turn1_events.append(event_to_turn_event(e))
            
        turns.append({
            "turn_index": 1,
            "events": turn1_events
        })
        
    # Extract final text outcome to satisfy responses schema requirement
    final_text = ""
    for turn in reversed(turns):
        for event in reversed(turn["events"]):
            if event["author"] == "expense_agent":
                parts = event["content"]["parts"]
                for part in parts:
                    if "text" in part and part["text"] and part["text"].startswith("Outcome:"):
                        final_text = part["text"]
                        break
                if final_text:
                    break
        if final_text:
            break
            
    # Fallback to last text if no Outcome prefix was found
    if not final_text:
        for turn in reversed(turns):
            for event in reversed(turn["events"]):
                if event["author"] == "expense_agent":
                    parts = event["content"]["parts"]
                    for part in parts:
                        if "text" in part and part["text"]:
                            final_text = part["text"]
                            break
                    if final_text:
                        break
            if final_text:
                break
                
    responses = [
        {
            "response": {
                "role": "model",
                "parts": [{"text": final_text or "No response"}]
            }
        }
    ]
        
    return {
        "eval_case_id": case_id,
        "prompt": content_to_dict(user_prompt),
        "responses": responses,
        "agent_data": {
            "agents": {
                "expense_agent": {
                    "agent_id": "expense_agent",
                    "agent_type": "Workflow"
                }
            },
            "turns": turns
        }
    }


async def main():
    print("Loading basic-dataset.json...")
    with open("tests/eval/datasets/basic-dataset.json") as f:
        dataset = json.load(f)
        
    eval_cases = dataset["eval_cases"]
    graded_cases = []
    
    # Mock Gemini.generate_content_async to run locally
    from google.adk.models.llm_response import LlmResponse
    from google.genai import types as genai_types

    async def mock_generate_content_async(*args, **kwargs):
        mock_val = {
            "risk_score": 1,
            "risk_factors": ["Standard business expense"],
            "alert_raised": False,
            "reasoning": "Reasonable amount for a business expense."
        }
        yield LlmResponse(
            content=genai_types.Content(
                role="model",
                parts=[genai_types.Part.from_text(text=json.dumps(mock_val))]
            )
        )

    with patch("google.adk.models.google_llm.Gemini.generate_content_async", side_effect=mock_generate_content_async):
        for case in eval_cases:
            print(f"Running evaluation case: {case['eval_case_id']}...")
            graded_case = await run_scenario(case)
            graded_cases.append(graded_case)
            
    output_dir = "artifacts/traces"
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, "generated_traces.json")
    
    print(f"Serializing traces to {output_file}...")
    with open(output_file, "w") as f:
        json.dump({"eval_cases": graded_cases}, f, indent=2)
    print("Traces generation completed successfully.")


if __name__ == "__main__":
    asyncio.run(main())
