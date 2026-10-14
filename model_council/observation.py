from __future__ import annotations

import json
import re
import subprocess
from hashlib import sha256
from pathlib import Path
from typing import Any

from .qualification import (
    ABSOLUTE_PATH_RE,
    CREDENTIAL_VALUE_RE,
    PERSONAL_PATH_RE,
)
from .supervisor import CANONICAL_LIFECYCLE_CHECKS
from .versions import version_from_output


OBSERVATION_KIND = "real_agent_qualification_observation"
OBSERVATION_VERSION = 1

# Whether the recorded facts were supplied by a caller or derived from a process
# this system ran. The two are not equally strong evidence, so they are never
# recorded under the same label: a caller-supplied record is a claim, and a
# probe-produced record is a receipt.
PROVENANCE_PROBE = "probe_run"
PROVENANCE_OPERATOR_AUTHORED = "operator_authored"
PROVENANCE_KINDS = (PROVENANCE_PROBE, PROVENANCE_OPERATOR_AUTHORED)

# How a fact was obtained. A value that a tool reports about itself is a weaker
# claim than one the service reports about the request it served, and the two
# must not be recorded under the same label.
SOURCE_TOOL_OUTPUT = "tool_output"
SOURCE_SERVICE_RESPONSE = "service_response"
SOURCE_LOCAL_PROCESS = "local_process"
SOURCE_OPERATOR_CONFIRMED = "operator_confirmed"
SOURCES = (
    SOURCE_TOOL_OUTPUT,
    SOURCE_SERVICE_RESPONSE,
    SOURCE_LOCAL_PROCESS,
    SOURCE_OPERATOR_CONFIRMED,
)
# Only these may appear in a record produced by a probe. An operator-authored
# record may still use the others, but a tool-produced record cannot claim a
# service response or an operator confirmation, because the probe saw neither.
PROBE_SOURCES = (SOURCE_TOOL_OUTPUT, SOURCE_LOCAL_PROCESS)

# Facts a version probe can actually establish. Everything else stays unknown:
# permission, protocol and connectivity need a real turn, and `actual_model` is
# not reported by a CLI host at all, which the 2026-10-14 observation showed.
PROBE_PROVIDES = ("process", "version")
PROBE_CANNOT_ESTABLISH = (
    "login",
    "actual_model",
    "permission",
    "protocol",
    "connectivity",
)

# A real turn can establish more, but still not the model identity: the Codex CLI
# stream carries no model field, and the relay endpoint rejects a direct request
# with a Cloudflare interstitial, so the serving model cannot be observed from
# either side on this machine. That limitation is data, not an omission.
TURN_PROVIDES = (
    "process",
    "version",
    "permission",
    "protocol",
    "connectivity",
)
TURN_CANNOT_ESTABLISH = ("actual_model",)

# The prompt is owned by this module rather than supplied by the caller. A
# reproducibility guarantee is worthless if the caller can choose what was sent,
# and a fixed synthetic prompt is what makes the record comparable across runs.
TURN_PROMPT = (
    "Return exactly the following ASCII token and nothing else: OBSERVE-20261014-OK"
)
TURN_EXPECTED_TOKEN = "OBSERVE-20261014-OK"

PROBE_TIMEOUT_SECONDS = 30
TURN_TIMEOUT_SECONDS = 180
PROBE_OUTPUT_LIMIT_BYTES = 65536
TURN_OUTPUT_LIMIT_BYTES = 262144

# Facts that can be observed without contacting anything.
OFFLINE_FACTS = (
    "process",
    "version",
    "permission",
    "protocol",
)
# Facts whose absence means "there is nothing to check here" rather than
# "something is missing". An API-key Agent has no interactive login state.
NOT_APPLICABLE_FACTS = ("login",)

STATUS_OBSERVED = "observed"
STATUS_UNKNOWN = "unknown"
STATUS_NOT_APPLICABLE = "not_applicable"
FACT_STATUSES = (STATUS_OBSERVED, STATUS_UNKNOWN, STATUS_NOT_APPLICABLE)

