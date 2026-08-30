from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .adapters import build_adapters
from .config import load_config
from .discovery import DiscoveryService
from .interoperability import InteroperabilityService, MCPToolBroker
from .outbound_context import OutboundContextService, validate_controlled_pilot
from .ledger import UsageLedger
from .orchestrator import Orchestrator
from .registry import RegistryService
from .routing import RoutingService
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
    run.add_argument(
        "--outbound-manifest",
        help=(
            "consume one approved Board 8 context manifest for its exact "
            "synthetic Codex architect prompt"
        ),
    )

    agents = subparsers.add_parser("agents", help="list configured agents")
    agents.add_argument("--config", default=str(default_config_path()))

    doctor = subparsers.add_parser(
        "doctor",
        help="validate configured adapters without invoking any model",
    )
    doctor.add_argument("--config", default=str(default_config_path()))

    discovery = subparsers.add_parser(
        "discovery",
        help="scan, inspect or configure local Agent hosts",
    )
    discovery_commands = discovery.add_subparsers(
        dest="discovery_command",
        required=True,
    )
    discovery_scan = discovery_commands.add_parser(
        "scan",
        help="scan configured Agents and known local commands without a model call",
    )
    discovery_scan.add_argument("--config", default=str(default_config_path()))
    discovery_show = discovery_commands.add_parser(
        "show",
        help="show persisted discovery and setup status",
    )
    discovery_show.add_argument("--config", default=str(default_config_path()))
    discovery_models = discovery_commands.add_parser(
        "models",
        help="explicitly ask one configured Adapter to discover available models",
    )
    discovery_models.add_argument("agent")
    discovery_models.add_argument("--config", default=str(default_config_path()))
    discovery_probe = discovery_commands.add_parser(
        "probe",
        help=(
            "opt in to a non-project connectivity test for one configured Agent"
        ),
    )
    discovery_probe.add_argument("agent")
    discovery_probe.add_argument("--config", default=str(default_config_path()))
    discovery_register = discovery_commands.add_parser(
        "register-gui",
        help="manually register a GUI-only Agent host",
    )
    discovery_register.add_argument("agent_id")
    discovery_register.add_argument("--name", required=True)
    discovery_register.add_argument("--provider")
    discovery_register.add_argument("--model")
    discovery_register.add_argument(
        "--capability",
        action="append",
        default=[],
    )
    discovery_register.add_argument(
        "--boundary",
        action="append",
        default=[],
    )
    discovery_register.add_argument(
        "--config",
        default=str(default_config_path()),
    )

    ledger = subparsers.add_parser(
        "ledger",
        help="inspect usage, cost, budgets and supported provider balances",
    )
    ledger_commands = ledger.add_subparsers(
        dest="ledger_command",
        required=True,
    )
    ledger_summary = ledger_commands.add_parser(
        "summary",
        help="show project, run and role usage totals",
    )
    ledger_summary.add_argument("--project")
    ledger_summary.add_argument("--run")
    ledger_summary.add_argument("--role")
    ledger_summary.add_argument("--config", default=str(default_config_path()))
    ledger_events = ledger_commands.add_parser(
        "events",
        help="show normalized per-call usage records",
    )
    ledger_events.add_argument("--run")
    ledger_events.add_argument("--limit", type=int, default=100)
    ledger_events.add_argument("--config", default=str(default_config_path()))
    ledger_budgets = ledger_commands.add_parser(
        "budgets",
        help="show persisted budget policies",
    )
    ledger_budgets.add_argument("--config", default=str(default_config_path()))
    ledger_set_budget = ledger_commands.add_parser(
        "set-budget",
        help="persist a user-owned warning or hard budget",
    )
    ledger_set_budget.add_argument("policy_id")
    ledger_set_budget.add_argument(
        "--scope",
        required=True,
        choices=("project", "run", "role"),
    )
    ledger_set_budget.add_argument("--scope-key")
    ledger_set_budget.add_argument(
        "--metric",
        required=True,
        choices=("tokens", "cost"),
    )
    ledger_set_budget.add_argument("--warning")
    ledger_set_budget.add_argument("--hard")
    ledger_set_budget.add_argument("--currency")
    ledger_set_budget.add_argument(
        "--config",
        default=str(default_config_path()),
    )
    ledger_alerts = ledger_commands.add_parser(
        "alerts",
        help="show budget warnings and hard-limit observations",
    )
    ledger_alerts.add_argument("--run")
    ledger_alerts.add_argument("--config", default=str(default_config_path()))
    ledger_balance = ledger_commands.add_parser(
        "balance",
        help="explicitly query a Provider balance when an Adapter supports it",
    )
    ledger_balance.add_argument("provider")
    ledger_balance.add_argument("--config", default=str(default_config_path()))
    ledger_balances = ledger_commands.add_parser(
        "balance-history",
        help="show persisted Provider balance snapshots",
    )
    ledger_balances.add_argument("--provider")
    ledger_balances.add_argument(
        "--config",
        default=str(default_config_path()),
    )

    routing = subparsers.add_parser(
        "routing",
        help="inspect persisted deterministic routing decisions",
    )
    routing_commands = routing.add_subparsers(
        dest="routing_command",
        required=True,
    )
    routing_decisions = routing_commands.add_parser(
        "decisions",
        help="show selected identities and rejected routing candidates",
    )
    routing_decisions.add_argument("--run")
    routing_decisions.add_argument(
        "--config",
        default=str(default_config_path()),
    )

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
    settings_assign.add_argument(
        "--constraints",
        default="{}",
        help="routing constraints as a JSON object",
    )
    settings_assign.add_argument("--config", default=str(default_config_path()))
    settings_set = settings_commands.add_parser(
        "set",
        help="persist one application setting as JSON or text",
    )
    settings_set.add_argument("key")
    settings_set.add_argument("value")
    settings_set.add_argument("--config", default=str(default_config_path()))

    web = subparsers.add_parser(
        "web",
        help="start the local-only settings interface without invoking models",
    )
    web.add_argument("--config", default=str(default_config_path()))
    web.add_argument("--host", default="127.0.0.1")
    web.add_argument("--port", type=int, default=8765)

    interop = subparsers.add_parser(
        "interop",
        help="inspect and operate persistent App Server, A2A and MCP contracts",
    )
    interop_commands = interop.add_subparsers(
        dest="interop_command",
        required=True,
    )
    interop_show = interop_commands.add_parser(
        "show",
        help="show configured interoperability endpoints and local evidence",
    )
    interop_show.add_argument("--config", default=str(default_config_path()))
    interop_sessions = interop_commands.add_parser(
        "sessions",
        help="show persistent interoperability sessions",
    )
    interop_sessions.add_argument("--endpoint")
    interop_sessions.add_argument("--agent")
    interop_sessions.add_argument("--config", default=str(default_config_path()))
    interop_events = interop_commands.add_parser(
        "events",
        help="show persisted protocol events",
    )
    interop_events.add_argument("--session")
    interop_events.add_argument("--limit", type=int, default=200)
    interop_events.add_argument("--config", default=str(default_config_path()))
    interop_approvals = interop_commands.add_parser(
        "approvals",
        help="show pending and decided interoperability approvals",
    )
    interop_approvals.add_argument(
        "--status",
        choices=("pending", "approved", "rejected"),
    )
    interop_approvals.add_argument("--config", default=str(default_config_path()))
    interop_approve = interop_commands.add_parser(
        "approve",
        help="approve one pending interoperability action",
    )
    interop_approve.add_argument("approval_id")
    interop_approve.add_argument("--config", default=str(default_config_path()))
    interop_reject = interop_commands.add_parser(
        "reject",
        help="reject one pending interoperability action",
    )
    interop_reject.add_argument("approval_id")
    interop_reject.add_argument("--config", default=str(default_config_path()))
    interop_request_tool = interop_commands.add_parser(
        "request-tool",
        help="create a pending, single-use MCP tool approval",
    )
    interop_request_tool.add_argument("server")
    interop_request_tool.add_argument("tool")
    interop_request_tool.add_argument("--arguments", default="{}")
    interop_request_tool.add_argument(
        "--config",
        default=str(default_config_path()),
    )
    interop_call_tool = interop_commands.add_parser(
        "call-tool",
        help="consume an approved MCP tool request and execute it once",
    )
    interop_call_tool.add_argument("approval_id")
    interop_call_tool.add_argument("--config", default=str(default_config_path()))
    interop_tools = interop_commands.add_parser(
        "tools",
        help="explicitly list tools from one enabled MCP server",
    )
    interop_tools.add_argument("server")
    interop_tools.add_argument("--config", default=str(default_config_path()))
    interop_contexts = interop_commands.add_parser(
        "contexts",
        help="inspect and decide exact outbound Codex App Server context",
    )
    interop_contexts.add_argument(
        "--status",
        choices=("pending", "approved", "rejected", "consumed", "blocked"),
    )
    interop_contexts.add_argument("--config", default=str(default_config_path()))
    interop_context = interop_commands.add_parser(
        "context",
        help="show or decide one locally stored outbound context manifest",
    )
    interop_context.add_argument("manifest_id")
    interop_context.add_argument(
        "--show-prompt",
        action="store_true",
        help="print the exact local prompt that would leave this machine",
    )
    interop_context.add_argument(
        "--approve-sha256",
        help="approve once only when this exactly matches the displayed digest",
    )
    interop_context.add_argument("--reject", action="store_true")
    interop_context.add_argument("--config", default=str(default_config_path()))

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
            manifest_by_agent = {}
            if args.outbound_manifest:
                service = OutboundContextService(
                    CouncilStore(config.state_dir / "council.db")
                )
                manifest = service.manifest(args.outbound_manifest)
                agent_id = validate_controlled_pilot(config, manifest)
                manifest_by_agent[agent_id] = manifest["id"]
            _run_goal(config, args.goal, manifest_by_agent)
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
        elif args.command == "discovery":
            config = load_config(args.config)
            discovery = _load_discovery(config)
            if args.discovery_command == "scan":
                payload = discovery.scan()
            elif args.discovery_command == "show":
                payload = discovery.registry.discovery_records()
            elif args.discovery_command == "models":
                payload = {
                    "agent_id": args.agent,
                    "models": discovery.discover_models(args.agent),
                }
            elif args.discovery_command == "probe":
                payload = discovery.probe(args.agent)
            elif args.discovery_command == "register-gui":
                payload = discovery.register_gui(
                    agent_id=args.agent_id,
                    display_name=args.name,
                    provider_id=args.provider,
                    model_id=args.model,
                    capabilities=args.capability,
                    boundaries=args.boundary,
                )
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            if (
                args.discovery_command == "probe"
                and payload["status"] != "passed"
            ):
                raise SystemExit(2)
        elif args.command == "ledger":
            config = load_config(args.config)
            ledger = _load_ledger(config)
            if args.ledger_command == "summary":
                project_name = args.project
                if project_name is None and args.run is None:
                    project_name = config.project_name
                payload = ledger.summary(
                    project_name=project_name,
                    run_id=args.run,
                    role=args.role,
                )
            elif args.ledger_command == "events":
                payload = ledger.events(
                    run_id=args.run,
                    limit=args.limit,
                )
            elif args.ledger_command == "budgets":
                payload = ledger.budget_policies()
            elif args.ledger_command == "set-budget":
                scope_key = args.scope_key
                if scope_key is None and args.scope == "project":
                    scope_key = config.project_name
                if scope_key is None:
                    raise ValueError(
                        "--scope-key is required for run and role budgets"
                    )
                ledger.set_budget_policy(
                    policy_id=args.policy_id,
                    scope=args.scope,
                    scope_key=scope_key,
                    metric=args.metric,
                    warning=args.warning,
                    hard=args.hard,
                    currency=args.currency,
                )
                payload = ledger.budget_policies()
            elif args.ledger_command == "alerts":
                payload = ledger.alerts(args.run)
            elif args.ledger_command == "balance":
                payload = ledger.provider_balance(
                    args.provider,
                    build_adapters(config),
                )
            elif args.ledger_command == "balance-history":
                payload = ledger.balance_snapshots(args.provider)
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        elif args.command == "routing":
            config = load_config(args.config)
            routing = _load_routing(config)
            if args.routing_command == "decisions":
                payload = routing.decisions(args.run)
            print(json.dumps(payload, ensure_ascii=False, indent=2))
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
                    constraints=_parse_constraints(args.constraints),
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
        elif args.command == "web":
            config = load_config(args.config)
            from .web import serve

            serve(config, host=args.host, port=args.port)
        elif args.command == "interop":
            config = load_config(args.config)
            interoperability = _load_interoperability(config)
            if args.interop_command == "show":
                payload = interoperability.snapshot()
            elif args.interop_command == "sessions":
                payload = interoperability.sessions(
                    endpoint_id=args.endpoint,
                    agent_id=args.agent,
                )
            elif args.interop_command == "events":
                payload = interoperability.events(
                    args.session,
                    limit=args.limit,
                )
            elif args.interop_command == "approvals":
                payload = interoperability.approvals(args.status)
            elif args.interop_command in {"approve", "reject"}:
                interoperability.decide_approval(
                    args.approval_id,
                    approve=args.interop_command == "approve",
                )
                payload = interoperability.approval(args.approval_id)
            elif args.interop_command == "contexts":
                payload = OutboundContextService(interoperability.store).manifests(
                    status=args.status
                )
            elif args.interop_command == "context":
                contexts = OutboundContextService(interoperability.store)
                if args.approve_sha256 and args.reject:
                    raise ValueError(
                        "--approve-sha256 and --reject cannot be used together"
                    )
                if args.approve_sha256:
                    contexts.decide(
                        args.manifest_id,
                        approve=True,
                        confirmation=args.approve_sha256,
                    )
                elif args.reject:
                    contexts.decide(
                        args.manifest_id,
                        approve=False,
                        confirmation="",
                    )
                payload = contexts.manifest(
                    args.manifest_id,
                    include_prompt=args.show_prompt,
                )
            else:
                broker = MCPToolBroker(
                    interoperability,
                    config_dir=Path(config.path).parent,
                )
                if args.interop_command == "request-tool":
                    payload = broker.request_tool_call(
                        args.server,
                        args.tool,
                        _parse_json_object(
                            args.arguments,
                            "--arguments",
                        ),
                    )
                elif args.interop_command == "call-tool":
                    payload = broker.call_approved_tool(args.approval_id)
                elif args.interop_command == "tools":
                    payload = broker.list_tools(args.server)
            print(json.dumps(payload, ensure_ascii=False, indent=2))
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
                "ledger": orchestrator.ledger.summary(run_id=args.run_id),
                "budget_alerts": orchestrator.ledger.alerts(args.run_id),
                "routing": orchestrator.router.decisions(args.run_id),
            }
            print(json.dumps(payload, ensure_ascii=False, indent=2))
    except KeyboardInterrupt:
        raise
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


