# Bale Auto PoC Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish a secure, testable repository foundation for `bale-auto`, including default-deny intent policy, secret-safe read-only health checks, and pull-request CI.

**Architecture:** This first pull request is deliberately deployment-free. Python 3.12 standard-library tools validate repository policy, scan tracked text for obvious secrets, and run a fixed-command Linux health check without accepting shell input. GitHub Actions runs the same tests and validators used locally; server provisioning and OpenClaw installation remain separate, manually approved phases.

**Tech Stack:** Python 3.12 standard library, JSON policy files, Markdown documentation, GitHub Actions, Linux system utilities.

## Global Constraints

- Keep `bale-auto` operationally independent from `BaleMed` and `BaleMedPrices`.
- Do not expose OpenClaw or an administrative interface directly to the public internet.
- Do not provide arbitrary shell execution or interpolate user input into a shell command.
- Do not store tokens, passwords, private keys, or live environment values in Git, Notion, tests, or logs.
- Treat unknown intents as denied.
- Keep server inspection read-only until a separate deployment plan is approved.
- Copy or adapt code only from sources with a clear compatible license and record provenance in `THIRD_PARTY_NOTICES.md`.
- Pin third-party GitHub Actions to immutable commit SHAs.
- Reserve `/opt/bale-auto` as the project-specific server application path; do not reuse `/opt/bale-bot` or any BaleMed path.

---

## Planned File Map

- `README.md`: project purpose, safety boundary, local verification, and contribution flow.
- `.gitignore`: local secrets, caches, reports, and editor artifacts that must never be committed.
- `.env.example`: variable names and safe descriptions only; every value remains empty.
- `THIRD_PARTY_NOTICES.md`: reviewed reference repositories, licenses, versions, and reuse decisions.
- `docs/product/PRD.md`: reviewed Notion PRD mirror and source link.
- `docs/security/SECURITY_MODEL.md`: one-operator trust model, default-deny policy, secret boundary, and network boundary.
- `docs/runbooks/BOOTSTRAP.md`: local setup, CI interpretation, server path, inspection, and rollback-oriented operational guidance.
- `policies/intents.json`: machine-readable allowlist for the single PoC intent.
- `scripts/validate_policy.py`: strict policy schema and invariant validator.
- `scripts/scan_secrets.py`: conservative tracked-file secret scanner with explicit exclusions.
- `scripts/health_check.py`: fixed-command, read-only Linux health report with redaction.
- `tests/test_validate_policy.py`: policy validator behavior and default-deny invariants.
- `tests/test_scan_secrets.py`: scanner detection, safe-example, and exclusion behavior.
- `tests/test_health_check.py`: command allowlist, timeout, missing-tool, redaction, and report behavior.
- `.github/workflows/ci.yml`: pinned, least-privilege pull-request and push checks.
- `.github/pull_request_template.md`: change, risk, verification, secrets, and rollback checklist.

---

### Task 1: Repository Contract and Product Documentation

**Files:**
- Modify: `README.md`
- Create: `.gitignore`
- Create: `.env.example`
- Create: `THIRD_PARTY_NOTICES.md`
- Create: `docs/product/PRD.md`
- Create: `docs/security/SECURITY_MODEL.md`
- Create: `docs/runbooks/BOOTSTRAP.md`

**Interfaces:**
- Consumes: the approved Notion PRD and repository/reuse inspection findings.
- Produces: documented repository boundaries and exact local verification commands used by later tasks.

- [ ] **Step 1: Replace the existing one-line README**

Document the project purpose, PoC scope, non-goals, repository layout, fixed health intent, local command `python -m unittest discover -s tests -v`, and the branch-to-PR workflow. State that `/opt/bale-auto` is reserved for this project and that no deployment occurs in this pull request.

- [ ] **Step 2: Add ignore and environment contracts**

Ignore `.env`, `.env.*` except `.env.example`, `__pycache__/`, `*.pyc`, `.pytest_cache/`, `.coverage`, `coverage.xml`, `reports/`, `.venv/`, `venv/`, IDE files, and local SSH material. Define empty variables `BALE_AUTO_LOG_LEVEL`, `BALE_AUTO_STATE_DIR`, and `OPENCLAW_CONFIG_PATH` with comments that values are supplied outside Git.

- [ ] **Step 3: Mirror the approved PRD and security boundary**

