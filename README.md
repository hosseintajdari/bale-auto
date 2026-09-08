# Conversational Work Ledger

A private, Persian-first work ledger for capturing payments, commitments, and
work notes from chat. A message becomes an editable draft; a record is created
only after the user explicitly confirms it.

## Status

This repository contains the synthetic P0 technical proof. It uses synthetic
data only and is not connected to a live chat channel, model, database, or
financial data. P0 remains pending owner review of the demonstration and the
privacy/consent draft.

## Run the proof

Python 3.12 and the standard library are sufficient.

```bash
python3 -m unittest discover -s tests -v
python3 run_p0_review.py
```

The review runner executes the acceptance suite and an asserted Persian
conversation demonstration. It writes local evidence to `work/p0_evidence/`;
that generated material is intentionally not committed.

## What P0 demonstrates

- Draft-first capture of money, notes, tasks, reminders, preferences, and
  relationships.
- One material clarification at a time, with no silent money-unit conversion.
- Explicit confirmation before a record is created, including the action
  `تأیید و ثبت`.
- Scoped retrieval, duplicate protection, correction, and confirmed deletion.
- Purging raw draft content when a draft is resolved.

## Current limits

The parser supports a deliberately narrow set of structured Persian inputs,
such as `دریافت ۵۰۰ تومان فروش`. It is not a general conversational interface.
There is no live channel integration, persistent storage, voice support,
Jalali/relative-date interpretation, or real-message trial. Do not use it for
real financial data.

## Project map

- `src/p0_core.py` — the sole active in-memory P0 core.
- `tests/test_p0_acceptance.py` — acceptance and adversarial checks.
- `run_p0_review.py` — the canonical test, demonstration, and evidence runner.
- `docs/product/CONVERSATIONAL_WORK_LEDGER_PRD.md` — product decisions and
  phase gates.
- `docs/product/P0_EVIDENCE_2026-09-05.md` — P0 evidence record.
- `CONTRIBUTING.md` and `SECURITY.md` — contribution and reporting guidance.

Earlier Python and Node.js prototypes were removed because they implemented
divergent contracts. New behavior and tests must target the canonical core above.

## Development workflow

Changes are checked by the repository CI workflow. Use a branch and pull
request for changes, and do not commit credentials, private messages, or
generated evidence.
