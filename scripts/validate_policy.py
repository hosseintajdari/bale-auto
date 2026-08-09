"""Validate the bale-auto intent policy."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

TOP_LEVEL_FIELDS = frozenset({"version", "default", "intents"})
INTENT_FIELDS = frozenset(
    {"risk", "approval", "executor", "timeout_seconds", "read_only"}
)
HEALTH_INTENT = "system.health.read"


def validate_policy(document: object) -> list[str]:
    """Return deterministic validation errors for an intent policy."""
    if not isinstance(document, dict):
        return ["policy must be an object"]

    errors: list[str] = []

    for field in sorted(set(document) - TOP_LEVEL_FIELDS):
        errors.append(f"unsupported top-level field: {field}")

    if document.get("version") != 1:
        errors.append("version must be 1")
    if document.get("default") != "deny":
        errors.append("default must be deny")

    intents = document.get("intents")
    if not isinstance(intents, dict):
        errors.append("intents must be an object")
        return errors

    if set(intents) != {HEALTH_INTENT}:
        for name in sorted(set(intents) - {HEALTH_INTENT}):
            errors.append(f"unsupported intent: {name}")
        if HEALTH_INTENT not in intents:
            errors.append(f"required intent missing: {HEALTH_INTENT}")
        return errors

    health = intents[HEALTH_INTENT]
    if not isinstance(health, dict):
        errors.append(f"intent {HEALTH_INTENT} must be an object")
        return errors

    for field in sorted(set(health) - INTENT_FIELDS):
        errors.append(f"unsupported field: {field}")

    if health.get("risk") != "low":
        errors.append("risk must be low")
    if health.get("approval") != "not_required":
        errors.append("approval must be not_required")
    if health.get("executor") != "health_check":
        errors.append("executor must be health_check")

    timeout = health.get("timeout_seconds")
    if type(timeout) is not int or not 1 <= timeout <= 30:
        errors.append("timeout_seconds must be an integer from 1 through 30")
    if health.get("read_only") is not True:
        errors.append("read_only must be true")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("policy", type=Path)
    args = parser.parse_args(argv)

    try:
        document = json.loads(args.policy.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"policy unreadable: {exc}")
        return 2

    errors = validate_policy(document)
    if errors:
        for error in errors:
            print(error)
        return 1

    print("policy valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
