# OpenClaw Docker PoC Design

## Decision

Run the official OpenClaw container on the existing Ubuntu host as the fastest
reversible path to a working personal automation test. This is an integration
and deployment task, not a redesign or security audit of OpenClaw.

## Selected release and source

- Upstream: `openclaw/openclaw`
- Stable release: `v2026.7.1-2`
- Container: `ghcr.io/openclaw/openclaw:2026.7.1-2-slim`
- Host: `ubuntu@185.204.170.119`
- Project root: `/opt/bale-auto`

The version is pinned so a restart does not silently adopt a different image.

## Runtime design

Docker Compose owns one OpenClaw gateway container and its persistent state.
The gateway publishes only to `127.0.0.1:18789` on the host. The operator opens
the UI through an SSH tunnel. A generated gateway token lives only in the
server-side ignored environment file and is never committed or printed.

The deployment does not reuse a BaleMed checkout, service, state directory,
credential, or port. Existing `/opt/bale-bot`, `/opt/bale-med-prices`, 3x-ui,
WARP, and their services remain outside its lifecycle.

## Data flow

1. The operator connects through SSH port forwarding.
2. The browser reaches the loopback-only OpenClaw gateway.
3. OpenClaw uses its isolated state under `/opt/bale-auto`.
4. The PoC health intent invokes only the repository's fixed health checker.
5. The result is redacted before it is returned or recorded.

## Failure and rollback

If the gateway fails, capture container status and bounded logs, then stop the
Compose project. Rollback is `docker compose down` while retaining state. A
full reset additionally removes only the bale-auto state after an explicit
identity check; it never deletes shared Docker data or another project path.

## Success criteria

- The pinned official image is pulled and its identity recorded.
- The gateway starts and remains healthy or reports a concrete configuration
  blocker.
- Host port `18789` listens only on `127.0.0.1`.
- The UI is reachable through an SSH tunnel.
- OpenClaw version/status commands succeed.
- The `system.health.read` PoC path returns a redacted read-only report.
- Existing BaleMed services and worktrees retain their pre-deployment state.

## Deferred work

Public exposure, multi-user isolation, Tailscale, reverse proxying, extensive
hardening, HA, centralized observability, and automated production deployment
are backlog items. They do not block this personal PoC.
