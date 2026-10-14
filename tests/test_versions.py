from __future__ import annotations

import unittest

from model_council.versions import (
    RECOMMENDATION_NONE,
    RECOMMENDATION_RECOMMENDED,
    RECOMMENDATION_UNDECIDABLE,
    RECOMMENDATION_USER_PREFERENCE,
    REASON_ALL_CANDIDATES_PRERELEASE,
    REASON_EXACT_SEMVER,
    REASON_NUMERIC_SEGMENTS,
    REASON_SINGLE_CANDIDATE,
    REASON_STABLE_OVER_PRERELEASE,
    REASON_UNDECIDABLE_VERSION_FORMAT,
    REASON_USER_OVERRIDE,
    compare_versions,
    is_parsed,
    parse_version,
    plan_upgrade,
    version_kind,
)


class ParseVersionTests(unittest.TestCase):
    def test_parses_the_version_shapes_observed_on_this_machine(self):
        for value in (
            "0.154.0",
            "1.7.0-rc.1",
            "1.35.0",
            "3.14.5.7961",
            "2.3.91089",
            "0.2.0-rc.2",
            "2.30.4",
            "2.1.6",
            "5.6.2",
        ):
            with self.subTest(value=value):
                self.assertTrue(is_parsed(parse_version(value)))

    def test_accepts_prefixes_and_operators(self):
        self.assertEqual(parse_version("v1.35.0"), parse_version("1.35.0"))
        self.assertEqual(parse_version("V1.35.0"), parse_version("1.35.0"))
        self.assertEqual(parse_version("=1.35.0"), parse_version("1.35.0"))
        self.assertEqual(parse_version(" 1.35.0 "), parse_version("1.35.0"))

    def test_rejects_values_without_a_numeric_form(self):
        for value in ("", "   ", None, 17, "latest", "stable", "unknown", []):
            with self.subTest(value=value):
                self.assertFalse(is_parsed(parse_version(value)))

    def test_classifies_stable_and_prerelease(self):
        self.assertEqual(version_kind("1.35.0"), "release")
        self.assertEqual(version_kind("1.7.0-rc.1"), "prerelease")
        self.assertEqual(version_kind("0.2.0-rc.2"), "prerelease")
        self.assertIsNone(version_kind("latest"))

    def test_a_date_like_version_has_no_comparable_form(self):
        # A date is not a version. Reporting it as unparsed is the honest
        # answer; reading it as '2024' with a suffix would invent an order.
        self.assertIsNone(version_kind("2024-08-29"))
        self.assertFalse(is_parsed(parse_version("2024-08-29")))


class CompareVersionTests(unittest.TestCase):
    def test_numeric_segments_compare_numerically_not_lexically(self):
        # The trap this guards: '1.7' must be lower than '1.35', even though
        # the digit 7 sorts above the digit 3 in a string comparison.
        self.assertLess(
            compare_versions(parse_version("1.7.0"), parse_version("1.35.0")),
            0,
        )
        self.assertLess(
            compare_versions(parse_version("9.0.0"), parse_version("10.0.0")),
            0,
        )

    def test_missing_segments_are_treated_as_zero(self):
        self.assertEqual(
            compare_versions(parse_version("1.2"), parse_version("1.2.0")),
            0,
        )
        self.assertLess(
            compare_versions(parse_version("1.2.0"), parse_version("1.2.1")),
            0,
        )

    def test_a_stable_release_outranks_its_own_prereleases(self):
        self.assertLess(
            compare_versions(
                parse_version("1.35.0-rc.1"),
                parse_version("1.35.0"),
            ),
            0,
        )
        self.assertLess(
            compare_versions(
                parse_version("0.2.0-rc.2"),
                parse_version("0.2.0"),
            ),
            0,
        )

    def test_prerelease_ordering_within_the_same_number(self):
        self.assertLess(
            compare_versions(
                parse_version("1.0.0-beta"),
                parse_version("1.0.0-rc"),
            ),
            0,
        )
        self.assertLess(
            compare_versions(
                parse_version("1.0.0-alpha"),
                parse_version("1.0.0-beta"),
            ),
            0,
        )

    def test_a_parsed_version_outranks_an_unparsed_one(self):
        self.assertLess(
            compare_versions(parse_version("latest"), parse_version("0.0.1")),
            0,
        )
        self.assertGreater(
            compare_versions(parse_version("0.0.1"), parse_version("latest")),
            0,
        )
        self.assertEqual(
            compare_versions(parse_version("latest"), parse_version("unknown")),
            0,
        )

    def test_four_segment_versions_compare_by_segment(self):
        self.assertLess(
            compare_versions(
                parse_version("3.14.5.7961"),
                parse_version("3.14.5.7962"),
            ),
            0,
        )
        self.assertLess(
            compare_versions(
                parse_version("3.14.5.7961"),
                parse_version("3.15.0.0"),
            ),
            0,
        )


