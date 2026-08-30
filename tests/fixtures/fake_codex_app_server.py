import json
import sys


def send(payload):
    print(json.dumps(payload), flush=True)


for line in sys.stdin:
    if not line.strip():
        continue
    message = json.loads(line)
    method = message.get("method")
    request_id = message.get("id")
    params = message.get("params", {})

    if method == "initialize":
        send(
            {
                "id": request_id,
                "result": {"userAgent": "fake-codex-app-server"},
            }
        )
    elif method == "initialized":
        continue
    elif method == "thread/start":
        send(
            {
                "id": request_id,
                "result": {"thread": {"id": "thread-persistent-1"}},
            }
        )
    elif method == "thread/resume":
        send(
            {
                "id": request_id,
                "result": {"thread": {"id": params["threadId"]}},
            }
        )
    elif method == "turn/start":
        send(
            {
                "id": request_id,
                "result": {"turn": {"id": "turn-fake-1", "status": "inProgress"}},
            }
        )
        send(
            {
                "id": 900,
                "method": "item/commandExecution/requestApproval",
                "params": {
                    "threadId": params["threadId"],
                    "turnId": "turn-fake-1",
                    "itemId": "command-fake-1",
                    "command": ["unsafe-command"],
                },
            }
        )
        approval_response = json.loads(sys.stdin.readline())
        if approval_response.get("result", {}).get("decision") != "decline":
            raise SystemExit("expected command approval to be declined")
        send(
            {
                "method": "item/agentMessage/delta",
                "params": {
                    "threadId": params["threadId"],
                    "turnId": "turn-fake-1",
                    "itemId": "message-fake-1",
                    "delta": "Persistent App Server result.",
                },
            }
        )
        send(
            {
                "method": "turn/completed",
                "params": {
                    "threadId": params["threadId"],
                    "turn": {
                        "id": "turn-fake-1",
                        "status": "completed",
                        "usage": {
                            "input_tokens": 10,
                            "output_tokens": 5,
                            "total_tokens": 15,
                        },
                    },
                },
            }
        )