Create a concise repository mirror that links to the approved Notion page, identifies Notion as the product source of truth, and preserves the accepted scope and criteria. Describe OpenClaw's one-operator trust boundary, loopback-only gateway, Tailscale/SSH remote access, fixed tools, default deny, and secret redaction.

- [ ] **Step 4: Record reuse and license decisions**

Record `openclaw/openclaw`, `openclaw/openclaw-ansible`, and `pandysp/openclaw-infra` as MIT-licensed references. Record `redhat-et/openclaw-infra` and `matskevich/openclaw-infra` as idea-only references because no license file was found during review. State that this pull request copies no third-party source code.

- [ ] **Step 5: Verify documentation mechanically**

Run: `git diff --check`

Expected: exit code 0 with no whitespace errors.

- [ ] **Step 6: Commit the documentation contract**

```bash
git add README.md .gitignore .env.example THIRD_PARTY_NOTICES.md docs
git commit -m "docs: define secure poc foundation"
```

---

### Task 2: Default-Deny Intent Policy

**Files:**
- Create: `policies/intents.json`
- Create: `scripts/validate_policy.py`
- Create: `tests/test_validate_policy.py`

**Interfaces:**
- Consumes: JSON object loaded from a policy path.
- Produces: `validate_policy(document: object) -> list[str]` and CLI exit code 0 only for a valid policy.

- [ ] **Step 1: Write failing policy tests**

```python
import unittest

from scripts.validate_policy import validate_policy


def valid_policy():
    return {
        "version": 1,
        "default": "deny",
        "intents": {
            "system.health.read": {
                "risk": "low",
                "approval": "not_required",
                "executor": "health_check",
                "timeout_seconds": 10,
                "read_only": True,
            }
        },
    }


class PolicyValidationTests(unittest.TestCase):
    def test_accepts_the_single_read_only_health_intent(self):
        self.assertEqual(validate_policy(valid_policy()), [])

    def test_rejects_a_policy_without_default_deny(self):
        policy = valid_policy()
        policy["default"] = "allow"
        self.assertIn("default must be deny", validate_policy(policy))

    def test_rejects_shell_or_command_fields(self):
        policy = valid_policy()
        policy["intents"]["system.health.read"]["command"] = "uname -a"
        self.assertIn("unsupported field: command", validate_policy(policy))
```

- [ ] **Step 2: Run tests and confirm the expected failure**

Run: `python -m unittest tests.test_validate_policy -v`

Expected: import failure because `scripts.validate_policy` does not exist.

- [ ] **Step 3: Implement the minimal validator**

Implement exact top-level keys `version`, `default`, and `intents`; require version 1 and default `deny`; accept only the intent `system.health.read`; accept only fields `risk`, `approval`, `executor`, `timeout_seconds`, and `read_only`; require the exact executor `health_check`, integer timeout from 1 through 30, and `read_only` set to true. Return deterministic human-readable errors instead of raising for invalid policy input.

- [ ] **Step 4: Add the valid policy document**

Create `policies/intents.json` matching `valid_policy()` exactly.

- [ ] **Step 5: Run focused and full tests**

Run: `python -m unittest tests.test_validate_policy -v`

Expected: all policy tests pass.

Run: `python scripts/validate_policy.py policies/intents.json`

Expected: exit code 0 and `policy valid`.

- [ ] **Step 6: Commit the default-deny policy**

```bash
git add policies scripts/validate_policy.py tests/test_validate_policy.py
git commit -m "feat: add default-deny intent policy"
```

---

### Task 3: Secret-Safe Repository Scanner

**Files:**
- Create: `scripts/scan_secrets.py`
- Create: `tests/test_scan_secrets.py`

**Interfaces:**
- Consumes: repository root path and text file contents.
- Produces: `scan_text(path: str, text: str) -> list[Finding]`, `scan_repository(root: Path) -> list[Finding]`, and a nonzero CLI exit code when a likely live secret is found.

- [ ] **Step 1: Write failing scanner tests**

