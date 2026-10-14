from __future__ import annotations

import re
from typing import Any


VERSION_KIND_RELEASE = "release"
VERSION_KIND_PRERELEASE = "prerelease"

RECOMMENDATION_RECOMMENDED = "recommended"
RECOMMENDATION_UNDECIDABLE = "undecidable"
RECOMMENDATION_USER_PREFERENCE = "user_preference"
RECOMMENDATION_NONE = "no_candidates"
RECOMMENDATION_AMBIGUOUS = "ambiguous_candidates"

REASON_SINGLE_CANDIDATE = "single_candidate"
REASON_UNDECIDABLE_VERSION_FORMAT = "undecidable_version_format"
REASON_EXACT_SEMVER = "exact_semver_comparison"
REASON_NUMERIC_SEGMENTS = "numeric_segment_comparison"
REASON_STABLE_OVER_PRERELEASE = "stable_release_preferred_over_prerelease"
REASON_ALL_CANDIDATES_PRERELEASE = "all_candidates_are_prereleases"
REASON_NOT_COMPARABLE = "not_comparable"
REASON_USER_OVERRIDE = "explicit_user_preference"

# Ordering of the three parse states. A version that parses outranks one that
# does not, so the caller never has to fall back to string comparison, which
# would order '10.0.0' below '9.0.0'.
_PARSE_KIND_UNPARSED = 0
_PARSE_KIND_NUMERIC = 1
_PARSE_KIND_SEMVER = 2

# Values that carry no order at all keep a non-empty numeric tuple so that a
# comparison against a parsed key cannot raise on tuple length.
_KEY_UNPARSED = (_PARSE_KIND_UNPARSED, (-1,), 0, ())


def parse_version(text: Any) -> tuple[int, tuple[int, ...], int, tuple[str, ...]]:
    """Parse a version string into a comparable key.

    The key encodes three things in priority order: whether the value parsed at
    all, the numeric segments, and the pre-release parts. A parsed version
    always outranks an unparsed one, and the caller is expected to treat a
    mixture of parsed and unparsed values as undecidable rather than guessing.
    """
    if not isinstance(text, str):
        return _KEY_UNPARSED
    candidate = text.strip()
    if not candidate:
        return _KEY_UNPARSED
    marker = candidate[0]
    if marker in ("=", "~", "^", ">", "<", "!", " "):
        candidate = candidate[1:].strip()
    candidate = candidate.lstrip("vV").strip()
    if not candidate:
        return _KEY_UNPARSED
    # Only a three-segment version may carry a pre-release suffix, which is
    # what semver specifies. Requiring that keeps a date-like value such as
    # '2024-08-29' out of the pre-release branch: it has no comparable form and
    # is reported as unparsed instead of being read as '2024' with a suffix.
    core = candidate
    prerelease_text = ""
    for index, character in enumerate(candidate):
        if character in ("-", "+"):
            prefix = candidate[:index]
            suffix = candidate[index + 1 :]
            if len(prefix.split(".")) == 3 and all(
                part.isdigit() for part in prefix.split(".")
            ):
                core = prefix
                prerelease_text = suffix
            break
    core = core.rstrip(".")
    segments_text = core.split(".")
    if not segments_text or any(not part.isdigit() for part in segments_text):
        return _KEY_UNPARSED
    segments = tuple(int(part) for part in segments_text)
    # Normalise trailing zeros so that '1.2' and '1.2.0' are the same version.
    while len(segments) > 1 and segments[-1] == 0:
        segments = segments[:-1]
    if prerelease_text == "":
        return (_PARSE_KIND_SEMVER, segments, 0, ())
    parts = tuple(
        part for part in prerelease_text.replace("_", ".").split(".") if part
    )
    if not parts:
        return (_PARSE_KIND_SEMVER, segments, 0, ())
    return (
        _PARSE_KIND_SEMVER,
        segments,
        1,
        tuple(part.lower() for part in parts),
    )


def is_parsed(key) -> bool:
    return key is not None and key[0] != _PARSE_KIND_UNPARSED


def compare_versions(left_key, right_key) -> int:
    """Return -1, 0 or 1 for two version keys.

    Unparsed values are accepted rather than rejected, so the caller can order a
    mixed set without a guard. A parsed value always outranks an unparsed one.
    Two unparsed values compare equal, which is the safest reading: neither has
    a defensible order, and the caller is expected to treat a mixed set as
    undecidable rather than relying on that equality.
    """
    left_unparsed = left_key is None or left_key[0] == _PARSE_KIND_UNPARSED
    right_unparsed = right_key is None or right_key[0] == _PARSE_KIND_UNPARSED
    if left_unparsed or right_unparsed:
        if left_unparsed and right_unparsed:
            return 0
        return -1 if left_unparsed else 1
    if left_key[0] != right_key[0]:
        return -1 if left_key[0] < right_key[0] else 1
    length = max(len(left_key[1]), len(right_key[1]))
    left_segments = left_key[1] + (0,) * (length - len(left_key[1]))
    right_segments = right_key[1] + (0,) * (length - len(right_key[1]))
    if left_segments != right_segments:
        # Compare the padded tuples, not the stored ones: trailing zeros are
        # normalised away at parse time, so '1.35' and '1.35.0' would otherwise
        # be treated as different numbers.
        return _order(left_segments, right_segments)
    # A stable release outranks a pre-release of the same number, so the
    # pre-release flag sorts descending: flag 1 (pre-release) is the smaller
    # version. Reading it as an ascending flag inverts the answer.
    if left_key[2] != right_key[2]:
        return _order(right_key[2], left_key[2])
    if left_key[3] != right_key[3]:
        return _order(left_key[3], right_key[3])
    return 0


