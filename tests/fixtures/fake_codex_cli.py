import json
import sys


prompt = sys.stdin.read()
if not prompt.strip():
    raise SystemExit("expected prompt on stdin")

events = [
    {
        "type": "thread.started",
        "thread_id": "thread-test-123",
    },
    {
        "type": "item.completed",
        "item": {
            "id": "item-1",
            "type": "reasoning",
            "text": "internal reasoning is not the final result",
        },
    },
    {
        "type": "item.completed",
        "item": {
            "id": "item-2",
            "type": "agent_message",
            "text": "# Architecture result\n\nUse deterministic boundaries.",
        },
    },
    {
        "type": "turn.completed",
        "usage": {
            "input_tokens": 120,
            "cached_input_tokens": 20,
            "output_tokens": 35,
        },
    },
]

for event in events:
    print(json.dumps(event))
print("fixture diagnostic", file=sys.stderr)
