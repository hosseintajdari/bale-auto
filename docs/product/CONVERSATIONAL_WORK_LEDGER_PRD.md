# PRD — Conversational Work Ledger MVP

**Status:** owner decisions accepted; P0 preparation is authorized. No server
mutation, real financial messages, or P1 trial is authorized by this document.

**Updated:** 2026-09-03

**Product boundary:** a private, chat-native work ledger for chat-native,
low-tool users across professions. This is not accounting software, a general
assistant, a CRM, or an OpenClaw continuation.

## 1. Executive summary

### Problem statement

People frequently remember a payment, commitment, or work detail in the same
moment they are busy with work. Opening a spreadsheet or finance application
is often deferred, and the fact is then lost or misremembered. A copied bank
SMS does not itself say whether an incoming amount is a sale, repayment, or a
personal transfer.

### Proposed solution

The user sends text or manually copied bank-SMS text to the product in their
usual WhatsApp chat. The product produces an editable Persian draft, asks one
material question at a time, and creates a durable record only after explicit
confirmation. LangBot is the chat-channel runtime and its WebUI is the
operator-control surface; the ledger remains an independent, narrowly scoped
service.

### Approved MVP decisions

These translate the owner's accepted conservative proposal into an executable
default. They may be revised before implementation, but they do not block the
P0 design gate.

| Decision | MVP rule |
| --- | --- |
| Raw source retention | Keep raw text/transcript only while its draft is active. On confirmation, rejection, or draft expiry, delete the raw body; retain only the confirmed normalized fields and a non-reversible duplicate fingerprint. |
| Confirmed-record deletion | A confirmed record is permanently deleted on a separately confirmed delete request. Retain only a non-content deletion marker for 30 days to make repeat delivery idempotent; it contains no amount, name, message, or transcript. |
| Incoming classification | `unknown` is an allowed confirmed state. It is excluded from a sales report and the exclusion count is shown. |
| Meaning of sale | A sale is cash actually received in a record explicitly classified `sale`. Order or invoice value is outside MVP. |
| Reminder delivery | `pull-only`: no outbound reminder message in MVP. A user can ask for today's reminders or a daily view. |
| Real-message trial | No real financial content enters the product until each design partner has accepted the short privacy notice and affirmative test consent. Synthetic data is the only P0 test input. |

### Success criteria

1. In a synthetic test suite of at least 50 scenarios, 100% of durable money,
   memo, task, reminder, preference, and relationship objects are created only
   after the matching explicit confirmation.
2. In 50 synthetic incoming-money examples, 100% of `unknown`, collection,
   transfer, loan/capital, and `other` records are excluded from sales totals.
3. In 20 duplicate/retry scenarios, the system creates no second confirmed
   record after a repeated confirmation or exact repeated submission.
4. In 20 deletion and correction scenarios, deleted source content is absent
   from retrieval and report output, and correction creates a visible linked
   replacement rather than silently overwriting history.
5. Every supported text-only path completes without buttons, dashboard use,
   or command syntax.

## 2. User experience and scope

### Primary persona

A self-employed or employed person who manages work through messages, calls,
and notes, but does not consistently use a spreadsheet, finance app, or
assistant. The segment is defined by interaction style and digital comfort,
not by profession.

### Core flow

```text
user-provided message
  -> receipt acknowledgement
  -> extraction and draft
  -> one material clarification, if needed
  -> explicit confirmation
  -> confirmed record + redacted audit event
  -> retrieval/query on confirmed records only
```

The acknowledgement is: `پیام دریافت شد. چند لحظه صبر کنید…`. It confirms
receipt only; it does not claim that a person is reading or that a free-form
conversation has begun.

### MVP user stories and acceptance criteria

#### US-01 — capture incoming or outgoing money

As a user, I want to turn a message or copied SMS into a reviewable money
draft so that I can save a payment without opening another app.

- Preserve the stated amount and unit exactly as source fields.
- Ask one question if rial/toman is not explicit; never silently convert.
- For incoming money, allow `sale`, `receivable_collection`,
  `personal_or_inter_account_transfer`, `loan_or_capital`, `other`, or
  `unknown`.
