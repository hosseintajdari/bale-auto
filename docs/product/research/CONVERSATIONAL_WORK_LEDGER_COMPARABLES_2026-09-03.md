# Comparable-pattern research — conversational work ledger

**Status:** design evidence, not a competitor matrix or implementation claim.

**Date:** 2026-09-03

## Question

What proven interaction and data-handling patterns from adjacent products can
make a chat-native work ledger safer and simpler? This review intentionally
examines receipt/expense and local-first ledger patterns, not a claim that any
one product is equivalent to the proposed WhatsApp experience.

## Direct evidence and applicable pattern

| Product/source | Verified behaviour | Adopt | Do not copy |
| --- | --- | --- | --- |
| [Expensify SmartScan](https://help.expensify.com/articles/new-expensify/reports-and-expenses/Troubleshoot-SmartScan-Issues) | Extracts merchant/date/amount; unreadable or incomplete receipts fail with a reason and manual entry remains available. | Treat AI/OCR output as a correctable draft with a manual fallback. | Automated expense submission/payment and enterprise approval semantics. |
| [Dext item review/publish](https://help.dext.com/en/articles/416716-how-to-edit-publish-and-export-items-in-dext) | Extracted item fields can be reviewed; incomplete items remain `To review` and only `Ready` items can publish. | Make state visible: draft, needs clarification, confirm, confirmed; block progression on missing material fields. | Accounting-system publishing and team roles. |
| [Dext duplicate/processing states](https://help.dext.com/en/articles/416741-ways-to-add-documents-to-dext) | Documents progress through processing/inbox; documented duplicate detection can identify a duplicate during submission. | Keep a submission fingerprint and explicit duplicate candidate state. | Automatic deletion of a suspected duplicate; the user must choose duplicate or separate. |
| [Actual Budget rules](https://actualbudget.org/docs/budgeting/rules/) | Keeps original imported payee distinct from normalized payee; rules can be learned from user behaviour and remain editable. | Separate source, normalized record, and user-approved preference. Learning can only prefill a draft. | Automatic category assignment as final financial truth. |
| [Actual Budget import matching](https://actualbudget.org/docs/transactions/importing/) | Uses an import ID first, then amount/date/payee similarity, to avoid duplicate records. | Idempotency key plus cautious similarity detection. | Re-import behavior without an explicit user-facing deletion contract. |
| [LangBot docs](https://docs.langbot.app/) and [repository](https://github.com/langbot-app/LangBot) | Provides WebUI, pipeline/plugin architecture, and Matrix support for bridged channels including WhatsApp. | Use it as the owner-managed channel/runtime and validate the actual adapter in P0. | Assume a generic integration gives a stable WhatsApp identity, message ID, retention policy, or production readiness. |

## Synthesis

The closest proven pattern is not "an AI accountant". It is a bounded pipeline:
capture source -> extract candidate values -> explain missing/ambiguous fields
-> user reviews -> user confirms -> durable record. The product differs by
placing that workflow in ordinary chat, preserving Persian unit ambiguity, and
requiring user confirmation even when a learned pattern is available.

There are also public examples of chat-native personal-expense prototypes, but
they are not used as authoritative product evidence because their claims and
controls are independently unverified. They are only a discovery signal that
chat-based capture is an established direction, not proof of demand, privacy,
or reliability in this product context.

## Consequence for MVP

Build only the text capture -> draft -> confirm -> retrieve loop first. Do not
build reminders, image/voice processing, automated classification, dashboards,
bank access, or accounting export to compensate for missing evidence. A
controlled synthetic test and a consented design-partner observation determine
which extension earns P2 consideration.
