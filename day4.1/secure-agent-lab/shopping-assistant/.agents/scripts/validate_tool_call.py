import json
import re
import sys


def main():
    try:
        raw_input = sys.stdin.read()
        if not raw_input:
            # If no input is piped, allow by default
            sys.exit(0)

        try:
            data = json.loads(raw_input)
        except json.JSONDecodeError:
            # If the input is not JSON, check it as a raw command string
            data = {"CommandLine": raw_input}

        # Try to retrieve the command line from common payload locations
        tool_input = data.get("toolInput", data.get("arguments", data))
        command_line = ""

        if isinstance(tool_input, dict):
            command_line = tool_input.get("CommandLine", tool_input.get("command", ""))
        elif isinstance(tool_input, str):
            command_line = tool_input

        if not command_line:
            command_line = data.get("CommandLine", "")

        cmd_str = str(command_line).strip()

        # Block dangerous rm -rf / patterns
        dangerous_patterns = [
            r"rm\s+-rf\s+/",
            r"rm\s+-f\s+/",
            r"rm\s+-r\s+/",
            r"rm\s+-[a-zA-Z]*rf[a-zA-Z]*\s+/",
            r"rm\s+-[a-zA-Z]*fr[a-zA-Z]*\s+/",
        ]

        is_dangerous = False
        for pattern in dangerous_patterns:
            if re.search(pattern, cmd_str):
                is_dangerous = True
                break

        if is_dangerous:
            reason = f"Security Block: Destructive command '{cmd_str}' is blocked by security policy."
            sys.stderr.write(reason + "\n")

            decision = {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                }
            }
            print(json.dumps(decision))
            sys.exit(2)

        # Allow the execution
        decision = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
            }
        }
        print(json.dumps(decision))
        sys.exit(0)

    except Exception as e:
        sys.stderr.write(f"Validation hook error: {e!s}\n")
        decision = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
            }
        }
        print(json.dumps(decision))
        sys.exit(0)


if __name__ == "__main__":
    main()
