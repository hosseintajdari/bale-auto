# Security policy

## Current status

This project is a synthetic, in-memory P0 prototype and is not ready for real
financial data or production deployment. Do not send secrets, private
transcripts, bank messages, credentials, or customer data to the repository,
issues, pull requests, tests, or CI logs.

## Reporting a vulnerability

Please do not open a public issue for a suspected security vulnerability.
Contact the repository owner privately through the GitHub account that owns
this repository, including:

- a concise description and impact;
- affected file, commit, or workflow;
- minimal reproduction steps using synthetic data only; and
- any suggested mitigation.

Do not include secrets or real personal/financial information. If private
contact is unavailable, stop at a local report and ask the owner to provide a
secure reporting channel.

## Security expectations

Contributors must preserve explicit confirmation before durable writes, source
purge after draft resolution, ownership isolation, idempotency, and read-only
CI permissions. Never bypass GitHub host-key checks or commit authentication
material.
