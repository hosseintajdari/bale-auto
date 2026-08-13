# Server preparation checklist

## Scope and safety boundary

This checklist prepares the shared Ubuntu host for `bale-auto` without changing
or coupling the existing BaleMed and Bale-Med-Prices projects. The projects must
keep separate repositories, paths, service identities, state, logs, ports, and
secrets.

Owner-confirmed target: `ubuntu@185.204.170.119`. The local `balemed` alias
resolves to that same user and address. Use the explicit destination in
high-risk or cross-project work so the target remains visible.

## Gate 1 — repository and owner approval

- [x] Read `docs/agents/HANDOFF.md` and `docs/agents/NOTION.md`.
- [x] Confirm the local checkout is on `feat/poc-foundation` and matches its
  remote tracking branch.
- [x] Refresh private GitHub PR, issue, and CI state from an authenticated
  connection. Draft Pull Request #1 was open at `14f427b`, and its configured
  CI check passed.
- [x] Obtain explicit owner approval to commit, push, and merge Draft Pull
  Request #1 when CI is green.
- [x] Treat server preparation as a separate owner-approved operation; do not
  infer merge approval.

## Gate 2 — exact-host access

- [x] Record the owner-confirmed destination `ubuntu@185.204.170.119`.
- [x] Confirm the SSH alias resolves to that same IP and user.
- [x] Confirm TCP port 22 accepts a connection on the corrected destination.
- [x] Receive an SSH server banner and complete key authentication.
- [x] Confirm `hostname`, `id`, OS version, current time, and uptime.
- [x] Confirm passwordless `sudo` is available.

The initially supplied `.118` address was a typo. No mutation was attempted on
that address. The corrected `.119` host was authenticated and inspected.

## Gate 3 — read-only shared-host inventory

- [x] Record root filesystem free space and memory availability.
- [x] Inventory direct children of `/opt`, including owner and mode only.
- [x] Verify the exact BaleMed and Bale-Med-Prices paths before touching `/opt`.
- [x] Verify their Git worktrees, active branches, and current commit IDs without
  printing remotes that may embed credentials.
- [x] Inventory related systemd services and running containers.
- [x] Record listening ports without reading environment values or service
  configuration.
- [x] Check Docker, Tailscale, OpenClaw, and `bale-auto` availability and active
  state.
- [x] Confirm `/backup`, 3x-ui, WARP, and all existing BaleMed deployment and
  backup paths remain protected.

Observed: `/opt/bale-bot` is the BaleMed checkout and had six status entries at
post-change verification; these pre-existing local changes were not modified.
`/opt/bale-med-prices` was clean. Docker and `bale-bot.service` were active;
3x-ui remained running. Tailscale and OpenClaw commands were unavailable. Root
storage was 87% used with 2.9 GB available.

## Gate 4 — minimum approved namespace preparation

Only after Gates 2 and 3 pass:

- [x] Reconfirm `/opt/bale-auto` does not already exist or identify its existing
  owner and purpose.
- [x] Create only the reserved application directory:

  ```bash
  sudo install -d -o ubuntu -g ubuntu -m 0750 /opt/bale-auto
  ```

- [x] Verify the result with `stat -c '%A %U:%G %n' /opt/bale-auto`.
- [x] Recheck the protected BaleMed and Bale-Med-Prices paths and services.
- [x] Record that no package, service, firewall rule, port, secret, or project
  checkout was changed.

Rollback for this empty namespace reservation: remove `/opt/bale-auto` only if
it is still empty and its identity has been reverified immediately before the
operation. Directory removal is a separate destructive approval.

## Gate 5 — approved personal PoC deployment

- [x] Select the official stable OpenClaw release `v2026.7.1-2` and pin the
  `ghcr.io/openclaw/openclaw:2026.7.1-2-slim` image.
- [x] Keep the PoC under the existing `ubuntu` operator and isolated
  `/opt/bale-auto` paths; a dedicated system user is deferred.
- [x] Define a gateway reachable only through `127.0.0.1:18789` and an SSH
  tunnel.
- [x] Keep the gateway token in the ignored server `.env` file.
- [x] Define Compose stop/start rollback in `docs/runbooks/OPENCLAW_POC.md`.
- [x] Obtain explicit owner approval for the personal PoC deployment.

Public exposure, Tailscale, reverse proxying, multi-user isolation, extensive
hardening, and production deployment automation are backlog items and do not
block the personal test.

## Completion evidence

Before declaring server preparation complete, attach only non-secret evidence:

- Exact target IP and verified host identity.
- OS, capacity, and availability summary.
- Protected project paths and service-health summary.
- `stat` output for `/opt/bale-auto`.
- Explicit list of what changed and what did not change.
- Verification results and any blocker.
- Next approval gate and rollback boundary.
