# Active checkpoint and handoff — bale-auto

This is the repository's single active resume point. Maintenance rules are in
[`README.md`](./README.md). Phase-specific handoffs under `docs/product/` are
historical evidence unless this file explicitly delegates current work to one.

## Metadata

- **Updated:** 2026-09-03
- **Status:** P0 preparation authorized; no server mutation or real-message trial authorized
- **Repository:** `hosseintajdari/bale-auto`
- **Checkout:** `C:\Users\hosse\Documents\ChatGPT\bale-auto\checkout`
- **Branch:** `codex/record-capacity-cleanup`
- **Local state:** inspect `git status --short --branch` and
  `git log -2 --oneline` at the start of a new task; branch state may advance
  after a handoff is written.
- **Local documentation snapshot:** commit `cff7f6b` contains the handoff
  standard and conversational work-ledger source documents. This checkout now
  has uncommitted PRD/research/handoff changes for owner review.
- **Remote state:** GitHub was intentionally not updated; local retention is
  sufficient for the current phase.
- **GitHub tracking:** no Issue or Pull Request is currently recorded for the
  conversational work-ledger design artifacts

## Checkpoint

### Conversational work-ledger design

- **Verified locally:** the exploratory batch `001–025` exists in
  [`CONVERSATIONAL_WORK_LEDGER_100_SCENARIOS_FA.md`](../product/CONVERSATIONAL_WORK_LEDGER_100_SCENARIOS_FA.md).
- **Verified locally:** the failure-oriented batch contains exactly 25
  continuously numbered scenarios, `026–050`, in
  [`CONVERSATIONAL_WORK_LEDGER_25_HARD_SCENARIOS_FA.md`](../product/CONVERSATIONAL_WORK_LEDGER_25_HARD_SCENARIOS_FA.md).
- **Verified locally:** the second batch ends with the recommendation
  **stop for now** because another invented batch is likely to create cosmetic
  variety rather than fresh design evidence.
- **Verified locally:** the conversation contract now separates user-provided
  source, interpretation/draft, confirmed record, relationship/alias, memo,
  reminder, and preference. Every persistent object requires its own explicit
  confirmation.
- **Boundary:** both batches are design hypotheses. No WhatsApp integration,
  ledger storage, reminder delivery, reporting engine, or product workflow has
  been implemented or field-validated.
- **Local retention:** the conversational work-ledger documents and the
  handoff-maintenance standard were committed locally in `cff7f6b` and have not
  been pushed.
- **Unrelated untracked work:** `docs/product/LANGGRAPH_ORCHESTRATION.md`
  remains untracked and outside this checkpoint. Preserve it unless the owner
  explicitly brings it into scope.
- **Verified locally:** `CONVERSATIONAL_WORK_LEDGER_PRD.md` now defines
  P0/P1/P2 outcome gates, MVP retention/deletion defaults, state rules,
  acceptance criteria, and LangBot integration constraints. Adjacent-product
  evidence is in
  `research/CONVERSATIONAL_WORK_LEDGER_COMPARABLES_2026-09-03.md`.

### LangBot P0 environment check

- **Verified read-only on 2026-09-03:** SSH alias `ct` reached host
  `vmi3534345`; it had 7.8 GiB RAM (6.5 GiB available), 4 GiB unused swap,
  and 82 GiB free on its 96 GiB root filesystem.
- **Verified read-only on 2026-09-03:** `langbot`, `langbot-postgres-1`,
  `langbot_box`, and `langbot_plugin_runtime` were running; the `langbot`
  container reported healthy. Its WebUI returned HTTP 200 on loopback
  `127.0.0.1:5300`; the Docker port binding was loopback-only.
- **Unknown:** exact configured channel adapter, sender/conversation/message
  identity fields, model and session-retention configuration, credential
  isolation, signing path, and WhatsApp behaviour. Do not inspect secrets or
  change this server to discover them.

### Existing OpenClaw PoC

- **Repository-recorded history:** PR #1 and PR #11 were merged and the
  fixed, read-only `system.health.read` PoC was previously verified. Commit
  `c2a1e0d` is the last tracked checkpoint before the local-only documentation
  snapshot.
- **Unknown current live state:** deployment health, server capacity, model
  availability, credentials, routes, and external services have not been
  refreshed for this checkpoint. Reverify them before operational claims or
  changes.
- **Boundary:** the OpenClaw PoC and the proposed conversational work ledger are
  separate scopes. Scenario design does not authorize server, GitHub, Notion,
  deployment, or OpenClaw changes.

## Decisions and blockers

