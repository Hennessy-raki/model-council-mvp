# -*- coding: utf-8 -*-
"""对本地 runtime 状态做就地脱敏：只替换机器可识别「值」，不改结构。

背景
----
项目此前的隐私工具只扫描 Git 跟踪与非忽略路径，而 runtime 被 .gitignore
忽略，因此从未被检查。实际检查发现：
  - artifacts.path 等列存有 C:\\Users\\<真实用户名>\\... 绝对路径
  - interoperability_* 表的 payload 里含 codexHome（真实用户名）、cwd、userAgent

按操作者要求（个人隐私不得被他人掌握），这些值必须从本机文件中消除。
本脚本采取「结构保留、值脱敏」策略：行数、表结构、记录关系一律不变，
只把机器可识别的值替换为占位符。

替换规则
--------
  C:\\Users\\<名字>        -> C:\\Users\\<USER>
  C:/Users/<名字>          -> C:/Users/<USER>
  Windows <版本>.<构建>    -> Windows <REDACTED-BUILD>
  (macOS|Mac OS X|Darwin) 同理

不可逆：请在运行前确认已有备份。
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sqlite3
import sys
from pathlib import Path


# 置于 --dry-run 之后，避免把真实用户名写进本文件。
# 这里只定义"形如"的模式，实际值在运行时从目标文件中匹配。
USER_PATH_BACKSLASH = re.compile(
    rb"(?i)([A-Z]:[\\/]+Users[\\/]+)(?![<%$])[^\\/\s\"'<>]+"
)
USER_PATH_FORWARD = re.compile(
    rb"(?i)([A-Z]:[\\/]+Users[\\/]+)(?![<%$])[^\\/\s\"'<>]+"
)
BUILD_FINGERPRINT = re.compile(
    rb"(?i)\b((?:Windows|Mac OS X|Darwin))\s+(\d+(?:\.\d+){1,4})"
)

USER_MARKER = rb"\1<USER>"
BUILD_MARKER = rb"\1 <REDACTED-BUILD>"


def redact_bytes(raw: bytes) -> tuple[bytes, dict[str, int]]:
    counts = {"user_path": 0, "build_fingerprint": 0}
    out, n = USER_PATH_BACKSLASH.subn(USER_MARKER, raw)
    counts["user_path"] += n
    raw, n = USER_PATH_FORWARD.subn(USER_MARKER, out)
    counts["user_path"] += n
    out, n = BUILD_FINGERPRINT.subn(BUILD_MARKER, raw)
    counts["build_fingerprint"] += n
    return out, counts


def redact_sqlite(path: Path, dry_run: bool) -> dict[str, object]:
    con = sqlite3.connect(path)
    con.execute("PRAGMA foreign_keys=ON")
    result: dict[str, object] = {
        "path": str(path),
        "rows_before": 0,
        "rows_after": 0,
        "cells_changed": 0,
        "details": [],
        "counts": {"user_path": 0, "build_fingerprint": 0},
    }
    tables = [
        r[0]
        for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    ]
    for table in tables:
        cols = [
            (c[1], c[2])
            for c in con.execute(f'PRAGMA table_info("{table}")').fetchall()
        ]
        if not cols:
            continue
        names = [c[0] for c in cols]
        where = " AND ".join(f'"{n}" IS NOT NULL' for n in names)
        try:
            rows = con.execute(
                f'SELECT rowid, {", ".join(chr(34) + n + chr(34) for n in names)}'
                f' FROM "{table}"'
            ).fetchall()
        except sqlite3.Error:
            continue
        result["rows_before"] += len(rows)
        for row in rows:
            rowid = row[0]
            for (col, _typ), value in zip(cols, row[1:]):
                if value is None:
                    continue
                changed = False
                counts = {"user_path": 0, "build_fingerprint": 0}
                if isinstance(value, str):
                    new, counts = redact_bytes(value.encode("utf-8"))
                    new_text = new.decode("utf-8")
                    if new_text != value:
                        changed = True
                        value_out: object = new_text
                    else:
                        value_out = value
                elif isinstance(value, (bytes, bytearray)):
                    new, counts = redact_bytes(bytes(value))
                    if new != bytes(value):
                        changed = True
                        value_out = new
                    else:
                        value_out = value
                else:
                    continue
                if not changed:
                    continue
                result["cells_changed"] += 1
                for key, n in counts.items():
                    result["counts"][key] += n
                detail = {
                    "table": table,
                    "column": col,
                    "rowid": rowid,
                    "counts": counts,
                }
                result["details"].append(detail)
                if not dry_run:
                    con.execute(
                        f'UPDATE "{table}" SET "{col}" = ? WHERE rowid = ?',
                        (value_out, rowid),
                    )
    if not dry_run:
        con.commit()
    result["rows_after"] = sum(
        con.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
        for t in tables
    )
    con.close()
    return result


def compact_database(path: Path) -> dict[str, int]:
    """Rebuild the file so freed pages no longer carry the old values.

    SQLite keeps a freed page's old bytes in the file when `secure_delete` is
    off, which it is by default. A redaction that only rewrites rows therefore
    leaves the previous values recoverable from the raw file. Rebuilding the
    database is what actually removes them.
    """
    before = path.stat().st_size
    con = sqlite3.connect(path)
    try:
        con.execute("PRAGMA secure_delete=ON")
        con.execute("VACUUM")
        con.commit()
    finally:
        con.close()
    after = path.stat().st_size
    return {"bytes_before": before, "bytes_after": after}


TEXT_SUFFIXES = (".md", ".txt", ".json", ".jsonl", ".log", ".yaml", ".yml")


def redact_text_file(path: Path, dry_run: bool) -> dict[str, object] | None:
    raw = path.read_bytes()
    new, counts = redact_bytes(raw)
    if new == raw:
        return None
    if not dry_run:
        path.write_bytes(new)
    return {"path": str(path), "counts": counts, "bytes": len(raw)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Redact machine-identifying values in local runtime state while "
            "preserving every table, row and relationship."
        )
    )
    parser.add_argument(
        "--root",
        type=Path,
        required=True,
        help="repository root containing runtime/ and runtime-*/ directories",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="report what would change without writing",
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help=(
            "rebuild each database after redaction with secure_delete enabled, "
            "so freed pages no longer contain the previous values"
        ),
    )
    parser.add_argument(
        "--text-files",
        action="store_true",
        help=(
            "also redact plain runtime text files; use with care, because a "
            "rewrite is not reversible without a backup"
        ),
    )
    args = parser.parse_args(argv)
    root = args.root.resolve()
    databases: list[Path] = []
    for pattern in ("runtime", "runtime-*"):
        for directory in sorted(root.glob(pattern)):
            if directory.is_dir():
                databases.extend(sorted(directory.rglob("*.db")))
    if not databases:
        print("no runtime databases found")
        return 0

    total_cells = 0
    total_counts = {"user_path": 0, "build_fingerprint": 0}
    for database in databases:
        before = hashlib.sha256(database.read_bytes()).hexdigest()[:12]
        report = redact_sqlite(database, args.dry_run)
        compact_report = None
        if args.compact and not args.dry_run:
            compact_report = compact_database(database)
        after = hashlib.sha256(database.read_bytes()).hexdigest()[:12]
        print("=" * 70)
        print(f"database      : {database.relative_to(root).as_posix()}")
        print(f"sha256 before : {before}")
        print(f"sha256 after  : {after}")
        print(f"rows before   : {report['rows_before']}")
        print(f"rows after    : {report['rows_after']}")
        print(f"cells changed : {report['cells_changed']}")
        print(
            "replacements  : "
            f"user_path={report['counts']['user_path']} "
            f"build_fingerprint={report['counts']['build_fingerprint']}"
        )
        if compact_report is not None:
            print(
                "compacted     : "
                f"{compact_report['bytes_before']} -> "
                f"{compact_report['bytes_after']} bytes"
            )
        for detail in report["details"]:
            print(
                f"   {detail['table']}.{detail['column']} "
                f"rowid={detail['rowid']} {detail['counts']}"
            )
        total_cells += report["cells_changed"]
        for key in total_counts:
            total_counts[key] += report["counts"][key]
    print("=" * 70)
    print(
        f"TOTAL cells={total_cells} "
        f"user_path={total_counts['user_path']} "
        f"build_fingerprint={total_counts['build_fingerprint']}"
    )
    if args.text_files:
        text_count = 0
        for pattern in ("runtime", "runtime-*"):
            for directory in sorted(root.glob(pattern)):
                if not directory.is_dir():
                    continue
                for path in sorted(directory.rglob("*")):
                    if not path.is_file():
                        continue
                    if path.suffix.lower() not in TEXT_SUFFIXES:
                        continue
                    outcome = redact_text_file(path, args.dry_run)
                    if outcome is None:
                        continue
                    text_count += 1
                    print(
                        f"text file redacted: "
                        f"{path.relative_to(root).as_posix()} "
                        f"{outcome['counts']}"
                    )
        print(f"TOTAL text files changed={text_count}")
    print("mode:", "DRY RUN (nothing written)" if args.dry_run else "WRITTEN")
    return 0


if __name__ == "__main__":
    sys.exit(main())
