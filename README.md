# bale-auto

`bale-auto` is a personal, auditable automation lab for learning how to build
safe delivery pipelines around OpenClaw. The first proof of concept accepts a
small Persian health-status request, maps it to the fixed
`system.health.read` intent, evaluates a default-deny policy, runs a registered
read-only health check, and returns a redacted audit result.

The project is operationally independent from BaleMed and BaleMedPrices. The
server may host multiple projects, but `bale-auto` has its own repository,
runtime path, policies, service identity, state, and secrets.

## PoC scope

- Repository documentation and pull-request quality gates.
- A machine-readable, default-deny intent policy.
- A non-destructive health check for Tailscale, Docker, OpenClaw, and systemd.
- Baseline detection of likely secrets without printing their values.
- Manual, approval-gated deployment after server inspection.

The PoC does not provide arbitrary shell access, public OpenClaw exposure,
payments, deletion, firewall changes, multi-tenant isolation, or medical logic.

## Repository layout

- `docs/` contains the PRD mirror, security model, runbooks, and plans.
- `docs/agents/` contains the version-controlled agent handoff and Notion
  publication rules.
- `docs/runbooks/SERVER_PREPARATION_CHECKLIST.md` records the exact-host,
  shared-server preparation gates and non-destructive verification evidence.
- `deploy/openclaw/` contains the pinned personal-PoC Compose definition; its
  live `.env` and state exist only on the server.
- `policies/` contains the executable intent allowlist.
- `scripts/` contains deterministic validators and read-only diagnostics.
- `tests/` covers policy, redaction, scanning, and failure-safe behavior.
- `.github/` contains pull-request checks and review guidance.

## Local verification

Use Python 3.12 or newer. Runtime tools use only the Python standard library;
development linting uses Ruff 0.16.2.

```powershell
python -m pip install ruff==0.16.2
ruff check scripts tests
python -m compileall -q scripts tests
python -m unittest discover -s tests -v
python scripts/validate_policy.py policies/intents.json
python scripts/scan_secrets.py .
python scripts/health_check.py --pretty
```

Linux-only checks appear as `unavailable` when the health check is run on
Windows. That is an expected, structured result rather than an error.

## Delivery flow

Create a topic branch, run the local gate, open a pull request, wait for CI,
review the risk and rollback notes, then merge. Server deployment is a separate
manual approval step and is not part of the foundation pull request.

The reserved server application path is `/opt/bale-auto`. Do not use
`/opt/bale-bot` or another project's directory.

## Product source of truth

The approved PRD lives in
[Notion](https://app.notion.com/p/3b7834f066298137a6e6fec4244fe141).
The repository keeps a concise mirror at [docs/product/PRD.md](docs/product/PRD.md).
