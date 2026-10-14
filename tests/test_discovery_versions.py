from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from model_council.discovery import (
    KNOWN_LOCAL_AGENTS,
    LocalAgentTarget,
    DiscoveryService,
    gui_targets_from_config,
    target_from_config,
    targets_from_config,
)
from model_council.registry import RegistryService
from model_council.store import CouncilStore
from model_council.versions import version_from_output


class VersionFromOutputTests(unittest.TestCase):
    """Real output shapes observed on this machine, not invented ones."""

    def test_codex_style_prefixed_output(self):
        self.assertEqual(version_from_output("codex-cli 0.154.0"), "0.154.0")

    def test_reasonix_style_v_prefixed_output(self):
        self.assertEqual(version_from_output("reasonix v1.35.0"), "1.35.0")

    def test_npm_style_prefixed_output(self):
        self.assertEqual(
            version_from_output("reasonix npm-v1.7.0-rc.1"),
            "1.7.0-rc.1",
        )

    def test_traework_style_multiline_output_picks_the_version_line(self):
        output = "1.107.1\n667d4fc5e62308ade25d24a60929a78863d65e00\nx64\n"
        self.assertEqual(version_from_output(output), "1.107.1")

    def test_takes_the_first_version_line_not_a_later_one(self):
        output = "tool 2.0.0\nhelper 9.9.9\n"
        self.assertEqual(version_from_output(output), "2.0.0")

    def test_four_segment_version_is_detected(self):
        self.assertEqual(version_from_output("ZCode 3.14.5.7961"), "3.14.5.7961")

    def test_output_without_a_version_is_none(self):
        for value in ("", "   ", None, 12, "no version here", "usage: tool"):
            with self.subTest(value=value):
                self.assertIsNone(version_from_output(value))

    def test_extensions_and_hashes_are_not_mistaken_for_versions(self):
        self.assertIsNone(
            version_from_output("C:\\tools\\agent.exe --help")
        )
        self.assertIsNone(
            version_from_output("667d4fc5e62308ade25d24a60929a78863d65e00")
        )


class TargetFromConfigTests(unittest.TestCase):
    def test_minimal_entry_uses_defaults(self):
        target = target_from_config(
            {"key": "myagent", "command_candidates": ["myagent"]},
            "discovery_targets[0]",
        )
        self.assertEqual(target.key, "myagent")
        self.assertEqual(target.display_name, "myagent")
        self.assertEqual(target.version_arguments, ("--version",))
        self.assertEqual(target.extra_path_patterns, ())

    def test_full_entry_is_read(self):
        target = target_from_config(
            {
                "key": "zcode",
                "display_name": "ZCode",
                "command_candidates": ["ZCode.exe"],
                "version_arguments": ["--version"],
                "extra_path_patterns": ["C:/Programs/ZCode/*.exe"],
            },
            "discovery_targets[0]",
        )
        self.assertEqual(target.display_name, "ZCode")
        self.assertEqual(target.command_candidates, ("ZCode.exe",))
        self.assertEqual(
            target.extra_path_patterns,
            ("C:/Programs/ZCode/*.exe",),
        )

    def test_invalid_entries_are_rejected(self):
        for item in (
            {},
            {"key": "", "command_candidates": ["x"]},
            {"key": "a"},
            {"key": "a", "command_candidates": []},
            {"key": "a", "command_candidates": [""]},
            {"key": "a", "command_candidates": ["x"], "version_arguments": "v"},
            {
                "key": "a",
                "command_candidates": ["x"],
                "extra_path_patterns": [""],
            },
        ):
            with self.subTest(item=item):
                with self.assertRaises(ValueError):
                    target_from_config(item, "discovery_targets[0]")

    def test_a_catalogue_replaces_the_builtin_default(self):
        catalogue = targets_from_config(
            [{"key": "only", "command_candidates": ["only"]}]
        )
        self.assertEqual(len(catalogue), 1)
        self.assertEqual(catalogue[0].key, "only")
        # An absent catalogue falls back to the built-in starting catalogue.
        self.assertIs(targets_from_config(None), KNOWN_LOCAL_AGENTS)

    def test_empty_catalogue_is_rejected(self):
        with self.assertRaises(ValueError):
            targets_from_config([])


class VersionCandidateTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = CouncilStore(Path(self.temp.name) / "council.db")
        self.registry = RegistryService(self.store)
        self.probed: list[str] = []

    def _service(self, versions: dict[str, str | None], target):
        def probe(executable, bound_target):
            self.probed.append(executable)
            return versions.get(executable)

        return DiscoveryService(
            None,
            self.registry,
            adapters={},
            known_targets=(target,),
            version_probe=probe,
        )

    def _target(self, commands=("codex-a.cmd", "codex-b.cmd")):
        return LocalAgentTarget("codex", "Codex CLI", commands)

    def test_two_installs_are_ranked_and_the_higher_one_is_recommended(self):
        target = self._target()
        service = self._service({}, target)
        # Patch resolution so the test does not depend on this machine's PATH.
        resolved = ["/fake/a/codex.cmd", "/fake/b/codex.cmd"]
        service._resolve_command = lambda candidates: resolved.pop(0)
        service.version_probe = lambda executable, bound: {
            "/fake/a/codex.cmd": "0.150.1",
            "/fake/b/codex.cmd": "0.154.0",
        }[executable]

        ranking = service.version_candidates(target)

        self.assertEqual(len(ranking["candidates"]), 2)
        self.assertEqual(ranking["versions_detected"], ["0.150.1", "0.154.0"])
        self.assertEqual(
            ranking["plan"]["recommended_version"],
            "0.154.0",
        )
        self.assertFalse(ranking["auto_switch"])
        self.assertFalse(ranking["plan"]["auto_switch"])

    def test_stable_release_wins_over_a_higher_prerelease(self):
        target = self._target()
        service = self._service({}, target)
        resolved = ["/fake/a/reasonix.cmd", "/fake/b/reasonix.cmd"]
        service._resolve_command = lambda candidates: resolved.pop(0)
        service.version_probe = lambda executable, bound: {
            "/fake/a/reasonix.cmd": "1.35.0",
            "/fake/b/reasonix.cmd": "1.36.0-rc.1",
        }[executable]

        ranking = service.version_candidates(target)

        self.assertEqual(ranking["plan"]["recommended_version"], "1.35.0")
        self.assertEqual(
            ranking["plan"]["reason"],
            "stable_release_preferred_over_prerelease",
        )

    def test_an_explicit_preference_overrides_the_recommendation(self):
        target = self._target()
        service = self._service({}, target)
        resolved = ["/fake/a/reasonix.cmd", "/fake/b/reasonix.cmd"]
        service._resolve_command = lambda candidates: resolved.pop(0)
        service.version_probe = lambda executable, bound: {
            "/fake/a/reasonix.cmd": "1.35.0",
            "/fake/b/reasonix.cmd": "1.7.0-rc.1",
        }[executable]

        ranking = service.version_candidates(
            target,
            existing={"details": {"preferred_version": "1.7.0-rc.1"}},
        )

        self.assertEqual(
            ranking["plan"]["recommendation"],
            "user_preference",
        )
        self.assertEqual(
            ranking["plan"]["recommended_version"],
            "1.7.0-rc.1",
        )

    def test_an_unreadable_version_is_reported_not_assumed(self):
        target = self._target()
        service = self._service({}, target)
        service._resolve_command = lambda candidates: "/fake/a/codex.cmd"
        service.version_probe = lambda executable, bound: None

        ranking = service.version_candidates(target)

        # The install is still reported; only its version is unknown, and it is
        # listed as undetected rather than silently dropped or guessed.
        self.assertEqual(ranking["versions_detected"], [])
        self.assertEqual(ranking["undetected"], ["/fake/a/codex.cmd"])
        self.assertEqual(len(ranking["candidates"]), 1)
        plan = ranking["plan"]
        if plan["recommendation"] == "recommended":
            self.assertIsNone(plan["recommended_version"])
        else:
            self.assertIsNone(plan["recommended_version"])
        self.assertFalse(plan["auto_switch"])

    def test_a_command_that_does_not_resolve_is_not_probed(self):
        target = self._target()
        service = self._service({}, target)
        calls: list[str] = []

        def probe(executable, bound):
            calls.append(executable)
            return "1.0.0"

        service._resolve_command = lambda candidates: None
        service.version_probe = probe

        ranking = service.version_candidates(target)

        self.assertEqual(calls, [])
        self.assertEqual(ranking["candidates"], [])

    def test_scan_records_the_version_plan_without_switching_anything(self):
        target = self._target(commands=("codex-a.cmd", "codex-b.cmd"))
        service = self._service({}, target)
        remaining = ["/fake/a/codex.cmd", "/fake/b/codex.cmd"]

        def fake_resolve(candidates):
            # Mirrors the real resolver: one command candidate per call.
            return remaining.pop(0) if remaining else None

        service._resolve_command = fake_resolve
        service.version_probe = lambda executable, bound: {
            "/fake/a/codex.cmd": "0.150.1",
            "/fake/b/codex.cmd": "0.154.0",
        }[executable]

        service.scan()

        record = self.registry.discovery_record("known:codex")
        self.assertIsNotNone(record)
        plan = record["details"]["version_plan"]
        self.assertEqual(plan["recommended_version"], "0.154.0")
        self.assertFalse(plan["auto_switch"])
        self.assertEqual(
            record["details"]["versions_detected"],
            ["0.150.1", "0.154.0"],
        )
        self.assertTrue(record["capabilities"]["version_probe"])
        # A recommendation must not create or change a team binding: discovery
        # only writes discovery records.
        with self.store.connect() as conn:
            bindings = conn.execute(
                "SELECT * FROM supervisor_team_bindings"
            ).fetchall()
        self.assertEqual(bindings, [])


