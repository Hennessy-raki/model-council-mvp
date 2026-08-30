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

    if method == "initialize":
        send(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "protocolVersion": "2025-11-25",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "fake-mcp", "version": "1.0"},
                },
            }
        )
    elif method == "notifications/initialized":
        continue
    elif method == "tools/list":
        send(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "tools": [
                        {
                            "name": "echo",
                            "description": "Return local test text",
                            "inputSchema": {"type": "object"},
                        }
                    ]
                },
            }
        )
    elif method == "tools/call":
        arguments = message.get("params", {}).get("arguments", {})
        send(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": str(arguments.get("text", "")),
                        }
                    ],
                    "isError": False,
                },
            }
        )