IDENTIFIER_RE = re.compile(r"^[a-z][a-z0-9._-]{0,63}$")
# Accepts the ISO-8601 forms that real tooling emits: with or without
# fractional seconds, and with either a 'Z' or a numeric UTC offset. The shape
# is checked here; the value is parsed later, and an unparseable value is
# reported rather than treated as fresh.
TIMESTAMP_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d{1,6})?)?"
    r"(?:Z|[+-]\d{2}:?\d{2})?$"
)


class ObservationError(ValueError):
    """Raised only when a submitted observation cannot be parsed at all."""


class ObservationService:
    """Turn one measurement into a reviewable qualification record.

    The service is pure: it reads no runtime state, starts nothing and stores
    nothing. Its job is to make a measurement checkable, which means recording
    two things a bare value cannot express — where the value came from, and when
    it was measured. A value without a measurement time is not evidence about
    the present, so an age limit is part of the record rather than an optional
    extra.

    A record built here is marked `operator_authored`, because the facts are
    supplied by the caller. That is not a defect of this method; it is its
    honest description. `ObservationProbeService` is what produces a record
    whose facts came from a process this system actually ran.
    """

    def build(
        self,
        submitted: dict[str, Any],
        *,
        max_age_seconds: int = 604800,
        now: str | None = None,
    ) -> dict[str, Any]:
        return self._build(
            submitted,
            max_age_seconds=max_age_seconds,
            provenance={
                "kind": PROVENANCE_OPERATOR_AUTHORED,
                "note": (
                    "facts were supplied by the caller and are not derived from "
                    "a process this system ran"
                ),
            },
        )

    def _build(
        self,
        submitted: dict[str, Any],
        *,
        max_age_seconds: int,
        provenance: dict[str, Any],
    ) -> dict[str, Any]:
        if not isinstance(submitted, dict):
            raise ObservationError("an observation must be an object")
        blockers: list[dict[str, str]] = []
        warnings: list[dict[str, str]] = []
        self._reject_sensitive_material(submitted, blockers)
        self._reject_unknown_fields(submitted, blockers)

        identity = self._identity(submitted, blockers)
        measured_at = self._measured_at(submitted, blockers)
        facts = self._facts(submitted, blockers)
        evidence = self._evidence(submitted, blockers)
        if not isinstance(max_age_seconds, int) or max_age_seconds < 1:
            self._block(blockers, "invalid_max_age", "max_age_seconds")

        if blockers:
            return {
                "status": "blocked",
                "blockers": blockers,
                "warnings": warnings,
                "record": None,
                "record_sha256": None,
                "expires_before": None,
                "summary": None,
            }

        summary = self._summarise(facts)
        record = {
            "kind": OBSERVATION_KIND,
            "version": OBSERVATION_VERSION,
            "identity": identity,
            "measured_at": measured_at,
            "max_age_seconds": max_age_seconds,
            "facts": facts,
            "evidence": evidence,
            "provenance": provenance,
        }
        record["fact_digest"] = self._digest(
            {
                "identity": identity,
                "measured_at": measured_at,
                "facts": facts,
                "provenance": provenance,
            }
        )
        return {
            "status": "recorded" if summary["observed"] else "incomplete",
            "blockers": [],
            "warnings": warnings,
            "record": record,
            "record_sha256": self._digest(record),
            "expires_before": measured_at,
            "summary": summary,
        }

    def verify(
        self,
        record: dict[str, Any],
        digest: str,
    ) -> bool:
        if not isinstance(record, dict) or not isinstance(digest, str):
            return False
        return self._digest(record) == digest

    def stale_reason(
        self,
        record: dict[str, Any],
        observed_now: str,
    ) -> str | None:
        """Report why a record no longer describes the present, if it does not.

        A record that never carried a measurement time cannot be aged at all,
        which is itself a reason to refuse it rather than to assume it is fresh.
        """
        measured = record.get("measured_at")
        if not isinstance(measured, str):
            return "measurement_time_missing"
        age = _age_seconds(measured, observed_now)
        if age is None:
            return "measurement_time_unreadable"
        limit = record.get("max_age_seconds")
        if not isinstance(limit, int) or limit < 1:
            return "age_limit_missing"
        if age > limit:
            return "measurement_expired"
        if age < 0:
            return "measurement_in_the_future"
        return None

    # ---------------------------------------------------------------- fields

    def _reject_unknown_fields(
        self,
        submitted: dict[str, Any],
        blockers: list[dict[str, str]],
    ) -> None:
        allowed = {
            "agent_id",
            "model_id",
            "provider_id",
            "measured_at",
            "facts",
            "evidence",
        }
        for key in submitted:
            if key not in allowed:
                self._block(blockers, "unsupported_observation_field", "observation")

    def _reject_sensitive_material(
        self,
        value: Any,
        blockers: list[dict[str, str]],
        path: str = "observation",
    ) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                key_text = str(key)
                normalized = key_text.lower().replace("-", "_")
                if self._is_sensitive_key(normalized):
                    self._block(blockers, "sensitive_field_forbidden", path)
                self._reject_sensitive_material(item, blockers, f"{path}.{key_text}")
            return
        if isinstance(value, list):
            for index, item in enumerate(value):
                self._reject_sensitive_material(item, blockers, f"{path}[{index}]")
            return
        if not isinstance(value, str):
            return
        if PERSONAL_PATH_RE.search(value):
            self._block(blockers, "personal_path_forbidden", path)
        elif ABSOLUTE_PATH_RE.search(value):
            self._block(blockers, "absolute_path_forbidden", path)
        if CREDENTIAL_VALUE_RE.search(value):
            self._block(blockers, "credential_value_forbidden", path)
        if "runtime-board14" in value.lower():
            self._block(blockers, "protected_runtime_reference_forbidden", path)

    def _identity(
        self,
        submitted: dict[str, Any],
        blockers: list[dict[str, str]],
    ) -> dict[str, str]:
        identity: dict[str, str] = {}
        for key in ("agent_id", "model_id", "provider_id"):
            value = submitted.get(key)
            if not isinstance(value, str) or not IDENTIFIER_RE.fullmatch(value):
                self._block(blockers, "invalid_identity_identifier", key)
            else:
                identity[key] = value
        return identity

    def _measured_at(
        self,
        submitted: dict[str, Any],
        blockers: list[dict[str, str]],
    ) -> str:
        value = submitted.get("measured_at")
        if not isinstance(value, str) or not TIMESTAMP_RE.fullmatch(value):
            self._block(
                blockers,
                "explicit_measurement_time_required",
                "measured_at",
            )
            return ""
        # A shape match is not validity: '2026-13-45T99:99:99Z' has the right
        # outline and is not a moment in time. The value is parsed here so an
        # impossible date is refused at submission rather than at ageing time.
        parsed = _parse_timestamp(value)
        if parsed is None:
            self._block(
                blockers,
                "measurement_time_not_a_real_moment",
                "measured_at",
            )
            return ""
        return value

    def _facts(
        self,
        submitted: dict[str, Any],
        blockers: list[dict[str, str]],
    ) -> dict[str, dict[str, Any]]:
        value = submitted.get("facts")
        if not isinstance(value, dict):
            self._block(blockers, "facts_required", "facts")
            return {}
        unknown = sorted(set(value) - set(CANONICAL_LIFECYCLE_CHECKS))
        if unknown:
            self._block(blockers, "unsupported_fact_name", "facts")
        facts: dict[str, dict[str, Any]] = {}
        for name in CANONICAL_LIFECYCLE_CHECKS:
            item = value.get(name)
            if item is None:
                facts[name] = {"status": STATUS_UNKNOWN, "source": None}
                continue
            if not isinstance(item, dict):
                self._block(blockers, "invalid_fact_entry", f"facts.{name}")
                continue
            status = item.get("status")
            if status not in FACT_STATUSES:
                self._block(blockers, "invalid_fact_status", f"facts.{name}")
                continue
            source = item.get("source")
            if status == STATUS_OBSERVED:
                if source not in SOURCES:
                    # An observed value must say how it was obtained; otherwise
                    # it is indistinguishable from an assertion.
                    self._block(
                        blockers,
                        "observation_source_required",
                        f"facts.{name}.source",
                    )
                if "value" not in item:
                    self._block(
                        blockers,
                        "observed_value_required",
                        f"facts.{name}.value",
                    )
            facts[name] = {
                "status": status,
                "source": source,
                "value": item.get("value"),
                "note": item.get("note"),
            }
        return facts

    def _evidence(
        self,
        submitted: dict[str, Any],
        blockers: list[dict[str, str]],
    ) -> dict[str, Any]:
        value = submitted.get("evidence")
        if value is None:
            return {"retained": False}
        if not isinstance(value, dict):
            self._block(blockers, "evidence_must_be_an_object", "evidence")
            return {}
        allowed = {
            "retained",
            "response_sha256",
            "response_bytes",
            "output_bytes",
            "prompt_tokens",
            "output_tokens",
            "prompt_token_sources",
            "thread_id",
            "exit_code",
        }
        for key in value:
            if key not in allowed:
                self._block(blockers, "unsupported_evidence_field", "evidence")
        result: dict[str, Any] = {}
        for key in allowed:
            if key in value:
                result[key] = value[key]
        result.setdefault("retained", False)
        return result

    @staticmethod
    def _summarise(facts: dict[str, dict[str, Any]]) -> dict[str, Any]:
        observed = [
            name
            for name, item in facts.items()
            if item.get("status") == STATUS_OBSERVED
        ]
        unknown = [
            name
            for name, item in facts.items()
            if item.get("status") == STATUS_UNKNOWN
        ]
        not_applicable = [
            name
            for name, item in facts.items()
            if item.get("status") == STATUS_NOT_APPLICABLE
        ]
        return {
            "observed": sorted(observed),
            "unknown": sorted(unknown),
            "not_applicable": sorted(not_applicable),
        }

    @staticmethod
    def _block(blockers: list[dict[str, str]], code: str, field: str) -> None:
        item = {"code": code, "field": field}
        if item not in blockers:
            blockers.append(item)

    @staticmethod
    def _is_sensitive_key(normalized: str) -> bool:
        if normalized in {
            "max_input_tokens",
            "max_output_tokens",
            "max_total_tokens",
            "prompt_tokens",
            "output_tokens",
            "prompt_token_sources",
            "token_source",
            "token_sources",
        }:
            # Token counts are measurements, not credentials. They are named
            # explicitly so the substring check below cannot mistake them for a
            # secret, which it otherwise does because the word contains "token".
            return False
        return any(
            part in normalized
            for part in (
                "api_key",
                "apikey",
                "authorization",
                "bearer",
                "password",
                "secret",
                "token",
            )
        )

    @staticmethod
    def _digest(value: dict[str, Any]) -> str:
        serialized = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return sha256(serialized.encode("utf-8")).hexdigest()


