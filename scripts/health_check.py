"""Run fixed, read-only host checks and emit a redacted JSON report."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import socket
import subprocess
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Callable


OUTPUT_LIMIT = 4096
BEARER_PATTERN = re.compile(r"(?i)(\bBearer\s+)[^\s]+")
ASSIGNED_SECRET_PATTERN = re.compile(
    r"(?im)(\b[A-Z][A-Z0-9_]*(?:TOKEN|SECRET|PASSWORD|API_KEY)\s*[:=]\s*)"
    r"[^\s]+"
)


@dataclass(frozen=True)
class CheckSpec:
    """A registered command with a short execution limit."""

    name: str
    argv: tuple[str, ...]
    timeout_seconds: float = 5.0


@dataclass(frozen=True)
class CheckResult:
    """A bounded, redacted command result."""

    name: str
    status: str
    exit_code: int | None
    stdout: str
    stderr: str
    duration_ms: int = 0


Runner = Callable[[CheckSpec], CheckResult]


REGISTERED_CHECKS = (
    CheckSpec("operating_system", ("uname", "-srmo")),
    CheckSpec("tailscale_version", ("tailscale", "version")),
    CheckSpec("tailscale_status", ("tailscale", "status", "--peers=false")),
    CheckSpec(
        "docker_version",
        ("docker", "version", "--format", "{{.Server.Version}}"),
    ),
    CheckSpec(
        "docker_containers",
        ("docker", "ps", "--format", "{{.Names}}|{{.Image}}|{{.Status}}"),
    ),
    CheckSpec("openclaw_version", ("openclaw", "--version")),
    CheckSpec("tailscaled_service", ("systemctl", "is-active", "tailscaled")),
    CheckSpec("docker_service", ("systemctl", "is-active", "docker")),
    CheckSpec("openclaw_service", ("systemctl", "is-active", "openclaw")),
)


def redact(text: str) -> str:
    """Remove common bearer and assigned-secret values from text."""
    text = BEARER_PATTERN.sub(r"\1[REDACTED]", text)
    return ASSIGNED_SECRET_PATTERN.sub(r"\1[REDACTED]", text)


def _bounded(text: str | bytes | None) -> str:
    if text is None:
        return ""
    if isinstance(text, bytes):
        text = text.decode("utf-8", errors="replace")
    return redact(text)[:OUTPUT_LIMIT]


def run_check(spec: CheckSpec) -> CheckResult:
    """Run one fixed argument vector without a shell."""
    started = time.monotonic()
    executable = spec.argv[0]
    if shutil.which(executable) is None:
        return CheckResult(
            spec.name,
            "unavailable",
            None,
            "",
            f"{executable} is not installed or not on PATH",
        )

    try:
        completed = subprocess.run(
            spec.argv,
            shell=False,
            capture_output=True,
            text=True,
            timeout=spec.timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        duration_ms = int((time.monotonic() - started) * 1000)
        return CheckResult(
            spec.name,
            "timeout",
            None,
            _bounded(exc.stdout),
            _bounded(exc.stderr),
            duration_ms,
        )
    except OSError as exc:
        duration_ms = int((time.monotonic() - started) * 1000)
        return CheckResult(spec.name, "unavailable", None, "", str(exc), duration_ms)

    duration_ms = int((time.monotonic() - started) * 1000)
    status = "ok" if completed.returncode == 0 else "degraded"
    return CheckResult(
        spec.name,
        status,
        completed.returncode,
        _bounded(completed.stdout),
        _bounded(completed.stderr),
        duration_ms,
    )


def build_report(run: Runner = run_check) -> dict[str, object]:
    """Build a versioned report from only the registered check list."""
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "hostname": socket.gethostname(),
        "checks": [asdict(run(spec)) for spec in REGISTERED_CHECKS],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)
    indent = 2 if args.pretty else None
    print(json.dumps(build_report(), ensure_ascii=False, indent=indent, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
