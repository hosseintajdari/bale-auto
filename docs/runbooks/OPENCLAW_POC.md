# OpenClaw personal PoC runbook

## Deployment

The PoC uses the official pinned image
`ghcr.io/openclaw/openclaw:2026.7.1-2-slim`. It runs only from
`/opt/bale-auto` and publishes the gateway at `127.0.0.1:18789`.

On the server, copy `deploy/openclaw/compose.yaml` to
`/opt/bale-auto/compose.yaml`, create `state` and `auth-profile-secrets`, and
generate the ignored environment file without printing its value:

```bash
cd /opt/bale-auto
install -d -m 0700 state auth-profile-secrets
umask 077
printf 'OPENCLAW_GATEWAY_TOKEN=%s\n' "$(openssl rand -hex 32)" > .env
docker compose config --quiet
```

Initialize the minimum local gateway configuration before first start:

```bash
docker compose run --rm --no-deps --entrypoint node openclaw-gateway \
  dist/index.js config set --batch-json \
  '[{"path":"gateway.mode","value":"local"},{"path":"gateway.bind","value":"lan"},{"path":"gateway.auth.mode","value":"token"},{"path":"gateway.auth.token","value":{"source":"env","provider":"default","id":"OPENCLAW_GATEWAY_TOKEN"}},{"path":"gateway.controlUi.allowedOrigins","value":["http://localhost:18789","http://127.0.0.1:18789"]}]'
docker compose up -d openclaw-gateway
```

## Verification

```bash
docker compose ps
docker compose exec -T openclaw-gateway node dist/index.js --version
docker compose exec -T openclaw-gateway node dist/index.js gateway status --require-rpc
curl --fail --silent --show-error http://127.0.0.1:18789/healthz
ss -lnt '( sport = :18789 )'
```

From Windows, keep this tunnel open:

```powershell
ssh -N -L 18789:127.0.0.1:18789 ubuntu@185.204.170.119
```

Then open `http://127.0.0.1:18789/`. Configure model authentication through
the OpenClaw onboarding UI; do not paste provider credentials into Git, Notion,
GitHub issues, or command output.

## Health-intent test

The repository policy and fixed checker can be copied under `/opt/bale-auto`
and run with:

```bash
python3 scripts/validate_policy.py policies/intents.json
python3 scripts/health_check.py --pretty
```

## Stop and rollback

Stop the PoC while retaining state:

```bash
cd /opt/bale-auto
docker compose down
```

Re-enable it with `docker compose up -d openclaw-gateway`. Do not remove
`state`, `auth-profile-secrets`, or `.env` unless a full reset is intended.