class UpgradePlanTests(unittest.TestCase):
    def test_single_candidate_is_recommended_without_comparison(self):
        result = plan_upgrade([{"version": "1.0.0", "source": "path"}])
        self.assertEqual(result["recommendation"], RECOMMENDATION_RECOMMENDED)
        self.assertEqual(result["reason"], REASON_SINGLE_CANDIDATE)
        self.assertEqual(result["recommended_version"], "1.0.0")
        self.assertFalse(result["auto_switch"])

    def test_no_candidates_is_reported_not_guessed(self):
        result = plan_upgrade([])
        self.assertEqual(result["recommendation"], RECOMMENDATION_NONE)
        self.assertIsNone(result["recommended_version"])

    def test_higher_version_wins_across_sources(self):
        result = plan_upgrade(
            [
                {"version": "1.7.0-rc.1", "source": "path"},
                {"version": "1.35.0", "source": "app"},
            ]
        )
        self.assertEqual(result["recommendation"], RECOMMENDATION_RECOMMENDED)
        self.assertEqual(result["recommended_version"], "1.35.0")
        self.assertEqual(result["recommended_source"], "app")
        self.assertEqual(result["reason"], REASON_STABLE_OVER_PRERELEASE)
        self.assertIn("1.7.0-rc.1", result["explanation"])

    def test_stable_absolute_priority_rejects_a_higher_prerelease(self):
        # The operator chose stable-absolute-priority: 1.34.9 outranks
        # 1.35.0-rc1 because a pre-release is not recommended while any stable
        # release exists, even though 1.35.0 is the larger number.
        result = plan_upgrade(
            [
                {"version": "1.34.9", "source": "path"},
                {"version": "1.35.0-rc.1", "source": "app"},
            ]
        )
        self.assertEqual(result["recommendation"], RECOMMENDATION_RECOMMENDED)
        self.assertEqual(result["recommended_version"], "1.34.9")
        self.assertEqual(result["reason"], REASON_STABLE_OVER_PRERELEASE)
        self.assertIn("1.35.0-rc.1", result["explanation"])

    def test_stable_absolute_priority_can_be_turned_off(self):
        # The other reading of the rule: rank purely by number. Kept available
        # because the setting is a decision, not a law.
        result = plan_upgrade(
            [
                {"version": "1.34.9", "source": "path"},
                {"version": "1.35.0-rc.1", "source": "app"},
            ],
            stable_absolute_priority=False,
        )
        self.assertEqual(result["recommended_version"], "1.35.0-rc.1")

    def test_all_prereleases_still_compares_them(self):
        result = plan_upgrade(
            [
                {"version": "1.7.0-rc.1", "source": "path"},
                {"version": "1.8.0-rc.1", "source": "app"},
            ]
        )
        self.assertEqual(result["recommendation"], RECOMMENDATION_RECOMMENDED)
        self.assertEqual(result["recommended_version"], "1.8.0-rc.1")
        self.assertEqual(
            result["reason"],
            REASON_ALL_CANDIDATES_PRERELEASE,
        )

    def test_equal_versions_are_broken_by_source_with_path_first(self):
        result = plan_upgrade(
            [
                {"version": "0.154.0", "source": "app", "path": "app"},
                {"version": "0.154.0", "source": "path", "path": "path"},
            ]
        )
        self.assertEqual(result["recommended_version"], "0.154.0")
        self.assertEqual(result["recommended_source"], "path")
        self.assertEqual(result["reason"], REASON_EXACT_SEMVER)

    def test_numeric_segment_reason_is_reported(self):
        result = plan_upgrade(
            [
                {"version": "3.14.5.7961", "source": "app"},
                {"version": "3.14.5.7962", "source": "app"},
            ]
        )
        self.assertEqual(result["recommended_version"], "3.14.5.7962")
        self.assertEqual(result["reason"], REASON_NUMERIC_SEGMENTS)

    def test_uncomparable_versions_are_not_guessed(self):
        result = plan_upgrade(
            [
                {"version": "1.35.0", "source": "path"},
                {"version": "latest", "source": "app"},
            ]
        )
        self.assertEqual(result["recommendation"], RECOMMENDATION_UNDECIDABLE)
        self.assertEqual(
            result["reason"],
            REASON_UNDECIDABLE_VERSION_FORMAT,
        )
        self.assertIsNone(result["recommended_version"])

    def test_non_object_candidate_is_rejected(self):
        result = plan_upgrade(["1.0.0"])
        self.assertEqual(result["recommendation"], RECOMMENDATION_UNDECIDABLE)
        self.assertIsNone(result["recommended_version"])

    def test_user_preference_overrides_the_computed_recommendation(self):
        # The requirement: a recommendation must never trap the operator in the
        # version the system prefers.
        result = plan_upgrade(
            [
                {"version": "1.7.0-rc.1", "source": "path"},
                {"version": "1.35.0", "source": "app"},
            ],
            preferred_version="1.7.0-rc.1",
        )
        self.assertEqual(
            result["recommendation"],
            RECOMMENDATION_USER_PREFERENCE,
        )
        self.assertEqual(result["reason"], REASON_USER_OVERRIDE)
        self.assertEqual(result["recommended_version"], "1.7.0-rc.1")
        self.assertIn("1.35.0", result["alternatives"])
        self.assertFalse(result["auto_switch"])

    def test_user_preference_must_exist_among_the_candidates(self):
        result = plan_upgrade(
            [{"version": "1.0.0", "source": "path"}],
            preferred_version="9.9.9",
        )
        self.assertEqual(result["recommendation"], RECOMMENDATION_UNDECIDABLE)
        self.assertIsNone(result["recommended_version"])

    def test_recommendation_never_authorizes_a_switch(self):
        for candidates in (
            [{"version": "1.0.0", "source": "path"}],
            [
                {"version": "1.0.0", "source": "path"},
                {"version": "2.0.0", "source": "app"},
            ],
        ):
            with self.subTest(candidates=candidates):
                self.assertFalse(plan_upgrade(candidates)["auto_switch"])


if __name__ == "__main__":
    unittest.main()
