# Active checkpoint and handoff — Conversational Work Ledger

## Metadata

- Updated: 2026-09-06.
- Status: synthetic technical proof passed; GitHub alignment and hosted CI
  verified; P0 awaits owner review/acceptance.
- Verified target: Linux server `ct`, `/home/admin/bale-auto`, SSH user `admin`.
- Git: server publication checkout on `main`; the verified GitHub-alignment
  source commit is `7604e48b3b564e4582bb834278609c8f9e16f424`.
- GitHub: private remote `https://github.com/hosseintajdari/bale-auto.git` is
  configured. The former remote `main` is verified at
  `archive/pre-ledger-main`; the ledger baseline replaced `main` using an exact
  force-with-lease and passed hosted CI.
- Control environment: this work used Windows Codex with SSH execution on Linux.
  Do not assume another client shares the same working directory; use this file.
- Scope authorized in the current conversation: align the local repository with
  GitHub conventions and run synthetic checks. This does not authorize
  credentials, live service configuration, real messages or P1 activation.

### GitHub reconstruction — verified 2026-09-05

- The owner authorized GitHub as the code repository to prevent future drift.
- The former GitHub `main` is an older OpenClaw PoC and is not aligned with this
  Conversational Work Ledger source tree. Its current remote commit was
  `8bc8ff34de70be235578353489a583e9c19aa2e5` before any replacement.
- This server directory is now a Git repository on `main`, with baseline commit
  `d00c3bfaa122885834157545557980a4bee56ed9` and remote
  `https://github.com/hosseintajdari/bale-auto.git` configured. The committed
  tree excludes `work/`, Python bytecode and environment files.
- Server HTTPS authentication was established through GitHub Device Flow for
  the repository owner; credentials are stored outside the project with mode
  `0600`. Authenticated fetch, API access, and repository `ADMIN` permission were
  verified without printing credential material.
- The old GitHub `main` commit
  `8bc8ff34de70be235578353489a583e9c19aa2e5` was published and verified at
  `archive/pre-ledger-main` before replacing `main`.
- GitHub Actions is enabled and standard hosted runners already have successful
  historical runs. The repository's current private GitHub Free plan does not
  expose branch protection; the API returned the documented Pro-plan requirement.
  Privacy was preserved and no paid-plan change was made.
- After the Git bootstrap, `python3 run_p0_review.py` again passed all 66 tests
  with zero failures, errors or skips on 2026-09-05. It remains synthetic only;
  the regenerated `work/p0_evidence/` artifacts are intentionally ignored.

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
  material; it remains separate from this server checkout and was not changed.
- The server checkout remains the publication source. Existing P0 evidence and
  code are preserved; generated `work/` evidence remains ignored.

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

- The root README is product-facing: it introduces the ledger, P0 status,
  proof commands, capabilities and limits. It deliberately excludes execution
  host names, server paths and historical-project references. This handoff is
  the internal operational record for those facts.
- Added the minimal repository baseline: `.github/workflows/ci.yml`,
  `CONTRIBUTING.md`, `SECURITY.md`, `.github/pull_request_template.md`, and
  `.github/CODEOWNERS`. `DOCUMENTATION_BUNDLE.md` is a local ignored transfer
  bundle and is intentionally not part of the repository tree.
- On 2026-09-05, `git diff --check`, targeted credential/private-key inspection,
  and workflow content assertions passed. `python3 run_p0_review.py` passed all
  66 synthetic tests with zero failures, errors, or skips; no live channel or
  persistent storage was exercised.
- CI action pins were verified by read-only GitHub tag lookups:
  `actions/checkout` v4.2.2 and `actions/setup-python` v5.6.0. GitHub-hosted run
  `33992863414` passed on source commit `7604e48` with the `synthetic-review`
  job successful. Actions is limited to GitHub-owned actions; the workflow token
  default and explicit workflow permission are read-only.
- New product docs: `P0_CAPABILITIES_2026-09-05.md`,
  `P0_PRIVACY_CONSENT_FA.md`, `P0_EVIDENCE_2026-09-05.md`.
- New runner: `run_p0_review.py`. Temporary installation materials live only
  under this project's `work/p0_20260905/`.
- Existing PRD, scenario documents, product-design handoff and prototypes were
  preserved. No unrelated server files or services were changed.

## Decisions and blockers

### Embednet OS recovery alignment — verified 2026-09-06

- The owner identified Embednet OS as the Notion portfolio/PKM map and asked
  for GitHub-first coordination while Notion remains stale. This checkout is a
  separate track from `bale-med` and `Bale-Med-Prices`; no code, credentials,
  services, webhooks, or deployment work is shared.
- Until the linked Notion pages are reviewed, current owner instruction and
  verified GitHub state take precedence over existing Notion content. See
  `docs/agents/EMBEDNET-OS.md`. This is a temporary recovery rule, not a change
  to the product P0/P1 gates.
- The concise Notion-ready status in that document is intended for a
  Notion-connected agent. No Notion page was changed from this server session.

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

### Issue #22 code remediation — 2026-10-20

- Removed the committed fallback value for `PANEL_API_SECRET`; panel emission
  now requires an explicitly configured secret and startup fails before Bale API
  access when it is missing. Operators can explicitly disable panel emission.
- Added a configuration regression test and README setup guidance. Synthetic
  validation passed 87 tests; compileall and `git diff --check` passed.
- No live service, credentials, panel, or exposed-secret rotation was accessed.
  Rotation remains an operator action outside this code change.
- Branch: `codex/fix-issue-22`; PR pending creation/CI.

### Issue #37 session persistence — 2026-10-20

- `save_session` now upserts missing sessions and refuses to overwrite another
  user's session. Regression tests verify both cases.
- `python3 run_p0_review.py`: 89 tests passed; compileall and diff check passed.
- Branch: `codex/fix-issue-37`; PR pending creation/CI.

### One next outcome

Obtain owner review of the concrete P0 evidence and settle the remaining privacy
and channel facts. Continue to use only synthetic data until the P1 gate is
explicitly satisfied. Use GitHub branches and pull requests for subsequent code
changes; private-branch protection remains unavailable on the current plan.

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
