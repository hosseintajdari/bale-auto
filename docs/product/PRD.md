# Product requirements: bale-auto

The approved, authoritative PRD is stored in
[Notion](https://app.notion.com/p/3b7834f066298137a6e6fec4244fe141).
This file is a concise repository mirror for implementation work.

## Outcome

Build a personal automation lab where a controlled Persian request is mapped to
a registered intent, evaluated by a default-deny policy, executed through a
fixed low-risk tool, and recorded as a redacted audit result.

The primary value is hands-on learning about repositories, CI, deployment,
secrets, observability, trust boundaries, and reversible automation. Commercial
or revenue goals are not required.

## First end-to-end scenario

A Persian health-status request maps to `system.health.read`. The policy marks
that intent low-risk, read-only, and pre-approved. The executor can invoke only
the registered health checker. Unknown intents and extra command fields fail
closed.

## Acceptance criteria

- Pull requests run deterministic tests, policy validation, and secret scanning.
- Inspection reports Tailscale, Docker, OpenClaw, and systemd availability
  without changing the host or reading secret material.
- User input is never interpolated into a shell command.
- Administrative access remains private through Tailscale or SSH, while the
  OpenClaw gateway remains loopback-only.
- No real secret is present in Git, Notion, tests, or logs.
- The repository, path, service identity, state, and secrets remain independent
  from BaleMed and BaleMedPrices.

## Delivery phases

1. Establish the repository contract and CI.
2. Validate the server without mutation.
3. Review a pinned deployment plan in check mode.
4. Perform an explicitly approved manual deployment.
5. Verify the health-intent path and preserve evidence.
