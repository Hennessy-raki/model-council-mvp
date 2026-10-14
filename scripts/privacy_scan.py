from __future__ import annotations

import argparse
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path


MAX_TEXT_BYTES = 2_000_000
ALLOWED_EMAIL_DOMAINS = {
    "example.com",
    "example.org",
    "example.net",
    "localhost",
    "users.noreply.github.com",
}


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    kind: str


PATTERNS = (
    (
        "windows_user_path",
        re.compile(r"(?i)[A-Z]:[\\/]+Users[\\/]+(?![<%$])[^\\/\s\"']+"),
    ),
    (
        "unix_home_path",
        re.compile(r"(?i)/(?:Users|home)/(?![<%$])[^/\s\"']+"),
    ),
    (
        "private_key",
        re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----"),
    ),
    (
        "openai_style_secret",
        re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    ),
    (
        "github_token",
        re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    ),
    (
        "aws_access_key",
        re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    ),
    (
        "os_build_fingerprint",
        re.compile(
            r"(?i)\b(?:Windows|Mac OS X|Darwin)\s+\d+(?:\.\d+){1,4}"
            r"(?:\s*;\s*[A-Za-z0-9_]+)*"
        ),
    ),
)


# Local runtime state is excluded from Git, so the repository scan above never
# reads it. The operator requirement is that no machine-identifying information
# should be recoverable from this host by a third party, and an ignored file on
# disk is still recoverable if the machine or the directory is ever copied. The
# scan below therefore inspects those directories explicitly.
RUNTIME_STATE_DIRECTORIES = ("runtime",)
RUNTIME_STATE_GLOBS = ("runtime-*",)
RUNTIME_STATE_MAX_BYTES = 64 * 1024 * 1024
BINARY_STATE_PATTERNS = (
    ("windows_user_path", re.compile(rb"(?i)[A-Z]:[\\/]+Users[\\/]+(?![<%$])[^\\/\s\"']+")),
    ("openai_style_secret", re.compile(rb"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("github_token", re.compile(rb"\bgh[pousr]_[A-Za-z0-9]{20,}\b")),
    ("aws_access_key", re.compile(rb"\bAKIA[0-9A-Z]{16}\b")),
    ("private_key", re.compile(rb"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----")),
    ("os_build_fingerprint", re.compile(rb"(?i)\bWindows\s+\d+(?:\.\d+){1,4}")),
)
EMAIL_PATTERN = re.compile(
    r"\b[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+"
    r"@([A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+)\b"
)


def scan_text(path: str, text: str) -> list[Finding]:
    findings: list[Finding] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        for kind, pattern in PATTERNS:
            if pattern.search(line):
                findings.append(Finding(path, line_number, kind))
        for match in EMAIL_PATTERN.finditer(line):
            if match.group(1).lower() not in ALLOWED_EMAIL_DOMAINS:
                findings.append(
                    Finding(path, line_number, "email_address")
                )
    return findings


def repository_files(root: Path) -> list[Path]:
    completed = subprocess.run(
        [
            "git",
            "ls-files",
            "--cached",
            "--others",
            "--exclude-standard",
            "-z",
        ],
        cwd=root,
        check=True,
        capture_output=True,
    )
    return [
        root / item.decode("utf-8")
        for item in completed.stdout.split(b"\0")
        if item
    ]


def scan_repository(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for path in repository_files(root):
        if not path.is_file() or path.stat().st_size > MAX_TEXT_BYTES:
            continue
        raw = path.read_bytes()
        if b"\0" in raw:
            continue
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            continue
        findings.extend(
            scan_text(path.relative_to(root).as_posix(), text)
        )
    return findings


def scan_history(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    objects = subprocess.run(
        ["git", "rev-list", "--objects", "--all"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout.splitlines()
    allowed_objects: set[str] = set()
    for item in objects:
        parts = item.split(" ", 1)
        if len(parts) != 2:
            continue
        object_id, path = parts
        allowed_objects.add(object_id)
    for object_id in allowed_objects:
        object_type = subprocess.run(
            ["git", "cat-file", "-t", object_id],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        ).stdout.strip()
        if object_type != "blob":
            continue
        size = int(
            subprocess.run(
                ["git", "cat-file", "-s", object_id],
                cwd=root,
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
            ).stdout.strip()
        )
        if size > MAX_TEXT_BYTES:
            continue
        raw = subprocess.run(
            ["git", "cat-file", "blob", object_id],
            cwd=root,
            check=True,
            capture_output=True,
        ).stdout
        if b"\0" in raw:
            continue
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            continue
        findings.extend(
            scan_text(f"history-blob:{object_id[:12]}", text)
        )
    findings.extend(scan_commit_authors(root))
    return findings


def runtime_state_directories(root: Path) -> list[Path]:
    directories: list[Path] = []
    for name in RUNTIME_STATE_DIRECTORIES:
        candidate = root / name
        if candidate.is_dir():
            directories.append(candidate)
    for pattern in RUNTIME_STATE_GLOBS:
        for candidate in sorted(root.glob(pattern)):
            if candidate.is_dir() and candidate not in directories:
                directories.append(candidate)
    return directories


def scan_local_state(root: Path) -> tuple[list[Finding], list[Path]]:
    """Scan ignored local runtime state for recoverable machine identity.

    Findings here are recorded, not enforced, because this scanner is also run
    as a release gate and local state legitimately contains runtime records that
    were never meant for publication. The purpose is visibility: the operator
    must be able to see what a third party could recover from this host.
    """
    findings: list[Finding] = []
    scanned: list[Path] = []
    for directory in runtime_state_directories(root):
        scanned.append(directory)
        for path in sorted(directory.rglob("*")):
            if not path.is_file():
                continue
            try:
                if path.stat().st_size > RUNTIME_STATE_MAX_BYTES:
                    continue
                raw = path.read_bytes()
            except OSError:
                continue
            label = path.relative_to(root).as_posix()
            if b"\0" in raw:
                findings.extend(scan_binary_state(label, raw))
                continue
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                findings.extend(scan_binary_state(label, raw))
                continue
            findings.extend(scan_text(label, text))
    return findings, scanned


def scan_binary_state(label: str, raw: bytes) -> list[Finding]:
    """Scan a binary file (for example SQLite) as raw bytes.

    Local runtime databases and archives are not UTF-8 text, so a text pass
    would miss them entirely. Matching the byte stream directly finds the same
    machine-identifying values without needing to parse every file format.
    """
    findings: list[Finding] = []
    seen: set[str] = set()
    for kind, pattern in BINARY_STATE_PATTERNS:
        if pattern.search(raw):
            if kind not in seen:
                seen.add(kind)
                findings.append(Finding(label, 0, kind))
    return findings


def scan_commit_authors(root: Path) -> list[Finding]:
    output = subprocess.run(
        ["git", "log", "--all", "--format=%H%x00%ae"],
        cwd=root,
        check=True,
        capture_output=True,
    ).stdout
    findings = []
    for raw_line in output.splitlines():
        commit_id, email = raw_line.decode("utf-8").split("\0", 1)
        domain = email.rsplit("@", 1)[-1].lower()
        if domain not in ALLOWED_EMAIL_DOMAINS:
            findings.append(
                Finding(
                    f"commit:{commit_id[:12]}",
                    0,
                    "commit_author_email",
                )
            )
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Scan tracked and non-ignored repository text for high-confidence "
            "credentials and personal-path indicators without printing values."
        )
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="repository root (default: current directory)",
    )
    parser.add_argument(
        "--history",
        action="store_true",
        help="also scan reachable historical blobs and commit-author domains",
    )
    parser.add_argument(
        "--local-state",
        action="store_true",
        help=(
            "also report machine-identifying values recoverable from ignored "
            "local runtime state; these findings are reported but do not fail "
            "the scan, because local runtime data is legitimate and is not "
            "published"
        ),
    )
    args = parser.parse_args(argv)
    root = args.root.resolve()
    findings = scan_repository(root)
    if args.history:
        findings.extend(scan_history(root))
    if args.local_state:
        state_findings, scanned = scan_local_state(root)
        print("Local runtime state inspection (informational):")
        if not scanned:
            print("  no runtime state directories found")
        for directory in scanned:
            print(f"  scanned {directory.relative_to(root).as_posix()}")
        if state_findings:
            for item in state_findings:
                print(f"  local-state {item.path}: {item.kind}")
            print(
                f"  {len(state_findings)} machine-identifying value(s) are "
                "recoverable from this host. Remove the runtime directory "
                "before archiving, copying or migrating the working tree."
            )
        else:
            print("  no machine-identifying values found")
    if findings:
        for item in findings:
            print(f"{item.path}:{item.line}: {item.kind}")
        print(f"Privacy scan failed with {len(findings)} finding(s).")
        return 1
    print("Privacy scan passed: no high-confidence findings.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
