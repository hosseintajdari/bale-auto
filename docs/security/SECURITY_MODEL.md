# Security model

## Trust boundary

The PoC has one trusted operator. OpenClaw session routing, presence, and memory
are not treated as authorization boundaries. A future untrusted operator needs
a separate operating-system user, gateway, credentials, and preferably host.

The model is not trusted. Prompt or content injection is expected, so safety is
provided by authentication, a default-deny intent policy, a fixed tool registry,
approval gates, timeouts, redaction, and host isolation.

## Network boundary

- Keep the OpenClaw gateway on loopback.
- Use Tailscale or SSH tunnelling for administrative access.
- Do not bind an administrative service to `0.0.0.0` or place it behind a
  public reverse proxy during the PoC.
- Treat an authenticated gateway caller as a trusted operator.

## Execution boundary

- Accept only registered intents from `policies/intents.json`.
- Deny unknown intents and unsupported policy fields.
- Pass a fixed argument vector to `subprocess`; never use `shell=True`.
- Do not accept commands, scripts, working directories, or environment values
  from user text.
- Keep every check read-only and bounded by a short timeout.

## Secret boundary

Git stores names and documentation, never live values. Development values stay
in ignored local files or an operating-system credential manager. Server values
will later be provided through a root- or service-readable credential location.
GitHub deployment credentials are deferred until a reviewed deployment design.

Tools must never print process environments, secret files, full authorization
headers, or matched secret values. Suspected exposure requires out-of-band
credential rotation.

## Server boundary

`/opt/bale-auto` is reserved for this application. It must not share a checkout,
configuration file, state directory, service unit, or secret with BaleMed or
BaleMedPrices. Service-user and persistent-state paths require a later ADR after
read-only host inspection succeeds.
