# Active checkpoint and handoff — Conversational Work Ledger

## Metadata

- Updated: 2026-09-05.
- Status: synthetic technical proof passed; P0 awaiting owner review/acceptance.
- Verified target: Linux server `ct`, `/home/admin/bale-auto`, SSH user `admin`.
- Git: this transferred directory has no Git repository, branch or HEAD.
- GitHub: no publication, issue, PR, push or other mutation performed or planned.
- Control environment: this work used Windows Codex with SSH execution on Linux.
  Do not assume another client shares the same working directory; use this file.
- Scope authorized in the current conversation: execute project P0. This covers
  development files and synthetic tests here, not SSH settings, live service
  configuration, credentials, real messages or P1 activation.

## Checkpoint

### Cross-environment continuity — verified 2026-09-05

- The owner requested state synchronization between Windows and `ct`.
- Project instructions now live in `/home/admin/bale-auto/AGENTS.md`.
  At inspection this file was absent; `/home/admin/.codex/AGENTS.md` was empty.
  Global agent configuration was left unchanged.
- Windows entry: `C:\Users\hosse\Documents\ChatGPT\bale-auto`.
  Its root handoff routes here and its `docs/agents/ct-state/` contains explicit
  snapshots refreshed by `scripts/Sync-CtProjectState.ps1` with SHA-256 checks.
- This server handoff remains the single active execution-state source.
  Snapshots are for continuity/review; no two-way code synchronization is enabled.
- The Windows root has an unborn `master` Git repository with existing untracked
  material; this server directory still has no Git repository. Neither was changed.
- Existing P0 evidence was reread and code hashes match the recorded P0 build.
  Tests were not rerun for this documentation-only synchronization.

### Verified synthetic implementation

- Preserved the existing `src/ledger.py`, `tests/test_p0_contract.py`,
  `demo_p0.py` and `p0_synthetic_flow.js`. They are historical prototypes.
- Added `src/p0_core.py` as the current synthetic core. The older amount parser
  concatenates all digits; do not use that prototype for further implementation.
- Added `tests/test_p0_acceptance.py`: 50 source-scenario boundary assertions,
  quantitative suites (50 unconfirmed objects, 50 incoming classifications,
  20 retry/duplicate vectors, 20 correction/deletion vectors), scope isolation,
  concurrent confirmation, signing/tamper, ambiguity and expiry tests.
- Verified on Linux Python 3.12.3: `python3 run_p0_review.py` ran 66 tests,
  zero failures/errors/skips, on 2026-09-05. This includes 3 legacy tests.
- The runner executed an asserted synthetic message -> draft -> unit/category
  clarification -> confirmation -> retrieval/report -> correction -> deletion
  demonstration. Evidence is under `work/p0_evidence/`.
- No production dependencies installed. Core state is in-memory and single
  process; there is no database, HTTP listener, live model or channel connection.
- Normalized cash-sales values are rial; explicit raw amount/unit are retained
  in confirmed objects. Unknown and other nonsale inflows are excluded.
- Separate confirmation gates money, memo, task, reminder, preference and alias;
  correction makes a linked replacement; deletion purges its superseded chain.
- Draft source and candidate fields are purged on resolution. Demonstration
  defaults: 24-hour lazy draft expiry, UTC receipt date when date is omitted,
  30-day keyed-hash deletion marker. These are prototype assumptions, not newly
  approved product policy. All state and the fingerprint key disappear at exit.

### Verified LangBot inspection and integration gap

- Installed-source version `4.10.9`; image tag `rockchin/langbot:latest`.
- `langbot` and `langbot-postgres-1` were healthy; Box and Plugin Runtime running.
- WebUI returned HTTP 200 from `127.0.0.1:5300`; Docker host binding is loopback.
- Telegram and Matrix adapters and per-bot/pipeline fields exist in installed
  source. This does not prove the owner's configured bots are ready.
- Generic webhook pusher creates random UUIDs, lacks an explicit private
  conversation field and sends no signing header in the inspected POST code.
  Matrix's original room/event IDs are retained in native event objects, not
  explicitly exported by this webhook. It is not a validated ledger write path.
- The PRD fallback was used: synthetic signed inbound envelope demonstration.
  A real adapter and authentication for all mutations remain unimplemented.
- Actual configured adapter, model, retention, secrets isolation, admin login,
  WhatsApp behavior and backup/restore remain unknown. Credentials, private
  transcripts, environment variables and database records were not inspected.

### Preserved and changed files

- Updated README and this active handoff with guarded hash checks. Their previous
  exact contents are retained in `docs/agents/history/`.
- New product docs: `P0_CAPABILITIES_2026-09-05.md`,
  `P0_PRIVACY_CONSENT_FA.md`, `P0_EVIDENCE_2026-09-05.md`.
- New runner: `run_p0_review.py`. Temporary installation materials live only
  under this project's `work/p0_20260905/`.
- Existing PRD, scenario documents, product-design handoff and prototypes were
  preserved. No unrelated server files or services were changed.

## Decisions and blockers

- Durable product decisions remain in the 2026-09-03 PRD: source purge on draft
  resolution; permanent confirmed-record deletion with a 30-day non-content
  marker; unknown allowed but excluded from sales; sale means cash received;
  pull-only reminders; affirmative consent before real financial content.
  Historical lists claiming these decisions are unresolved are superseded.
- Owner review of the demonstration and proposed privacy/consent text remains
  pending. Do not label all of P0 accepted or begin P1 from passing tests alone.
- The privacy notice deliberately lists facts still needed before real consent:
  operator/contact, actual model/providers, channel/history retention, draft and
  backup retention, deletion propagation, regional processing and possible cost.
- The proof tests bounded structured Persian text and domain operations. It does
  not establish full natural-language UX, model extraction quality, voice,
  Jalali/relative dates, persistence across restart or live channel reliability.
- When adding persistent storage, revalidate atomic writes, replay after restart,
  key persistence/rotation, encryption, backup restore and deletion propagation.
  No dependency or service change is implied by this handoff.

## Handoff

### One next outcome

Obtain owner review of the concrete P0 evidence and settle the remaining privacy
and channel facts before proposing a bounded real-channel pilot. Continue to
use only synthetic data until the P1 gate is explicitly satisfied.

### Read in order

1. This file and `docs/agents/README.md`.
2. Root `README.md` for commands and implementation limits.
3. `docs/product/P0_EVIDENCE_2026-09-05.md`.
4. `work/p0_evidence/P0_DEMO_FA.md` and `P0_SCENARIO_COVERAGE.md`.
5. `docs/product/P0_CAPABILITIES_2026-09-05.md`.
6. `docs/product/P0_PRIVACY_CONSENT_FA.md` and the existing PRD.

### Completion criteria

- Technical proof: passing synthetic suite, factual capability record and
  reviewable demo/consent draft — produced in this run.
- Formal P0 exit: owner accepts demo and privacy/consent text — still pending.
- P1 entry additionally requires explicit authorization, actual channel/write
  identity validation, storage/privacy readiness and participant consent.

## History pointers

- `history/HANDOFF_2026-09-03_TRANSFER.md`: prior checkpoint with source Windows
  checkout/Git metadata; those paths are historical, not this server's state.
- `history/README_PRE_P0_2026-09-05.md`: previous prototype instructions.
- `../product/CONVERSATIONAL_WORK_LEDGER_PRD.md`: current product contract.
- Existing scenario 001-025 and 026-050 documents: design hypotheses mapped in
  the generated P0 coverage table, not field evidence.
- OpenClaw PoC remains a separate historical scope; it was not touched.
