"""Scan repository text for a small set of likely live-secret patterns."""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path

MAX_FILE_BYTES = 1024 * 1024
PRIVATE_KEY_PATTERN = re.compile(r"-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY-----")
BEARER_PATTERN = re.compile(r"\bBearer\s+[A-Za-z0-9._~+/-]{8,}", re.IGNORECASE)
ASSIGNMENT_PATTERN = re.compile(
    r"^\s*([A-Z][A-Z0-9_]*(?:TOKEN|SECRET|PASSWORD|API_KEY))"
    r"\s*[:=]\s*[\"']?([^\s\"'#]+)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Finding:
    """A location-only result that never retains a matched secret value."""

    rule: str
    path: str
    line: int


def scan_text(path: str, text: str) -> list[Finding]:
    """Return likely-secret locations without retaining matched values."""
    findings: list[Finding] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if PRIVATE_KEY_PATTERN.search(line):
            findings.append(Finding("private-key", path, line_number))
        if BEARER_PATTERN.search(line):
            findings.append(Finding("bearer-token", path, line_number))
        if ASSIGNMENT_PATTERN.search(line):
            findings.append(Finding("assigned-secret", path, line_number))
    return findings


def scan_repository(root: Path) -> list[Finding]:
    """Scan small UTF-8 files below root while excluding Git metadata."""
    findings: list[Finding] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if ".git" in relative.parts:
            continue
        try:
            if path.stat().st_size > MAX_FILE_BYTES:
                continue
            content = path.read_bytes()
        except OSError:
            continue
        if b"\x00" in content:
            continue
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            continue
        findings.extend(scan_text(relative.as_posix(), text))
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)

    findings = scan_repository(args.root.resolve())
    if not findings:
        print("no likely secrets found")
        return 0

    for finding in findings:
        print(f"{finding.rule}: {finding.path}:{finding.line}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
