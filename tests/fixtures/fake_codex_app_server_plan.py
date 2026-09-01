import json
import sys


def send(payload):
    print(json.dumps(payload), flush=True)


usage_mode = "last"
if "--usage-mode" in sys.argv:
    index = sys.argv.index("--usage-mode")
    usage_mode = sys.argv[index + 1]

plan_mode = "valid"
if "--plan-mode" in sys.argv:
    index = sys.argv.index("--plan-mode")
    plan_mode = sys.argv[index + 1]

input_tokens = 10
if "--input-tokens" in sys.argv:
    index = sys.argv.index("--input-tokens")
    input_tokens = int(sys.argv[index + 1])

output_tokens = 5
if "--output-tokens" in sys.argv:
    index = sys.argv.index("--output-tokens")
    output_tokens = int(sys.argv[index + 1])


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
            "You are a local synthetic Manager. Return only one JSON object; "
            "do not return Markdown, commentary, or code fences. The top-level "
            'object must contain exactly one property, "tasks". "tasks" must be '
            "an array of exactly two task objects. Use each Worker Agent exactly "
            'once: "fake-worker-a" and "fake-worker-b". Each task object must '
            'contain exactly the properties "key", "agent", and "depends_on"; '
            '"key" must be a non-empty unique string; "agent" must be one of '
            'the two Worker IDs above; and "depends_on" must be exactly []. Do '
            "not add permissions, tools, workspace, files, Artifacts, Git, "
            "command, or any other control field."
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
                {
                    "key": "work_1",
                    "agent": "fake-worker-a",
                    "depends_on": [],
                },
                {
                    "key": "work_2",
                    "agent": "fake-worker-b",
                    "depends_on": [],
                },
            ]
        }
        if plan_mode == "invalid_json":
            plan_text = "not-json"
        else:
            if plan_mode == "missing_tasks":
                plan = {"plan": []}
            elif plan_mode == "task_count":
                plan = {"tasks": [plan["tasks"][0]]}
            elif plan_mode == "agent_mismatch":
                plan["tasks"][1]["agent"] = "unexpected-worker"
            elif plan_mode == "duplicate_key":
                plan["tasks"][1]["key"] = "work_1"
            elif plan_mode == "dependent":
                plan["tasks"][1]["depends_on"] = ["work_1"]
            elif plan_mode == "null_dependency":
                plan["tasks"][1]["depends_on"] = None
            elif plan_mode == "unsafe_field":
                plan["tasks"][0]["tools"] = ["shell"]
            elif plan_mode == "root_fields":
                plan["summary"] = "not allowed"
            elif plan_mode == "task_fields":
                plan["tasks"][0]["title"] = "not allowed"
            plan_text = json.dumps(plan, separators=(",", ":"))
        send(
            {
                "method": "item/completed",
                "params": {
                    "turnId": "fixture-turn",
                    "item": {
                        "type": "agentMessage",
                        "text": plan_text,
                    },
                },
            }
        )
        usage = {
            "inputTokens": input_tokens,
            "outputTokens": output_tokens,
            "totalTokens": input_tokens + output_tokens,
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
