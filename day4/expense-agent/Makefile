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

.PHONY: install playground run run-web generate-traces grade

install:
	uv python pin 3.11
	uv sync

playground:
	uv run agents-cli playground

run-web:
	uv run python -m expense_agent.fast_api_app

generate-traces:
	uv run python tests/eval/generate_traces.py

grade:
	/Users/ayushk/.local/share/uv/tools/google-agents-cli/bin/python tests/eval/grade_wrapper.py eval grade --traces artifacts/traces/generated_traces.json --config tests/eval/eval_config.yaml