def _order(left: Any, right: Any) -> int:
    """Return -1 when ``left`` sorts below ``right``, 1 when it sorts above.

    Written as an explicit three-way branch so a caller cannot invert the
    result by misreading a conditional expression's direction.
    """
    if left == right:
        return 0
    return -1 if left < right else 1


def version_kind(text: Any) -> str | None:
    key = parse_version(text)
    if not is_parsed(key):
        return None
    return VERSION_KIND_RELEASE if key[2] == 0 else VERSION_KIND_PRERELEASE


# A version token inside a larger output line. Real command output is messy:
# `codex --version` prints 'codex-cli 0.154.0', `reasonix --version` prints
# 'reasonix v1.35.0', and npm prints 'reasonix npm-v1.7.0-rc.1'. The token must
# begin with a digit, with an optional single-letter tag right before it, so a
# file extension such as '.exe' or a bare commit hash is not read as a version.
_OUTPUT_VERSION_RE = re.compile(
    r"(?<![\w.])"
    r"[vV]?\d+(?:\.\d+){1,3}(?:-[A-Za-z][A-Za-z0-9.]*)?"
    r"(?![A-Za-z0-9._-])"
)


def version_from_output(text: Any) -> str | None:
    """Extract the first version-shaped token from command output.

    Tools report their version in different shapes, so the value is located
    rather than assumed to be the whole output. A leading ``v`` is kept out of
    the returned string so that comparisons and display use one form.
    """
    if not isinstance(text, str) or not text:
        return None
    for line in text.splitlines():
        candidate = line.strip()
        if not candidate:
            continue
        for match in _OUTPUT_VERSION_RE.finditer(candidate):
            token = match.group(0)
            if version_kind(token) is None:
                continue
            return token[1:] if token[:1] in ("v", "V") else token
    return None


