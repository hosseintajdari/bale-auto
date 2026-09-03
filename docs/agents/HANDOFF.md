# Active checkpoint and handoff — bale-auto

This is the repository's single active resume point. Maintenance rules are in
[`README.md`](./README.md). Phase-specific handoffs under `docs/product/` are
historical evidence unless this file explicitly delegates current work to one.

## Metadata

- **Updated:** 2026-09-03
- **Status:** awaiting owner decisions; no product implementation authorized
- **Repository:** `hosseintajdari/bale-auto`
- **Checkout:** `C:\Users\hosse\Documents\ChatGPT\bale-auto\checkout`
- **Branch:** `codex/record-capacity-cleanup`
- **Local state:** inspect `git status --short --branch` and
  `git log -2 --oneline` at the start of a new task; branch state may advance
  after a handoff is written.
- **Local documentation snapshot:** commit `cff7f6b` contains the handoff
  standard and conversational work-ledger source documents.
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

The owner must decide these before a build-ready product specification can be
approved:

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

Produce an owner-reviewed, build-ready PRD/specification for the conversational
work ledger. Do not create more synthetic scenario batches before field
evidence shows a specific gap.

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

### Authorized scope

- Clarify the six owner decisions above.
- Draft or revise a product PRD/specification with state transitions,
  acceptance criteria, privacy/retention/deletion behavior, duplicate and
  idempotency behavior, correction semantics, reporting exclusions, and
  synthetic test cases.
- Keep the result design-only until the owner explicitly authorizes
  implementation or external testing.

### Completion criteria

The next phase is complete only when:

- each owner decision is recorded as approved or explicitly deferred;
- every persistent object and allowed state transition has a testable rule;
- retention, deletion, correction, duplication, reporting, and reminder
  behavior have acceptance criteria;
- test examples contain only synthetic data;
- the owner approves the specification before implementation; and
- this handoff is refreshed with the approved artifact, evidence, Git status,
  and the newly authorized next outcome.

## History pointers

- [`CONVERSATIONAL_WORK_LEDGER_NEXT_25_HARD_SCENARIOS_HANDOFF_FA.md`](../product/CONVERSATIONAL_WORK_LEDGER_NEXT_25_HARD_SCENARIOS_HANDOFF_FA.md)
  — completed execution brief for producing scenarios `026–050`.
- [`SCENARIO_EXECUTION_HANDOFF.md`](../product/SCENARIO_EXECUTION_HANDOFF.md)
  — archived execution brief for scenarios `001–025`.
- [`OPENCLAW_POC.md`](../runbooks/OPENCLAW_POC.md) and
  [`SERVER_PREPARATION_CHECKLIST.md`](../runbooks/SERVER_PREPARATION_CHECKLIST.md)
  — operational references for the separate PoC; live facts require refresh.
