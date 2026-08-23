from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .config import load_config
from .orchestrator import Orchestrator


def default_config_path() -> Path:
    return Path(__file__).resolve().parent.parent / "config.example.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="model-council",
        description="Local-first multi-model collaboration orchestrator.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    demo = subparsers.add_parser("demo", help="run the offline mock demonstration")
    demo.add_argument(
        "goal",
        nargs="?",
        default="设计一个可以让不同模型协作完成实际项目的系统",
    )

    run = subparsers.add_parser("run", help="run a goal with a configuration")
    run.add_argument("goal")
    run.add_argument("--config", default=str(default_config_path()))

    agents = subparsers.add_parser("agents", help="list configured agents")
    agents.add_argument("--config", default=str(default_config_path()))

    runs = subparsers.add_parser("runs", help="list recent runs")
    runs.add_argument("--config", default=str(default_config_path()))
    runs.add_argument("--limit", type=int, default=20)

    status = subparsers.add_parser("status", help="show one run and its tasks")
    status.add_argument("run_id")
    status.add_argument("--config", default=str(default_config_path()))
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "demo":
            config = load_config(default_config_path())
            _run_goal(config, args.goal)
        elif args.command == "run":
            config = load_config(args.config)
            _run_goal(config, args.goal)
        elif args.command == "agents":
            config = load_config(args.config)
            for name in config.agents:
                card = config.card(name)
                adapter_type = config.agents[name].get("type", "mock")
                print(
                    f"{name:16} {adapter_type:20} {card.role:12} "
                    f"{', '.join(card.capabilities)}"
                )
        elif args.command == "runs":
            config = load_config(args.config)
            orchestrator = Orchestrator(config)
            for item in orchestrator.store.list_runs(args.limit):
                print(
                    f"{item['id']}  {item['status']:10}  "
                    f"{item['created_at']}  {item['goal']}"
                )
        elif args.command == "status":
            config = load_config(args.config)
            orchestrator = Orchestrator(config)
            run = orchestrator.store.get_run(args.run_id)
            if not run:
                raise SystemExit(f"run {args.run_id!r} not found")
            payload = {
                "run": run,
                "tasks": orchestrator.store.tasks_for_run(args.run_id),
                "artifacts": orchestrator.store.artifacts_for_run(args.run_id),
            }
            print(json.dumps(payload, ensure_ascii=False, indent=2))
    except KeyboardInterrupt:
        raise
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


def _run_goal(config, goal: str) -> None:
    orchestrator = Orchestrator(config)
    result = orchestrator.run(goal)
    print(f"RUN_ID={result.run_id}")
    print(f"FINAL_ARTIFACT={result.final_artifact.path}")
    print()
    print(result.final_text)
