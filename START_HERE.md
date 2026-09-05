# Conversational Work Ledger — transfer package

## Purpose

This package is the portable design and P0 handoff for the Conversational Work
Ledger. It is intentionally independent of the historical `bale-auto`
OpenClaw PoC. It contains no secrets, SSH configuration, Git history, customer
data, model credentials, server configuration, or production code.

## Read in order

1. `docs/agents/HANDOFF.md`
2. `docs/agents/README.md`
3. `docs/product/CONVERSATIONAL_WORK_LEDGER_PRD.md`
4. `docs/product/research/CONVERSATIONAL_WORK_LEDGER_COMPARABLES_2026-09-03.md`
5. `docs/product/CONVERSATIONAL_WORK_LEDGER_HANDOFF.md`
6. The two scenario documents and persona evidence only when their question is
   relevant.

## Authorized next outcome

Complete P0 for the new, independent product:

- build and run a local synthetic contract/evaluation for the text flow;
- record non-secret capability facts for the owner's existing LangBot route;
- keep all test data synthetic; and
- prepare a concise P0 evidence record for owner review.

## Hard boundaries

- Do not use, copy, modify, deploy, or describe the historical OpenClaw PoC as
  part of this product.
- Do not mutate a server, configure WhatsApp, create GitHub work, install a
  dependency, or contact a design partner unless the owner explicitly requests
  that particular action.
- Do not add a second bot framework to bypass a LangBot adapter limitation.
- Do not include real financial messages, secrets, SSH keys, or credentials in
  tests, logs, commits, or handoffs.
- Do not advance to P1 until P0 exit criteria, user consent text, and owner
  review are complete.

## Environment note

The owner reports a Europe Linux server reachable as `ssh ct`, with LangBot and
its WebUI already running. That SSH alias and its credentials are deliberately
not in this package. A new device must have owner-provided SSH access configured
out of band; never copy private keys through a project archive.

## Package inventory

`MANIFEST.md` lists the intentional contents. No hash, key, secret, or server
configuration is included in this transfer package.