def run_turn_command(
    executable: str,
    executable_arguments: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Run one bounded, read-only real turn and capture its event stream.

    The argument list is built here, not by the caller. That matters for two
    reasons: the prompt cannot be swapped for something that carries project
    content, and the read-only, ephemeral, no-repository flags cannot be
    relaxed by whoever asks for the observation.

    The tool's response text is parsed for classification only. It is never
    stored: the record keeps hashes, byte counts and the one synthetic token the
    task asked for.
    """
    from .store import utc_now

    command = [
        executable,
        *executable_arguments,
        "exec",
        "--json",
        "--ephemeral",
        "--skip-git-repo-check",
        "--sandbox",
        "read-only",
        "--color",
        "never",
        # Close the optional subsystems that made unauthenticated catalog
        # requests during the first live pilot.
        "--disable",
        "plugins",
        "--disable",
        "remote_plugin",
        "--disable",
        "apps",
    ]
    command_digest = sha256(
        json.dumps(command, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    started_at = utc_now()
    try:
        completed = subprocess.run(
            command,
            input=TURN_PROMPT.encode("utf-8"),
            shell=False,
            capture_output=True,
            timeout=TURN_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError):
        return {
            "exit_code": None,
            "started_at": started_at,
            "finished_at": utc_now(),
            "events": [],
            "output_sha256": sha256(b"").hexdigest(),
            "command_digest": command_digest,
            "error": "turn_failed",
        }
    raw = (completed.stdout or b"")[:TURN_OUTPUT_LIMIT_BYTES]
    events: list[dict[str, Any]] = []
    for line in raw.decode("utf-8", "replace").splitlines():
        candidate = line.strip()
        if not candidate.startswith("{"):
            continue
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            events.append(parsed)
    return {
        "exit_code": completed.returncode,
        "started_at": started_at,
        "finished_at": utc_now(),
        "events": events,
        "output_sha256": sha256(raw).hexdigest(),
        "command_digest": command_digest,
        "stderr_bytes": len(completed.stderr or b""),
    }


def combine_probe_records(
    results: list[dict[str, Any]],
    *,
    max_age_seconds: int = 604800,
) -> dict[str, Any]:
    """Merge several probe records for one identity into a single record.

    A version query establishes two facts and a real turn establishes three, and
    neither covers the union. Merging them is legitimate because both are
    receipts from processes this system ran; it is not legitimate to merge a
    receipt with a caller-supplied claim, so every input must be probe-produced
    and every input is checked to carry the same identity.

    The provenance keeps each contributing record's own digests, so a merged
    record still says where every fact came from.
    """
    service = ObservationService()
    if not isinstance(results, list) or not results:
        raise ObservationError("combining requires at least one probe result")
    records: list[dict[str, Any]] = []
    for index, result in enumerate(results):
        if not isinstance(result, dict):
            raise ObservationError(f"merge input {index} is not an object")
        record = result.get("record")
        digest = result.get("record_sha256")
        if not isinstance(record, dict) or not isinstance(digest, str):
            raise ObservationError(f"merge input {index} is incomplete")
        if not service.verify(record, digest):
            raise ObservationError(f"merge input {index} has an invalid digest")
        provenance = record.get("provenance")
        if (
            not isinstance(provenance, dict)
            or provenance.get("kind") != PROVENANCE_PROBE
        ):
            raise ObservationError(
                f"merge input {index} is not probe-produced; only receipts may "
                "be merged"
            )
        records.append(record)

    identity = records[0].get("identity")
    if not isinstance(identity, dict):
        raise ObservationError("merge input has no identity")
    for index, record in enumerate(records[1:], start=1):
        if record.get("identity") != identity:
            raise ObservationError(
                f"merge input {index} has a different identity"
            )

    merged: dict[str, dict[str, Any]] = {
        name: {"status": STATUS_UNKNOWN, "source": None}
        for name in CANONICAL_LIFECYCLE_CHECKS
    }
    measured_at = ""

    def better(candidate: dict[str, Any], current: dict[str, Any]) -> bool:
        # A concrete observation wins over a placeholder; a second concrete
        # value does not silently overwrite the first, because two probes
        # disagreeing is a fact worth surfacing rather than resolving.
        if current.get("status") == STATUS_OBSERVED:
            return False
        if candidate.get("status") == STATUS_OBSERVED:
            return True
        if candidate.get("status") == STATUS_NOT_APPLICABLE:
            return current.get("status") == STATUS_UNKNOWN
        return False

    for record in records:
        facts = record.get("facts")
        if isinstance(facts, dict):
            for name, item in facts.items():
                if name not in merged or not isinstance(item, dict):
                    continue
                if better(item, merged[name]):
                    merged[name] = dict(item)
        candidate_time = record.get("measured_at")
        if isinstance(candidate_time, str) and candidate_time:
            # The combined record is only as fresh as its oldest input, because
            # a fact measured earlier cannot be made current by a later probe.
            if measured_at == "" or candidate_time < measured_at:
                measured_at = candidate_time

    digests = [
        {
            "kind": record.get("provenance", {}).get("mode", "version_probe"),
            "record_sha256": result["record_sha256"],
            "measured_at": record.get("measured_at"),
        }
        for record, result in zip(records, results)
    ]
    evidence: dict[str, Any] = {"retained": False}
    prompt_tokens = [
        record.get("evidence", {}).get("prompt_tokens")
        for record in records
        if isinstance(record.get("evidence"), dict)
    ]
    observed_prompt_tokens = [
        value for value in prompt_tokens if isinstance(value, int)
    ]
    if observed_prompt_tokens:
        evidence["prompt_tokens"] = max(observed_prompt_tokens)
        evidence["prompt_token_sources"] = len(observed_prompt_tokens)
    return service._build(
        {
            "agent_id": identity.get("agent_id"),
            "model_id": identity.get("model_id"),
            "provider_id": identity.get("provider_id"),
            "measured_at": measured_at,
            "facts": merged,
            "evidence": evidence,
        },
        max_age_seconds=max_age_seconds,
        provenance={
            "kind": PROVENANCE_PROBE,
            "mode": "combined_probes",
            "contributing_records": digests,
            "contributed": len(records),
        },
    )


class ObservationTurnService(ObservationService):
    """Produce a record from one real, read-only, synthetic turn.

    The probe service establishes two facts because a version query reveals two.
    A real turn reveals more, and this service derives them from the captured
    event stream: the process exit, the sandbox the tool actually reported, the
    protocol it actually spoke, and whether the synthetic token came back.

    It does not establish the model identity, because the stream does not carry
    one. Rather than filling that in from configuration, the fact is left
    unknown, which is the only honest answer available on this machine.
    """

    def turn(
        self,
        *,
        agent_id: str,
        model_id: str,
        provider_id: str,
        executable: str,
        executable_arguments: tuple[str, ...] = (),
        max_age_seconds: int = 604800,
        runner: Any = None,
        authentication_mode: str = "api_key",
    ) -> dict[str, Any]:
        if not isinstance(executable, str) or not executable.strip():
            raise ObservationError("a turn probe requires an executable path")
        run = runner or run_turn_command
        captured = run(executable, executable_arguments)
        if not isinstance(captured, dict):
            raise ObservationError("a turn runner must return an object")

        exit_code = captured.get("exit_code")
        started_at = captured.get("started_at")
        finished_at = captured.get("finished_at")
        output_sha256 = captured.get("output_sha256")
        command_digest = captured.get("command_digest")
        events = captured.get("events")
        if not isinstance(output_sha256, str) or not isinstance(
            command_digest, str
        ):
            raise ObservationError("a turn runner must report both digests")
        if not isinstance(started_at, str) or not isinstance(finished_at, str):
            raise ObservationError("a turn runner must report its own times")
        if not isinstance(events, list):
            events = []

        observed_kinds = set()
        token_returned = False
        token_mismatch = False
        usage: dict[str, Any] = {}
        sandbox = None
        protocol_events = 0
        for event in events:
            if not isinstance(event, dict):
                continue
            kind = event.get("type")
            if isinstance(kind, str):
                observed_kinds.add(kind)
            if kind in ("thread.started", "turn.started", "turn.completed"):
                protocol_events += 1
            if kind == "turn.completed":
                candidate = event.get("usage")
                if isinstance(candidate, dict):
                    usage = candidate
            payload = event.get("item")
            if isinstance(payload, dict) and payload.get("type") == "agent_message":
                text = payload.get("text")
                if isinstance(text, str):
                    if text.strip() == TURN_EXPECTED_TOKEN:
                        token_returned = True
                    else:
                        token_mismatch = True
            for source in (event, payload):
                if not isinstance(source, dict):
                    continue
                sandbox_value = source.get("sandbox")
                if isinstance(sandbox_value, str) and sandbox_value:
                    sandbox = sandbox_value
                if "sandbox" in source and isinstance(source["sandbox"], str):
                    sandbox = source["sandbox"]

        facts: dict[str, dict[str, Any]] = {
            name: {"status": STATUS_UNKNOWN, "source": None}
            for name in CANONICAL_LIFECYCLE_CHECKS
        }
        if isinstance(exit_code, int) and not isinstance(exit_code, bool):
            facts["process"] = {
                "status": STATUS_OBSERVED,
                "source": SOURCE_LOCAL_PROCESS,
                "value": f"exit_code={exit_code}",
            }
        if protocol_events:
            facts["protocol"] = {
                "status": STATUS_OBSERVED,
                "source": SOURCE_TOOL_OUTPUT,
                "value": f"jsonl_events={protocol_events}",
            }
        if token_returned and not token_mismatch:
            # The turn completed and answered the one synthetic question, so the
            # path from prompt to response was exercised. This is connectivity
            # evidence, not model-identity evidence.
            facts["connectivity"] = {
                "status": STATUS_OBSERVED,
                "source": SOURCE_SERVICE_RESPONSE,
                "value": "synthetic_token_returned",
            }
        if isinstance(sandbox, str):
            facts["permission"] = {
                "status": STATUS_OBSERVED,
                "source": SOURCE_TOOL_OUTPUT,
                "value": sandbox,
            }
        else:
            # The run was requested read-only and the tool did not echo the
            # sandbox. Recording the requested value as observed would be a
            # claim about the tool, so it stays unknown.
            facts["permission"] = {"status": STATUS_UNKNOWN, "source": None}
        if authentication_mode == "api_key":
            facts["login"] = {"status": STATUS_NOT_APPLICABLE, "source": None}
        if not token_returned:
            # A turn that produced no matching answer did not exercise the path,
            # so connectivity is not established even if the process exited.
            facts["connectivity"] = {"status": STATUS_UNKNOWN, "source": None}
        # `actual_model` is deliberately left unknown: the event stream carries
        # no model field, and a configured model is not evidence about which one
        # served the request.
        facts["actual_model"] = {"status": STATUS_UNKNOWN, "source": None}

        prompt_tokens = usage.get("input_tokens") if isinstance(usage, dict) else None
        output_tokens = usage.get("output_tokens") if isinstance(usage, dict) else None
        evidence = {
            "retained": False,
            "exit_code": exit_code if isinstance(exit_code, int) else None,
            "prompt_tokens": (
                prompt_tokens if isinstance(prompt_tokens, int) else None
            ),
            "output_tokens": (
                output_tokens if isinstance(output_tokens, int) else None
            ),
        }
        provenance = {
            "kind": PROVENANCE_PROBE,
            "mode": "real_turn",
            "command_digest": command_digest,
            "output_sha256": output_sha256,
            "started_at": started_at,
            "finished_at": finished_at,
            "prompt_sha256": sha256(
                TURN_PROMPT.encode("utf-8")
            ).hexdigest(),
            "prompt_bytes": len(TURN_PROMPT.encode("utf-8")),
            "event_count": len(events),
            "event_types": sorted(observed_kinds),
            "argument_count": len(executable_arguments),
        }
        return self._build(
            {
                "agent_id": agent_id,
                "model_id": model_id,
                "provider_id": provider_id,
                "measured_at": finished_at,
                "facts": facts,
                "evidence": evidence,
            },
            max_age_seconds=max_age_seconds,
            provenance=provenance,
        )


class ObservationProbeService(ObservationService):
    """Produce a record by running one bounded probe and reading its output.

    The difference from the plain builder is where the facts come from. Here the
    caller supplies the identity and the command to run, and nothing else: the
    fact values are derived from the captured output by this class, and the
    record carries the command digest and the output hash. A caller therefore
    cannot assert that a fact was observed; it can only run something and accept
    what came back.

    This does not make forgery impossible, and claiming otherwise would be
    dishonest. A local operator owns the process, the disk and the tool, so a
    determined operator can always fake evidence. What changes is the trust
    boundary: the record no longer rests on free-form caller JSON, and any
    inconsistency in the captured provenance is reportable.
    """

    def probe(
        self,
        *,
        agent_id: str,
        model_id: str,
        provider_id: str,
        executable: str,
        version_arguments: tuple[str, ...] = ("--version",),
        max_age_seconds: int = 604800,
        runner: Any = None,
    ) -> dict[str, Any]:
        if not isinstance(executable, str) or not executable.strip():
            raise ObservationError("a probe requires an executable path")
        if not isinstance(version_arguments, tuple) or any(
            not isinstance(item, str) for item in version_arguments
        ):
            raise ObservationError("version_arguments must be a tuple of strings")
        run = runner or run_probe_command
        captured = run(executable, version_arguments)
        if not isinstance(captured, dict):
            raise ObservationError("a probe runner must return an object")

        exit_code = captured.get("exit_code")
        started_at = captured.get("started_at")
        finished_at = captured.get("finished_at")
        output_sha256 = captured.get("output_sha256")
        command_digest = captured.get("command_digest")
        if not isinstance(output_sha256, str) or not isinstance(
            command_digest, str
        ):
            raise ObservationError("a probe runner must report both digests")
        if not isinstance(started_at, str) or not isinstance(finished_at, str):
            raise ObservationError("a probe runner must report its own times")

        output_text = captured.get("output_text") or ""
        reported_version = (
            version_from_output(output_text)
            if isinstance(output_text, str)
            else None
        )
        facts: dict[str, dict[str, Any]] = {}
        for name in CANONICAL_LIFECYCLE_CHECKS:
            facts[name] = {"status": STATUS_UNKNOWN, "source": None}
        if isinstance(exit_code, int) and not isinstance(exit_code, bool):
            facts["process"] = {
                "status": STATUS_OBSERVED,
                "source": SOURCE_LOCAL_PROCESS,
                "value": f"exit_code={exit_code}",
            }
        if reported_version is not None:
            facts["version"] = {
                "status": STATUS_OBSERVED,
                "source": SOURCE_TOOL_OUTPUT,
                "value": reported_version,
            }
        # Everything a version probe cannot establish stays unknown rather than
        # being filled in from configuration. `actual_model` is the important
        # one: a CLI host does not report it, and the fact that a probe ran is
        # not evidence about which model would serve a request.
        for name in PROBE_CANNOT_ESTABLISH:
            facts.setdefault(name, {"status": STATUS_UNKNOWN, "source": None})

        evidence = {
            "retained": False,
            "exit_code": exit_code if isinstance(exit_code, int) else None,
            "output_bytes": (
                len(output_text.encode("utf-8"))
                if isinstance(output_text, str)
                else None
            ),
        }
        provenance = {
            "kind": PROVENANCE_PROBE,
            "command_digest": command_digest,
            "output_sha256": output_sha256,
            "started_at": started_at,
            "finished_at": finished_at,
            # Deliberately not the executable path: the probe knows it, the
            # record does not need to carry a machine path.
            "argument_count": len(version_arguments),
        }
        return self._build(
            {
                "agent_id": agent_id,
                "model_id": model_id,
                "provider_id": provider_id,
                # The measurement time is the probe's own finish time, not a
                # value the caller chose.
                "measured_at": finished_at,
                "facts": facts,
                "evidence": evidence,
            },
            max_age_seconds=max_age_seconds,
            provenance=provenance,
        )


def run_probe_command(
    executable: str,
    version_arguments: tuple[str, ...],
) -> dict[str, Any]:
    """Run one argument-array, shell-free, time-limited probe.

    The probe sends no project context; it asks the tool to identify itself. Its
    own start and finish times are captured here so the measurement time in the
    record cannot be chosen by the caller, and the output is hashed before it is
    parsed.
    """
    from .store import utc_now

    command = [executable, *version_arguments]
    command_digest = sha256(
        json.dumps(command, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    started_at = utc_now()
    try:
        completed = subprocess.run(
            command,
            shell=False,
            capture_output=True,
            timeout=PROBE_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError):
        return {
            "exit_code": None,
            "started_at": started_at,
            "finished_at": utc_now(),
            "output_text": "",
            "output_sha256": sha256(b"").hexdigest(),
            "command_digest": command_digest,
            "error": "probe_failed",
        }
    raw = (completed.stdout or b"") + b"\n" + (completed.stderr or b"")
    raw = raw[:PROBE_OUTPUT_LIMIT_BYTES]
    return {
        "exit_code": completed.returncode,
        "started_at": started_at,
        "finished_at": utc_now(),
        "output_text": raw.decode("utf-8", "replace"),
        "output_sha256": sha256(raw).hexdigest(),
        "command_digest": command_digest,
    }


def _parse_timestamp(text: str):
    """Parse one ISO-8601 timestamp, returning None when it is not a real one."""
    from datetime import datetime

    candidate = text.strip()
    if candidate.endswith(("Z", "z")):
        candidate = candidate[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(candidate)
    except ValueError:
        return None


def _age_seconds(measured_at: str, observed_now: str) -> int | None:
    """Return the age in whole seconds, or None if either value is unreadable."""
    from .store import utc_now  # local import avoids a cycle at module load

    start = _parse_timestamp(measured_at)
    end = _parse_timestamp(observed_now) if observed_now else _parse_timestamp(
        utc_now()
    )
    if start is None or end is None:
        return None
    if start.tzinfo is None and end.tzinfo is not None:
        start = start.replace(tzinfo=end.tzinfo)
    if end.tzinfo is None and start.tzinfo is not None:
        end = end.replace(tzinfo=start.tzinfo)
    return int((end - start).total_seconds())