class GuiOnlyTargetTests(unittest.TestCase):
    """A desktop application must never look invocable."""

    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = CouncilStore(Path(self.temp.name) / "council.db")
        self.registry = RegistryService(self.store)
        self.probes: list[str] = []

    def _service(self, gui_targets):
        def probe(executable, bound):
            self.probes.append(executable)
            return "1.0.0"

        return DiscoveryService(
            None,
            self.registry,
            adapters={},
            known_targets=(),
            gui_targets=gui_targets,
            version_probe=probe,
        )

    def _gui_target(self, key="zcode", name="ZCode"):
        return LocalAgentTarget(
            key,
            name,
            (),
            version_arguments=(),
            interface_kind="gui_only",
        )

    def test_a_gui_target_is_recorded_as_not_invocable(self):
        service = self._service((self._gui_target(),))
        service.scan()

        record = self.registry.discovery_record("known:zcode")
        self.assertIsNotNone(record)
        self.assertEqual(record["target_kind"], "gui_only_application")
        self.assertEqual(record["adapter_type"], "manual")
        self.assertIsNone(record["agent_id"])
        self.assertIsNone(record["resolved_executable"])
        self.assertFalse(record["capabilities"]["invocable"])
        self.assertTrue(record["capabilities"]["manual_setup"])
        self.assertFalse(record["capabilities"]["version_probe"])
        self.assertEqual(record["details"]["interface_kind"], "gui_only")
        self.assertTrue(record["details"]["requires_manual_handoff"])

    def test_no_command_is_probed_for_a_gui_target(self):
        service = self._service((self._gui_target(),))
        service.scan()
        self.assertEqual(self.probes, [])

    def test_a_gui_target_creates_no_runnable_agent(self):
        service = self._service((self._gui_target(),))
        service.scan()
        # No Agent profile is registered for a GUI-only entry, so nothing can be
        # routed to it. A CLI target in the same run would register one, which
        # is why the assertion is scoped to the GUI key rather than to the
        # total count.
        with self.store.connect() as conn:
            profiles = conn.execute(
                "SELECT id FROM agent_profiles"
            ).fetchall()
            discovered = conn.execute(
                """
                SELECT agent_id FROM agent_discovery
                WHERE id = 'known:zcode'
                """
            ).fetchone()
        self.assertEqual(profiles, [])
        self.assertIsNone(discovered["agent_id"])

    def test_install_locations_are_preserved_across_scans(self):
        target = self._gui_target()
        service = self._service((target,))
        service.scan()
        with self.store.connect() as conn:
            conn.execute(
                """
                UPDATE agent_discovery
                SET details_json = ?
                WHERE id = 'known:zcode'
                """,
                (
                    json.dumps(
                        {
                            "interface_kind": "gui_only",
                            "install_locations": ["/fake/ZCode.exe"],
                        }
                    ),
                ),
            )
        service.scan()
        record = self.registry.discovery_record("known:zcode")
        self.assertEqual(
            record["details"]["install_locations"],
            ["/fake/ZCode.exe"],
        )

    def test_gui_catalogue_rejects_a_cli_entry(self):
        with self.assertRaises(ValueError):
            gui_targets_from_config(
                [{"key": "x", "command_candidates": ["x"]}]
            )

    def test_gui_catalogue_allows_an_empty_list(self):
        self.assertEqual(gui_targets_from_config([]), ())

    def test_a_cli_target_still_requires_a_command(self):
        with self.assertRaises(ValueError):
            target_from_config(
                {"key": "x", "interface_kind": "cli"},
                "discovery_targets[0]",
            )

    def test_an_unknown_interface_kind_is_rejected(self):
        with self.assertRaises(ValueError):
            target_from_config(
                {
                    "key": "x",
                    "command_candidates": ["x"],
                    "interface_kind": "magic",
                },
                "discovery_targets[0]",
            )

    def test_the_cli_and_gui_catalogues_stay_separate(self):
        service = self._service((self._gui_target("zcode"),))
        service.known_targets = ()
        self.assertEqual(len(service.gui_targets), 1)
        self.assertEqual(service.gui_targets[0].interface_kind, "gui_only")


class RealProbeTests(unittest.TestCase):
    """Exercise the real probe against a real executable on this machine.

    The probe is argument-array and shell-free. It only asks the tool to
    identify itself; no project context is sent. If no agent is installed the
    test is skipped rather than weakened.
    """

    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = CouncilStore(Path(self.temp.name) / "council.db")
        self.registry = RegistryService(self.store)

    def test_probes_an_installed_agent_or_skips(self):
        service = DiscoveryService(
            None,
            self.registry,
            adapters={},
            known_targets=KNOWN_LOCAL_AGENTS,
        )
        found = []
        for target in KNOWN_LOCAL_AGENTS:
            ranking = service.version_candidates(target)
            if ranking["versions_detected"]:
                found.append((target.key, ranking["versions_detected"]))
        if not found:
            self.skipTest("no known Agent executable is installed on PATH")
        for key, versions in found:
            with self.subTest(agent=key):
                self.assertTrue(versions)
                for value in versions:
                    self.assertTrue(value)
                self.assertNotIn("\\", versions[0])


if __name__ == "__main__":
    unittest.main()