- Show the fields to be stored and require an explicit `confirm` equivalent.
- `yes` is valid only when exactly one active draft expects confirmation.
- No confirmation, silence, timeout, or network retry creates a record.

#### US-02 — capture a memo or follow-up

As a user, I want to save a work note or follow-up so that I can find it
later without making it look like a payment.

- A price, quotation, or promise is a memo unless the user explicitly says a
  payment was made or received.
- A task and a reminder are separate objects, with separate confirmation.
- MVP accepts text. Voice transcription is a P1 capability, not an MVP claim.

#### US-03 — retrieve an item or report

As a user, I want to ask about saved work so that I can recover a fact without
seeing unrelated private information.

- Queries read confirmed, non-deleted records only.
- A sales answer includes its date range, count, total, and number of unknown
  incoming records excluded.
- If the user says "sales" and only unconstrained incoming money exists, ask
  whether they mean `sale` or all incoming money; never substitute one total
  for the other.
- Multiple plausible results require a minimal choice; do not disclose all
  candidates by default.

#### US-04 — correct, cancel, or delete

As a user, I want clear reversal paths so that a correction does not become a
hidden or irreversible mistake.

- `cancel` closes a draft only and cannot delete a confirmed record.
- Correction selects one confirmed record, shows old and proposed values, and
  requires confirmation. The result is a linked replacement with a redacted
  change event.
- Deletion selects one object, says it is permanent, and requires a distinct
  confirmation. Any linked reminder is listed and requires its own action.
- After deletion, retrieval and reports exclude the record; the retained
  idempotency marker cannot reconstruct content.

### Non-goals

- Bank/SMS inbox access, bank accounts, automatic bank sync, or automatic
  payment classification.
- Formal accounting, invoices, taxes, legal/financial advice, inventory, CRM,
  team access, customer messaging, or outbound sales messages.
- Outbound WhatsApp reminders, automated follow-up messages, group messages,
  or proactive notification in MVP.
- General conversation, therapy, medical/clinical features, or patient data.
- Voice, receipt image OCR, a web dashboard for end users, and a full report
  engine in MVP.

## 3. State and data contract

### Persistent objects

| Object | Created only after | MVP state |
| --- | --- | --- |
| Source | user sends processable content | active draft only; raw body purged on resolution |
| Interpretation draft | parse succeeds | `draft`, `needs_clarification`, `cancelled`, `expired`, `confirmed` |
| Money record | confirmation of that money draft | `confirmed`, `superseded`, `deleted` |
| Memo | confirmation | `confirmed`, `superseded`, `deleted` |
| Task | confirmation | `open`, `done`, `deleted` |
| Reminder | separate confirmation | `scheduled_pull_only`, `done`, `deleted` |
| Counterparty/alias | separate confirmation | `confirmed`, `deleted` |
| Preference | separate confirmation | `active`, `replaced`, `deleted` |

### Invariants

- A source, draft, and confirmed record are never the same object.
- Learning/pattern rules may prefill a draft but cannot create or modify a
  financial record without confirmation.
- A message that may contain multiple objects gets one draft per object and
  one confirmation per durable object.
- Every write receives an idempotency key scoped to user, conversation, and
  draft/action. Repeated delivery returns the original result.
- Duplicate detection yields `possible_duplicate`, not silent merge or delete.
  The user chooses `duplicate` or `separate` before any new confirmation.
- Timestamps distinguish source receipt, event time supplied by user, draft
  time, confirmation time, and deletion time.

### Minimal fields for a money record

`record_id`, `user_id`, `direction`, `amount_raw`, `unit_raw`,
`amount_normalized`, `currency`, `event_time`, `classification`,
`counterparty_id?`, `purpose?`, `source_fingerprint`, `created_at`,
`supersedes_record_id?`, `deleted_at?`.

`amount_normalized` must have a declared canonical unit; displayed source
amount/unit remain available on the confirmed record. No conversion is stored
until unit is explicit or separately confirmed.

## 4. Technical specification