def _run_goal(
    config,
    goal: str,
    outbound_manifest_by_agent: dict[str, str] | None = None,
) -> None:
    orchestrator = Orchestrator(
        config,
        outbound_manifest_by_agent=outbound_manifest_by_agent,
    )
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


def _load_discovery(config) -> DiscoveryService:
    registry = _load_registry(config)
    return DiscoveryService(
        config=config,
        registry=registry,
        adapters=build_adapters(config, registry.store),
    )


def _load_ledger(config) -> UsageLedger:
    registry = _load_registry(config)
    return UsageLedger(
        config=config,
        store=registry.store,
        registry=registry,
    )


def _load_routing(config) -> RoutingService:
    registry = _load_registry(config)
    return RoutingService(
        config=config,
        store=registry.store,
        registry=registry,
        adapters=build_adapters(config, registry.store),
    )


def _load_interoperability(config) -> InteroperabilityService:
    store = CouncilStore(config.state_dir / "council.db")
    return InteroperabilityService(config, store)


def _parse_setting_value(value: str):
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def _parse_constraints(value: str) -> dict:
    return _parse_json_object(value, "--constraints")


def _parse_json_object(value: str, label: str) -> dict:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label} must be valid JSON") from exc
    if not isinstance(parsed, dict):
        raise ValueError(f"{label} must be a JSON object")
    return parsed
