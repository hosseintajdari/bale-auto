import sys
import unittest

from scripts.health_check import (
    REGISTERED_CHECKS,
    CheckResult,
    CheckSpec,
    build_report,
    redact,
    run_check,
)


class HealthCheckTests(unittest.TestCase):
    def test_redacts_bearer_tokens_and_secret_assignments(self):
        bearer = "Bearer " + "abc123-secret"
        key = "API_" + "TOKEN"
        text = f"Authorization: {bearer}\n{key}=abc123-secret"
        redacted = redact(text)
        self.assertNotIn("abc123-secret", redacted)
        self.assertIn("[REDACTED]", redacted)

    def test_report_uses_only_registered_checks(self):
        seen = []

        def fake_run(spec):
            seen.append(spec.argv)
            return CheckResult(spec.name, "ok", 0, "ready", "")

        report = build_report(fake_run)
        self.assertEqual(report["schema_version"], 1)
        self.assertTrue(seen)
        self.assertNotIn("shell", report)

    def test_registered_checks_match_the_docker_openclaw_deployment(self):
        checks = {spec.name: spec.argv for spec in REGISTERED_CHECKS}

        self.assertEqual(
            checks["openclaw_container"],
            (
                "docker",
                "inspect",
                "--format",
                "{{.Config.Image}}|{{.State.Status}}|"
                "{{if .State.Health}}{{.State.Health.Status}}{{end}}",
                "bale-auto-openclaw",
            ),
        )
        self.assertEqual(
            checks["openclaw_gateway_health"],
            (
                "curl",
                "--fail",
                "--silent",
                "--show-error",
                "--max-time",
                "3",
                "http://127.0.0.1:18789/healthz",
            ),
        )
        self.assertNotIn("openclaw_version", checks)
        self.assertNotIn("openclaw_service", checks)

    def test_missing_optional_tool_is_reported_not_raised(self):
        spec = CheckSpec("missing", ("bale-auto-command-that-does-not-exist",))
        result = run_check(spec)
        self.assertEqual(result.status, "unavailable")
        self.assertIsNone(result.exit_code)

    def test_timeout_is_reported_not_raised(self):
        spec = CheckSpec(
            "timeout",
            (sys.executable, "-c", "import time; time.sleep(0.2)"),
            timeout_seconds=0.01,
        )
        result = run_check(spec)
        self.assertEqual(result.status, "timeout")


if __name__ == "__main__":
    unittest.main()
