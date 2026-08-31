import json
import sys


def send(payload):
    print(json.dumps(payload), flush=True)


usage_mode = "last"
if "--usage-mode" in sys.argv:
    index = sys.argv.index("--usage-mode")
    usage_mode = sys.argv[index + 1]


for line in sys.stdin:
    if not line.strip():
        continue
    message = json.loads(line)
    method = message.get("method")
    request_id = message.get("id")
    params = message.get("params", {})

    if method == "initialize":
        send({"id": request_id, "result": {"userAgent": "fake-board14-plan"}})
    elif method == "initialized":
        continue
    elif method == "thread/start":
        if params.get("sandbox") != "read-only":
            raise SystemExit("expected read-only sandbox")
        if params.get("approvalPolicy") != "never":
            raise SystemExit("expected never approval policy")
        send({"id": request_id, "result": {"thread": {"id": "fixture-thread"}}})
    elif method == "turn/start":
        prompt = params["input"][0]["text"]
        expected = (
            "Create exactly two independent synthetic tasks for local fake "
            "workers. Return only the required JSON plan."
        )
        if prompt != expected:
            raise SystemExit("unexpected prompt")
        send(
            {
                "id": request_id,
                "result": {"turn": {"id": "fixture-turn", "status": "inProgress"}},
            }
        )
        plan = {
            "tasks": [
                {"key": "work_1", "agent": "fake-worker-a"},
                {"key": "work_2", "agent": "fake-worker-b"},
            ]
        }
        send(
            {
                "method": "item/completed",
                "params": {
                    "turnId": "fixture-turn",
                    "item": {
                        "type": "agentMessage",
                        "text": json.dumps(plan, separators=(",", ":")),
                    },
                },
            }
        )
        usage = {
            "inputTokens": 10,
            "outputTokens": 5,
            "totalTokens": 15,
        }
        if usage_mode == "incomplete":
            usage = {
                "inputTokens": 10,
                "totalTokens": 15,
            }
        if usage_mode in {"last", "total"}:
            send(
                {
                    "method": "thread/tokenUsage/updated",
                    "params": {
                        "turnId": "fixture-turn",
                        "tokenUsage": {usage_mode: usage},
                    },
                }
            )
        elif usage_mode == "direct":
            send(
                {
                    "method": "thread/tokenUsage/updated",
                    "params": {
                        "turnId": "fixture-turn",
                        "tokenUsage": usage,
                    },
                }
            )
        elif usage_mode == "incomplete":
            send(
                {
                    "method": "thread/tokenUsage/updated",
                    "params": {
                        "turnId": "fixture-turn",
                        "tokenUsage": {"last": usage},
                    },
                }
            )
        completed_turn = {"id": "fixture-turn", "status": "completed"}
        if usage_mode == "completed":
            completed_turn["usage"] = usage
        send(
            {
                "method": "turn/completed",
                "params": {
                    "turn": completed_turn
                },
            }
        )