```python
import unittest

from scripts.scan_secrets import scan_text


class SecretScannerTests(unittest.TestCase):
    def test_detects_a_private_key_header(self):
        header = "-" * 5 + "BEGIN PRIVATE KEY" + "-" * 5
        findings = scan_text("bad.pem", header)
        self.assertEqual(findings[0].rule, "private-key")

    def test_detects_a_token_assignment_with_a_value(self):
        key = "TELEGRAM_BOT_" + "TOKEN"
        findings = scan_text("bad.env", f"{key}=live-" + "secret-value")
        self.assertEqual(findings[0].rule, "assigned-secret")

    def test_allows_empty_values_in_env_example(self):
        self.assertEqual(scan_text(".env.example", "TELEGRAM_BOT_TOKEN="), [])
```

- [ ] **Step 2: Run tests and confirm the expected failure**

Run: `python -m unittest tests.test_scan_secrets -v`

Expected: import failure because `scripts.scan_secrets` does not exist.

- [ ] **Step 3: Implement conservative scanning**

Use standard-library regular expressions to detect private-key headers, bearer tokens, and nonempty assignments whose key ends in `TOKEN`, `SECRET`, `PASSWORD`, or `API_KEY`. Skip `.git`, binary files, and files larger than 1 MiB. Never print the matched value; report only rule, relative path, and line number.

- [ ] **Step 4: Run focused and repository scans**

Run: `python -m unittest tests.test_scan_secrets -v`

Expected: all scanner tests pass.

Run: `python scripts/scan_secrets.py .`

Expected: exit code 0 and `no likely secrets found`.

- [ ] **Step 5: Commit the secret guardrail**

```bash
git add scripts/scan_secrets.py tests/test_scan_secrets.py
git commit -m "feat: add baseline secret scanner"
```

---

### Task 4: Non-Destructive Health Check

**Files:**
- Create: `scripts/health_check.py`
- Create: `tests/test_health_check.py`

**Interfaces:**
- Consumes: fixed `CheckSpec` values and an injectable command runner for tests.
- Produces: `run_check(spec: CheckSpec) -> CheckResult`, `build_report(run: Runner) -> dict[str, object]`, redacted JSON on stdout, and exit code 0 when the report was generated even if optional tools are absent.

- [ ] **Step 1: Write failing health-check tests**

```python
import unittest

from scripts.health_check import CheckResult, build_report, redact


class HealthCheckTests(unittest.TestCase):
    def test_redacts_bearer_tokens_and_secret_assignments(self):
        bearer = "Bearer " + "abc123"
        key = "API_" + "TOKEN"
        text = f"Authorization: {bearer}\n{key}=abc123"
        self.assertNotIn("abc123", redact(text))

    def test_report_uses_only_registered_checks(self):
        seen = []

        def fake_run(spec):
            seen.append(spec.argv)
            return CheckResult(spec.name, "ok", 0, "ready", "")

        report = build_report(fake_run)
        self.assertEqual(report["schema_version"], 1)
        self.assertTrue(seen)
        self.assertNotIn("shell", report)

    def test_missing_optional_tool_is_reported_not_raised(self):
        def missing_run(spec):
            return CheckResult(spec.name, "unavailable", None, "", "not installed")

        report = build_report(missing_run)
        self.assertTrue(all(item["status"] == "unavailable" for item in report["checks"]))
```

- [ ] **Step 2: Run tests and confirm the expected failure**

Run: `python -m unittest tests.test_health_check -v`

Expected: import failure because `scripts.health_check` does not exist.

- [ ] **Step 3: Implement fixed command execution**

Define immutable checks for operating-system identity, `tailscale version`, `tailscale status --peers=false`, `docker version`, `docker ps`, `openclaw --version`, `systemctl is-active tailscaled`, `systemctl is-active docker`, and `systemctl is-active openclaw`. Execute with `subprocess.run(argv, shell=False, capture_output=True, text=True, timeout=spec.timeout_seconds, check=False)`. Treat missing executables and timeouts as structured statuses. Never read environment values, service logs, OpenClaw configuration, or secret files.

- [ ] **Step 4: Add deterministic JSON and redaction**

Emit schema version, UTC timestamp, hostname, and check results. Limit each output stream to 4096 characters. Redact bearer tokens and assignments ending in `TOKEN`, `SECRET`, `PASSWORD`, or `API_KEY`. Keep stderr separate and never include a process environment dump.

- [ ] **Step 5: Run focused and full tests**

Run: `python -m unittest tests.test_health_check -v`

Expected: all health-check tests pass.

Run: `python scripts/health_check.py --pretty`

Expected on Windows: valid JSON with unavailable Linux-only checks and no traceback.

