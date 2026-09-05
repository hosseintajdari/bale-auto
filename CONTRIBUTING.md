# Contributing

Thanks for helping with the Conversational Work Ledger.

## Scope

This repository currently contains a synthetic, in-memory P0 proof. Keep tests
synthetic and preserve the product contract: explicit confirmation before every
durable write, explicit rial/toman units, user/conversation ownership, and
idempotent retries. Do not add real financial messages, credentials, service
configuration, or generated `work/` evidence.

P0 is not a production integration. Do not introduce a live channel, model,
database, outbound reminder, or P1 behavior without an explicit product and
implementation decision recorded in the handoff and PRD.

## Before opening a pull request

Run the standard-library checks from the repository root:

```bash
python3 -m unittest discover -s tests -v
python3 run_p0_review.py
git diff --check
```

Explain behavioral changes, update relevant documentation, and include tests
for contract changes. Keep commits focused and do not rewrite `main` history.

## Review expectations

Changes affecting confirmation, ownership, deletion, retention, parsing, or
synthetic-data boundaries require explicit discussion in the pull request.
Security concerns should follow `SECURITY.md` rather than being disclosed in a
public issue.
