# OpenClaw Docker PoC Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deploy and verify a pinned official OpenClaw gateway for the personal bale-auto automation PoC.

**Architecture:** Docker Compose runs one isolated gateway from the official pinned image under `/opt/bale-auto`. The gateway is loopback-only, state and credentials stay outside Git, and the existing fixed health checker provides the first automation test.

**Tech Stack:** Docker Engine, Docker Compose v2, OpenClaw `v2026.7.1-2`, Python 3.12, systemd/Docker restart policy, SSH port forwarding.

## Global Constraints

- Use only `ubuntu@185.204.170.119` and `/opt/bale-auto`.
- Do not modify `/opt/bale-bot`, `/opt/bale-med-prices`, 3x-ui, WARP, or their services.
- Pin `ghcr.io/openclaw/openclaw:2026.7.1-2-slim`; do not deploy a moving tag.
- Bind the gateway host port only to `127.0.0.1:18789`.
- Keep live secrets outside Git and do not print them.
- No public reverse proxy, Tailscale, multi-user support, or production hardening in this PoC.

---

### Task 1: Publish the approved deployment definition

**Files:**
- Create: `deploy/openclaw/compose.yaml`
- Create: `deploy/openclaw/.env.example`
- Create: `docs/runbooks/OPENCLAW_POC.md`
- Modify: `docs/agents/HANDOFF.md`

**Interfaces:**
- Consumes: official OpenClaw image and Docker Compose v2.
- Produces: a reproducible Compose project whose only host listener is `127.0.0.1:18789`.

- [ ] Add a Compose service using the pinned image, restart policy, isolated volumes, and loopback port mapping.
- [ ] Document server-side environment generation without displaying the token.
- [ ] Validate with `docker compose config --quiet`.
- [ ] Run all repository tests, policy validation, secret scan, and whitespace check.
- [ ] Commit and push the branch; merge PR #1 only after CI is green.

### Task 2: Deploy the pinned gateway

**Files:**
- Deploy: `/opt/bale-auto/compose.yaml`
- Create outside Git: `/opt/bale-auto/.env`
- Create outside Git: `/opt/bale-auto/state/`

**Interfaces:**
- Consumes: the reviewed Compose definition from Task 1.
- Produces: a running `bale-auto-openclaw` container on loopback port 18789.

- [ ] Reverify target identity, free disk, existing listeners, and protected project status.
- [ ] Pull the pinned official image and record its immutable digest.
- [ ] Generate a gateway token directly into the server `.env` without printing it.
- [ ] Start the Compose project.
- [x] Verify container state, OpenClaw version, listener binding, and bounded logs.

### Task 3: Validate the personal automation path

**Files:**
- Deploy: `/opt/bale-auto/scripts/health_check.py`
- Deploy: `/opt/bale-auto/policies/intents.json`

**Interfaces:**
- Consumes: `system.health.read` policy and fixed repository health checker.
- Produces: a redacted end-to-end health result and a reachable private gateway UI.

- [ ] Copy only the policy and health-check runtime files from the merged repository.
- [ ] Run the policy validator and health checker on the host.
- [ ] Confirm the gateway HTTP endpoint through `127.0.0.1:18789`.
- [ ] Confirm the SSH tunnel command reaches the private UI.
- [ ] Recheck `bale-bot`, Docker, 3x-ui, and both protected worktrees.

### Task 4: Publish verified operational state

**Files:**
- Modify: `docs/agents/HANDOFF.md`
- Modify: `docs/runbooks/OPENCLAW_POC.md`

**Interfaces:**
- Consumes: fresh server and CI evidence.
- Produces: concise GitHub and Notion status with no secret values.

- [ ] Record image tag/digest, listener, verification, rollback, and any remaining onboarding blocker.
- [ ] Update the relevant GitHub issues and roadmap state.
- [ ] Update the Notion Project page with the stable deployment result and next gate.
- [ ] Fetch GitHub and Notion again to verify the writes.