The owner accepted a conservative direction on 2026-09-03. The proposed
implementation defaults are now recorded in
[`CONVERSATIONAL_WORK_LEDGER_PRD.md`](../product/CONVERSATIONAL_WORK_LEDGER_PRD.md):
purge raw source on draft resolution, permanent confirmed-record deletion with
a 30-day non-content idempotency marker, allowed `unknown` excluded from sales,
sale means confirmed cash received, pull-only reminders, and affirmative
consent before real messages. The owner authorized P0 preparation on
2026-09-03; P1 remains separately gated.

The remaining P0 blockers are isolated: actual LangBot adapter capabilities
(identity/message ID/signed write path) and consent text. Each has a
synthetic-data fallback; neither authorizes a server or GitHub change.

Historical unresolved choices, retained as design context:

1. Raw-source retention and deletion: duration, user-visible deletion effect,
   and whether confirmed records can outlive the source.
2. Confirmed-record deletion: complete removal, minimal audit trace, or a
   recoverable deletion period.
3. Incoming-payment classification: mandatory meaning at confirmation or an
   allowed `unknown` state excluded from sales.
4. Meaning of `sale`: cash received, order/invoice value, or separately
   reported measures.
5. First-trial reminder delivery: `pull-only` only, or explicitly opted-in
   `private`/`detailed` outbound reminders.
6. Design-partner evidence and privacy agreement required before any real work
   or financial message is used.

The primary blockers are decisions 1–2 (retention/deletion) and 5 (outbound
notification boundary).

## Handoff

### One next outcome

Complete P0's local synthetic contract/evaluation and record only the
non-secret capability facts needed from the owner's LangBot route. Do not
create more synthetic scenario batches before field evidence shows a specific
gap.

### Read in order

1. This file.
2. [`CONVERSATIONAL_WORK_LEDGER_HANDOFF.md`](../product/CONVERSATIONAL_WORK_LEDGER_HANDOFF.md)
   for the product boundary and base contract.
3. [`CONVERSATIONAL_WORK_LEDGER_100_SCENARIOS_FA.md`](../product/CONVERSATIONAL_WORK_LEDGER_100_SCENARIOS_FA.md)
   for scenarios `001–025`.
4. [`CONVERSATIONAL_WORK_LEDGER_25_HARD_SCENARIOS_FA.md`](../product/CONVERSATIONAL_WORK_LEDGER_25_HARD_SCENARIOS_FA.md)
   for scenarios `026–050`, the revised proposed contract, unresolved choices,
   and saturation decision.
5. [`IRAN_SISTAN_WORK_LEDGER_PERSONA_EVIDENCE_2026-08-26.md`](../product/research/IRAN_SISTAN_WORK_LEDGER_PERSONA_EVIDENCE_2026-08-26.md)
   only when evaluating persona assumptions or planning field research.
6. [`CONVERSATIONAL_WORK_LEDGER_COMPARABLES_2026-09-03.md`](../product/research/CONVERSATIONAL_WORK_LEDGER_COMPARABLES_2026-09-03.md)
   for adjacent-product evidence behind the P0/P1/P2 scope.

### Authorized scope

- Build only P0: local synthetic contract/evaluation and a read-only capability
  record for the owner's existing LangBot route.
- Keep the work free of GitHub, OpenClaw, server mutation, and external testing
  until the owner separately authorizes the relevant action.

### Completion criteria

The next phase is complete only when:

- the owner approves the PRD's retention/deletion and P0 scope;
- P0's synthetic acceptance suite passes and LangBot capability facts are
  recorded without server mutation;
- test examples contain only synthetic data;
- any real-message test has separate consent; and
- this handoff is refreshed with actual Git status, P0 evidence, and the newly
  authorized next outcome.

## History pointers

- [`CONVERSATIONAL_WORK_LEDGER_NEXT_25_HARD_SCENARIOS_HANDOFF_FA.md`](../product/CONVERSATIONAL_WORK_LEDGER_NEXT_25_HARD_SCENARIOS_HANDOFF_FA.md)
  — completed execution brief for producing scenarios `026–050`.
- [`SCENARIO_EXECUTION_HANDOFF.md`](../product/SCENARIO_EXECUTION_HANDOFF.md)
  — archived execution brief for scenarios `001–025`.
- [`OPENCLAW_POC.md`](../runbooks/OPENCLAW_POC.md) and
  [`SERVER_PREPARATION_CHECKLIST.md`](../runbooks/SERVER_PREPARATION_CHECKLIST.md)
  — operational references for the separate PoC; live facts require refresh.
