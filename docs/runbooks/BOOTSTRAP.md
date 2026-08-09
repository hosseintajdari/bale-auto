# Bootstrap runbook

## Purpose

This runbook establishes the repository quality gate and describes the safe
boundary for later server work. It does not install or start OpenClaw.

## Local setup

1. Install Python 3.12 or newer.
2. Check out a topic branch.
3. Keep live values outside the repository; `.env.example` is names-only.
4. Run the commands listed in the README.
5. Open a pull request and attach the verification output without secret values.

## CI interpretation

The `test-and-validate` job compiles Python, runs unit tests, validates the
default-deny policy, scans for likely secrets, and checks whitespace. A failed
step blocks merge until the cause is understood and fixed.

CI does not connect to the server, hold an SSH key, install a package, or deploy
a service in the foundation phase.

## Server namespace

Reserve `/opt/bale-auto` for application releases. Do not place this checkout in
`/opt/bale-bot` and do not reuse another project's user, unit, state, log, or
credential file.

Before creating the path, authenticate with a dedicated SSH key and run the
read-only health checker. Record existing owners and modes under `/opt` without
printing configuration contents or environment values.

The initial path creation, when separately approved and authenticated, is:

```bash
sudo install -d -o ubuntu -g ubuntu -m 0750 /opt/bale-auto
```

This reserves an application checkout path only. A dedicated service user and
the `/etc/bale-auto`, `/var/lib/bale-auto`, and `/var/log/bale-auto` paths require
a later architecture decision before creation.

## Safe inspection

The repository health checker may report command versions, service active state,
and running container names. It must not print environments, service logs,
OpenClaw configuration, token files, or private keys.

## Failure and rollback boundary

Repository changes are reverted through Git commits. No server rollback is
needed for this foundation pull request because it performs no deployment. A
future deployment runbook must record the previous immutable release before it
may change the active release.