### Architecture boundary

```text
WhatsApp user
  -> owner-configured LangBot channel adapter
  -> bounded ledger conversation policy
  -> Ledger Core API
  -> relational store + encrypted backup
  -> redacted audit events

LangBot WebUI -> bot/channel/pipeline operations only
```

LangBot is an integration/runtime dependency, not the ledger's source of
truth. The ledger domain must be callable through a small versioned interface,
so a future channel adapter can be replaced without changing confirmation,
data, or privacy rules.

### MVP integration requirements

- The owner-controlled LangBot configuration must deliver an inbound sender
  identity, conversation identity, message identifier, text body, and reply
  capability to Ledger Core. If a required capability is absent, P0 stops and
  uses a synthetic adapter; do not add another bot framework to work around it.
- Ledger Core must verify a trusted adapter credential and reject direct public
  writes.
- LangBot/WhatsApp configuration, model selection, token pricing, regional
  availability, and session-history retention are external facts. P0 verifies
  them in the owner's existing instance before real-data testing.
- The supplied server capacity is reported as 4 vCPU, 8 GB RAM, 100 GB disk,
  unlimited bandwidth, and Europe location. It is adequate as an initial
  planning envelope, not proof of live health, security, route, backup, or
  channel readiness. This PRD authorizes no server change.

### Security and privacy requirements

- Per-user authorization; no cross-user retrieval, search, or duplicate match.
- Store secrets outside source control and never echo them in chat, logs, or
  audit events.
- Encrypt persisted content and backups; logs contain event type, correlation
  identifier, status, and timestamp, never message body, amount, name, card
  suffix, or transcript.
- Provide user-visible deletion semantics exactly as specified above.
- No use of message content for training, unsolicited outreach, or broad
  analytics in MVP.
- A privacy notice and affirmative consent gate precede any real-message trial.

### AI requirements

- The model may classify intent, extract candidate fields, and formulate a
  Persian draft. It has no direct database write, delete, outbound-message, or
  shell capability.
- Deterministic validation checks units, required fields, active-draft state,
  confirmation grammar, ownership, idempotency, and report filters.
- Low-confidence extraction leads to a single clarification or a manual-entry
  draft, never an invented value.
- Evaluate with at least 50 synthetic Persian examples spanning rial/toman,
  ambiguity, duplicate/retry, correction, deletion, off-scope text, and report
  exclusions. A material safety violation is any write without confirmation,
  silent monetary-unit conversion, cross-user disclosure, or an `unknown`
  inflow included in sales.

## 5. Non-time-based milestones

Milestones are outcome gates, not calendar promises. The one-week target is
the intended MVP delivery window; it changes neither the quality gates nor the
scope.

### P0 — unblock and prove the narrow path

**Outcome:** a safe, executable technical slice is specified and demonstrated
with synthetic data only.

1. Record the approved MVP decisions in this PRD and turn the 50 scenarios
   into an executable synthetic acceptance suite.
2. Run a read-only capability check in the owner's LangBot WebUI/instance:
   sender identity, conversation identity, stable message ID, inbound text,
   outbound reply, separate bot configuration, persistence behavior, and
   administrator access. Record actual version and capabilities; no inference
   from generic documentation.
3. Build a synthetic adapter contract test before WhatsApp: inbound text ->
   draft -> correction/confirmation -> confirmed record -> query.
4. Demonstrate the P0 safety matrix: one explicit confirmation, unit
   clarification, `unknown` excluded from sales, repeat confirmation
   idempotency, duplicate candidate, correction, permanent deletion, and
   off-scope refusal.
5. Write the one-page privacy notice and consent text; do not collect real
   financial content yet.

**P0 blockers and fast exits**

| Blocker | Fast exit that preserves the product boundary |
| --- | --- |
| LangBot does not expose stable sender/conversation/message IDs | Keep P0 on the synthetic adapter and obtain the owner's confirmed adapter capability; do not invent identity from display name or add a second framework. |
| LangBot cannot call Ledger Core safely | Use a bounded local/plugin integration only after its permissions and request signing are demonstrated. Do not expose a write endpoint publicly. |
| WhatsApp path is unavailable or unstable | Finish the same contract through the synthetic adapter; WhatsApp remains a P1 channel gate, not a reason to weaken data rules. |
| Consent text is not approved | Use synthetic data only; do not delay P0 contract/evaluation work. |
| Model output is unreliable | Route to manual structured clarification; deterministic validation still controls writes. |

