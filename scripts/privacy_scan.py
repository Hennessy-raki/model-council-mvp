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
    seen: set[str] = set()
    for item in objects:
        object_id = item.split(" ", 1)[0]
        if object_id in seen:
            continue
        seen.add(object_id)
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
    args = parser.parse_args(argv)
    root = args.root.resolve()
    findings = scan_repository(root)
    if args.history:
        findings.extend(scan_history(root))
    if findings:
        for item in findings:
            print(f"{item.path}:{item.line}: {item.kind}")
        print(f"Privacy scan failed with {len(findings)} finding(s).")
        return 1
    print("Privacy scan passed: no high-confidence findings.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