- [ ] **Step 6: Commit the health check**

```bash
git add scripts/health_check.py tests/test_health_check.py
git commit -m "feat: add read-only health check"
```

---

### Task 5: Pull-Request CI and Review Gate

**Files:**
- Create: `.github/workflows/ci.yml`
- Create: `.github/pull_request_template.md`
- Create: `pyproject.toml`

**Interfaces:**
- Consumes: repository contents on pull request and push.
- Produces: required `test-and-validate` job with no write permissions and the same verification results as local commands.

- [ ] **Step 1: Create least-privilege CI**

Use `permissions: contents: read`, set `timeout-minutes: 10`, and run on pull requests plus pushes to `main`. Pin checkout to `actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1`, setup-python to `actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97`, and ruff-action to `astral-sh/ruff-action@278981a28ce3188b1e39527901f38254bf3aac89`. Configure Python `3.12` and Ruff `0.16.2`.

- [ ] **Step 2: Run all deterministic checks in CI**

Run these commands in separate named steps:

```bash
ruff check scripts tests
python -m compileall -q scripts tests
python -m unittest discover -s tests -v
python scripts/validate_policy.py policies/intents.json
python scripts/scan_secrets.py .
git diff --check origin/main...HEAD
```

For the initial branch where `HEAD^` exists, whitespace validation must pass. Do not add a deployment job, SSH key, environment secret, or privileged permission.

- [ ] **Step 3: Add the pull-request checklist**

Require summary, scope, risk, verification evidence, secret review, server-effect declaration, and rollback notes. Include an explicit checkbox confirming no BaleMed path or resource is touched.

- [ ] **Step 4: Validate workflow syntax and repository checks**

Run: `python -c "import pathlib; text=pathlib.Path('.github/workflows/ci.yml').read_text(); assert 'permissions:' in text and 'contents: read' in text and 'pull_request:' in text"`

Expected: exit code 0.

Run: `python -m unittest discover -s tests -v`

Expected: all tests pass.

Run: `python scripts/validate_policy.py policies/intents.json`

Expected: exit code 0.

Run: `python scripts/scan_secrets.py .`

Expected: exit code 0.

- [ ] **Step 5: Commit CI and review policy**

```bash
git add .github
git commit -m "ci: add pull-request validation"
```

---

### Task 6: Final Verification and Pull-Request Preparation

**Files:**
- Modify: `docs/runbooks/BOOTSTRAP.md` only if verification reveals an inaccurate command.

**Interfaces:**
- Consumes: the complete branch.
- Produces: clean verification evidence and a draft pull-request description.

- [ ] **Step 1: Run the complete local gate**

Run: `ruff check scripts tests`

Expected: `All checks passed!`.

Run: `python -m compileall -q scripts tests`

Expected: exit code 0.

Run: `python -m unittest discover -s tests -v`

Expected: all tests pass with no warnings or tracebacks.

Run: `python scripts/validate_policy.py policies/intents.json`

Expected: `policy valid`.

Run: `python scripts/scan_secrets.py .`

Expected: `no likely secrets found`.

Run: `python scripts/health_check.py --pretty`

Expected: valid redacted JSON; missing Linux tools are represented as unavailable.

Run: `git diff main...HEAD --check`

Expected: exit code 0.

- [ ] **Step 2: Inspect the exact branch scope**

Run: `git status --short --branch`

Expected: branch `feat/poc-foundation` and no uncommitted files.

Run: `git diff --stat main...HEAD`

Expected: only the files listed in this plan.

- [ ] **Step 3: Prepare the pull-request summary**

Describe repository foundation, default-deny policy, secret guardrail, read-only health check, CI, tests, server auth blocker, and the explicit statement that no server or BaleMed resource changed.

---

## Deferred to Separate Plans

- Creating `/opt/bale-auto` on the server after SSH key authentication succeeds.
- Inspecting and pinning the installed or selected OpenClaw version.
- Selecting a dedicated service user and the `/etc`, `/var/lib`, and `/var/log` layout.
- Running Ansible in check mode and reviewing every proposed system change.
- Installing or starting OpenClaw, Docker, Tailscale, or systemd units.
- Adding Telegram, ChatGPT, iPhone Shortcuts, webhooks, or public endpoints.
- Creating a deployment workflow or storing deployment credentials in GitHub.
