from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .adapters import build_adapters
from .config import load_config
from .orchestrator import Orchestrator
from .registry import RegistryService
from .store import CouncilStore


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

    doctor = subparsers.add_parser(
        "doctor",
        help="validate configured adapters without invoking any model",
    )
    doctor.add_argument("--config", default=str(default_config_path()))

    settings = subparsers.add_parser(
        "settings",
        help="inspect or update the persistent settings registry",
    )
    settings_commands = settings.add_subparsers(
        dest="settings_command",
        required=True,
    )
    settings_show = settings_commands.add_parser(
        "show",
        help="show providers, models, agents, roles and settings",
    )
    settings_show.add_argument("--config", default=str(default_config_path()))
    settings_sync = settings_commands.add_parser(
        "sync",
        help="synchronize the JSON seed configuration into SQLite",
    )
    settings_sync.add_argument("--config", default=str(default_config_path()))
    settings_assign = settings_commands.add_parser(
        "assign",
        help="persist a user role assignment",
    )
    settings_assign.add_argument("role_key")
    settings_assign.add_argument(
        "--mode",
        required=True,
        choices=("manual", "auto", "hybrid"),
    )
    settings_assign.add_argument("--agent")
    settings_assign.add_argument("--model")
    settings_assign.add_argument("--locked", action="store_true")
    settings_assign.add_argument("--config", default=str(default_config_path()))
    settings_set = settings_commands.add_parser(
        "set",
        help="persist one application setting as JSON or text",
    )
    settings_set.add_argument("key")
    settings_set.add_argument("value")
    settings_set.add_argument("--config", default=str(default_config_path()))

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
        elif args.command == "doctor":
            config = load_config(args.config)
            diagnostics = {
                name: adapter.diagnose()
                for name, adapter in build_adapters(config).items()
            }
            print(json.dumps(diagnostics, ensure_ascii=False, indent=2))
            if not all(item.get("ok", False) for item in diagnostics.values()):
                raise SystemExit(2)
        elif args.command == "settings":
            config = load_config(args.config)
            registry = _load_registry(config)
            if args.settings_command == "show":
                print(
                    json.dumps(
                        registry.snapshot(),
                        ensure_ascii=False,
                        indent=2,
                    )
                )
            elif args.settings_command == "sync":
                counts = registry.sync_from_config(config)
                print(json.dumps(counts, ensure_ascii=False, indent=2))
            elif args.settings_command == "assign":
                registry.assign_role(
                    role_key=args.role_key,
                    mode=args.mode,
                    agent_id=args.agent,
                    model_id=args.model,
                    locked=args.locked,
                )
                print(
                    json.dumps(
                        registry.snapshot()["roles"],
                        ensure_ascii=False,
                        indent=2,
                    )
                )
            elif args.settings_command == "set":
                registry.set_setting(args.key, _parse_setting_value(args.value))
                print(
                    json.dumps(
                        registry.snapshot()["settings"][args.key],
                        ensure_ascii=False,
                        indent=2,
                    )
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
                "messages": orchestrator.store.messages_for_run(args.run_id),
                "artifacts": orchestrator.store.artifacts_for_run(
                    args.run_id,
                    display_mode=orchestrator.registry.provenance_display_mode(),
                ),
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


def _load_registry(config) -> RegistryService:
    store = CouncilStore(config.state_dir / "council.db")
    registry = RegistryService(store)
    registry.sync_from_config(config)
    return registry


def _parse_setting_value(value: str):
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value
