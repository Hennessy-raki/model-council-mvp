from pathlib import Path
import json
import sys


prompt = sys.stdin.read()
if (Path.cwd() / ".git").exists():
    print("connectivity probe used a project checkout", file=sys.stderr)
    raise SystemExit(3)
if "MODEL_COUNCIL_OK" not in prompt:
    print("connectivity prompt was not project-neutral", file=sys.stderr)
    raise SystemExit(4)

events = [
    {"type": "thread.started", "thread_id": "discovery-thread"},
    {
        "type": "item.completed",
        "item": {"type": "agent_message", "text": "MODEL_COUNCIL_OK"},
    },
    {
        "type": "turn.completed",
        "usage": {"input_tokens": 5, "output_tokens": 3},
    },
]
for event in events:
    print(json.dumps(event))