**P0 exit criteria:** all P0 tests pass on synthetic data; the integration
capability record is factual; the privacy/consent text is approved; and the
owner accepts the demonstration. Failure of the real WhatsApp channel does not
block the synthetic proof, but does block P1 channel testing.

### P1 — controlled WhatsApp MVP trial

**Outcome:** a small, consented design-partner test validates whether the
capture-confirm-retrieve loop is understandable in the owner's actual LangBot
WhatsApp route.

- Enable text-only capture, confirmation, correction, deletion, and basic
  retrieval for approved participants only.
- Retain metrics with no message bodies: initiated drafts, confirmations,
  corrections, cancellations, duplicate warnings, retrieval success, and
  safety defects.
- Conduct a restore rehearsal from an encrypted backup using synthetic data.
- Pause real-data activity on any safety violation and preserve evidence
  without retaining raw content unnecessarily.

**P1 exit criteria:** every participant has consented; no unconfirmed write or
cross-user disclosure occurs; metrics and observed corrections support a
specific usability conclusion; and the owner reviews the results.

### P2 — earned extensions

**Outcome:** only evidence-supported capabilities are considered.

- Voice transcription with the same draft/confirmation contract.
- Receipt/image input, tested separately for extraction and privacy.
- Pull-only reminders and daily view, after capture reliability is shown.
- Optional private/detailed outbound reminders only after separate opt-in,
  platform-policy validation, and notification-exposure testing.
- Export and minimal web recovery/settings view.

No P2 item starts merely because P1 was attempted. It needs a P1 evidence gap,
an explicit owner decision, updated acceptance tests, and a revised privacy
review.

## 6. Risks and evidence-based design choices

| Finding | Design consequence |
| --- | --- |
| Expensify documents that OCR extraction can miss or misread material fields, and provides manual correction/fallback. | Extraction produces an editable draft; no confidence score can bypass confirmation. |
| Dext separates processing, `To review`, `Ready`, and explicit publish; missing/duplicate fields keep an item from the ready path. | Explicit draft/clarification/confirmed states are core product states, not UI decoration. |
| Actual Budget retains imported source text separately from normalized payee/rules and uses IDs plus field similarity for duplicate matching. | Preserve source-derived fingerprint separately from confirmed data; offer duplicate resolution rather than silent merge. |
| LangBot documents a WebUI, pipelines, plugins, and Matrix as a bridge for WhatsApp and other channels. | Treat LangBot as a configurable channel/runtime. Verify the owner's exact adapter and the identity/persistence contract in P0 before real messages. |

### Sources consulted

- [Expensify: SmartScan troubleshooting](https://help.expensify.com/articles/new-expensify/reports-and-expenses/Troubleshoot-SmartScan-Issues)
- [Dext: edit, review, and publish items](https://help.dext.com/en/articles/416716-how-to-edit-publish-and-export-items-in-dext)
- [Dext: `To review` and `Ready` states](https://help.dext.com/en/articles/416750-what-do-to-review-and-ready-mean-in-dext)
- [Actual Budget: rules and original imported payee](https://actualbudget.org/docs/budgeting/rules/)
- [Actual Budget: duplicate transaction matching](https://actualbudget.org/docs/transactions/importing/)
- [LangBot documentation](https://docs.langbot.app/) and [LangBot repository](https://github.com/langbot-app/LangBot)

## 7. Owner approval before implementation

The owner accepted the MVP direction and authorized P0 preparation on
2026-09-03. P0 begins with the local synthetic contract and read-only LangBot
capability record; no GitHub, server mutation, OpenClaw, or external-user
action is required. Advancing to P1 still requires the explicit consent gate,
P0 exit evidence, and owner review.