def plan_upgrade(
    candidates: Any,
    preferred_version: Any = None,
    stable_absolute_priority: bool = True,
) -> dict[str, Any]:
    """Recommend the version to prefer for one Agent.

    The recommendation is advisory by design. An explicit ``preferred_version``
    always wins, because the operator asked for that version. Nothing here
    changes a binding: the caller decides what to do with the recommendation.

    Stability acts at two separate levels, because the operator asked for both.
    At the level of comparing two versions, a stable release outranks only a
    pre-release of the *same* number: '1.35.0' beats '1.35.0-rc.1', while the
    comparison of '1.34.9' with '1.35.0-rc.1' is decided by the numbers. At the
    level of ranking candidates, ``stable_absolute_priority`` prefers any stable
    release over any pre-release, so '1.34.9' is recommended over
    '1.35.0-rc.1'. Pass ``False`` to rank purely by version number instead and
    fall back to the standard behaviour. Either way the switch is never
    automatic and the reason string records which rule decided.
    """
    if not isinstance(candidates, list):
        return _result(
            RECOMMENDATION_UNDECIDABLE,
            REASON_UNDECIDABLE_VERSION_FORMAT,
            [],
            None,
            None,
            "candidates must be a list",
        )
    entries: list[dict[str, Any]] = []
    for index, item in enumerate(candidates):
        if not isinstance(item, dict):
            return _result(
                RECOMMENDATION_UNDECIDABLE,
                REASON_UNDECIDABLE_VERSION_FORMAT,
                [],
                None,
                None,
                f"candidate {index} is not an object",
            )
        version = item.get("version")
        entries.append(
            {
                "key": parse_version(version),
                "version": version,
                "source": item.get("source"),
                "agent_id": item.get("agent_id"),
                "path": item.get("path"),
            }
        )

    if preferred_version is not None:
        matches = [
            item for item in entries if item["version"] == preferred_version
        ]
        if not matches:
            return _result(
                RECOMMENDATION_UNDECIDABLE,
                REASON_NOT_COMPARABLE,
                [item["version"] for item in entries],
                None,
                None,
                "the preferred version is not among the candidates",
            )
        chosen = matches[0]
        alternatives = [
            item["version"]
            for item in entries
            if item["version"] != preferred_version
        ]
        return _result(
            RECOMMENDATION_USER_PREFERENCE,
            REASON_USER_OVERRIDE,
            [item["version"] for item in entries],
            chosen["version"],
            chosen["source"],
            "user preference overrides the computed recommendation",
            alternatives,
        )

    if not entries:
        return _result(
            RECOMMENDATION_NONE,
            REASON_SINGLE_CANDIDATE,
            [],
            None,
            None,
            "no candidate versions were supplied",
        )
    if len(entries) == 1:
        only = entries[0]
        return _result(
            RECOMMENDATION_RECOMMENDED,
            REASON_SINGLE_CANDIDATE,
            [only["version"]],
            only["version"],
            only["source"],
            "there is only one candidate",
        )

    distinguishable = [item for item in entries if is_parsed(item["key"])]
    exactly_one_distinct = False
    if distinguishable:
        reference = distinguishable[0]["key"]
        exactly_one_distinct = all(
            item["key"] == reference for item in distinguishable
        )
    if not distinguishable or (
        exactly_one_distinct and len(distinguishable) != len(entries)
    ):
        # Either nothing parses, or a parsed value competes with an unparsed
        # one. Neither case supports a defensible ordering.
        return _result(
            RECOMMENDATION_UNDECIDABLE,
            REASON_UNDECIDABLE_VERSION_FORMAT,
            [item["version"] for item in entries],
            None,
            None,
            "at least one candidate version has no comparable numeric form",
        )

    kinds = {item["key"][2] for item in distinguishable}
    # Level two of the stability rule: when any stable release is present,
    # pre-releases are not recommended at all, even if their number is higher.
    pool = distinguishable
    stable_only = False
    if stable_absolute_priority:
        stable_pool = [
            item for item in distinguishable if item["key"][2] == 0
        ]
        if stable_pool:
            pool = stable_pool
            stable_only = len(stable_pool) != len(distinguishable)
    # The reason names the rule that actually decided, not merely which kinds
    # were present: with stable priority off, the numbers decide and saying
    # otherwise would misattribute the outcome.
    if stable_only:
        reason = REASON_STABLE_OVER_PRERELEASE
    elif len(kinds) == 1 and 1 in kinds:
        reason = REASON_ALL_CANDIDATES_PRERELEASE
    elif len(pool) > 1 and all(len(item["key"][1]) > 3 for item in pool):
        reason = REASON_NUMERIC_SEGMENTS
    else:
        reason = REASON_EXACT_SEMVER

    best = pool[0]
    for item in pool[1:]:
        if compare_versions(item["key"], best["key"]) > 0:
            best = item
    top = [
        item
        for item in pool
        if compare_versions(item["key"], best["key"]) == 0
    ]
    # Preference between sources applies only when the versions are equal.
    ordered_top = sorted(
        top,
        key=lambda item: (
            item["source"] != "path",
            str(item["source"]),
            str(item["agent_id"]),
            str(item["path"]),
        ),
    )
    chosen = ordered_top[0]
    alternatives = [
        item["version"] for item in entries if item is not chosen
    ]
    return _result(
        RECOMMENDATION_RECOMMENDED,
        reason,
        [item["version"] for item in entries],
        chosen["version"],
        chosen["source"],
        _explain(reason, chosen, entries),
        alternatives,
    )


def _explain(
    reason: str,
    chosen: dict[str, Any],
    entries: list[dict[str, Any]],
) -> str:
    others = [
        f"{item['version']} ({item['source']})"
        for item in entries
        if item is not chosen
    ]
    if reason == REASON_STABLE_OVER_PRERELEASE:
        return (
            f"{chosen['version']} ({chosen['source']}) is the highest stable "
            f"release; a stable release is preferred over any pre-release, so "
            f"a pre-release with a larger number is not recommended. "
            f"Rejected: {', '.join(others)}"
        )
    if reason == REASON_ALL_CANDIDATES_PRERELEASE:
        return (
            f"{chosen['version']} ({chosen['source']}) is the highest "
            f"pre-release and no stable release is available. "
            f"Rejected: {', '.join(others)}"
        )
    if reason == REASON_NUMERIC_SEGMENTS:
        return (
            f"{chosen['version']} ({chosen['source']}) is the highest by "
            f"numeric segment comparison. Rejected: {', '.join(others)}"
        )
    return (
        f"{chosen['version']} ({chosen['source']}) is the highest version. "
        f"Rejected: {', '.join(others)}"
    )


def _result(
    recommendation: str,
    reason: str,
    candidates: list[Any],
    version: Any,
    source: Any,
    explanation: str,
    alternatives: list[Any] | None = None,
) -> dict[str, Any]:
    return {
        "recommendation": recommendation,
        "reason": reason,
        "candidates": candidates,
        "recommended_version": version,
        "recommended_source": source,
        "explanation": explanation,
        "alternatives": alternatives or [],
        # A recommendation never authorizes replacing a binding or invoking an
        # Agent. It is evidence for a decision the operator still makes.
        "auto_switch": False,
    }
