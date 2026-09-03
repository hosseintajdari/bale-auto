# ARCHIVED CHECKPOINT — First 25 Conversational Work-Ledger Scenarios

> **Stop here for new work.** This file documents the completed first batch
> (`001–025`) only. Its former next-stage brief has also been completed. The
> only active project resume point is now
> [`../agents/HANDOFF.md`](../agents/HANDOFF.md).

**Status:** First exploratory scenario batch completed and reviewed. This is a
design task, not an implementation task.

**Created:** 2026-08-26


## Objective

Create one Persian Markdown artifact containing **exactly 25 distinct,
realistic conversation scenarios** for the prospective chat-native work
ledger. This first batch is deliberately exploratory: its purpose is diversity
and surfacing ambiguity, not completeness or a claim of market prevalence.

Do not code, prototype, deploy, change product behavior, or reopen the separate
OpenClaw/bale-auto technical PoC. The only authorized mutations for this stage
are the scenario Markdown file and this execution handoff.

## Completed-stage record and next-agent boundary

- The exploratory set `001–025` has been drafted in
  `docs/product/CONVERSATIONAL_WORK_LEDGER_100_SCENARIOS_FA.md`.
- It includes the requested compact coverage index, scenario-level design
  questions, extracted domain map, and coverage/repetition review.
- The historical `_100_` filename is not a request to extend the artifact to
  100 scenarios. The owner deliberately changed this stage to 25.
- A next agent must treat the 25 scenarios as design hypotheses and facilitate
  owner/field review of their ambiguities before proposing implementation or
  more scenarios. No expansion, code, server work, OpenClaw work, GitHub,
  Notion, commit, or push is authorized by this handoff.

## Required sources, in order

Read both files completely before drafting:

1. [`CONVERSATIONAL_WORK_LEDGER_HANDOFF.md`](./CONVERSATIONAL_WORK_LEDGER_HANDOFF.md)
   — authoritative product boundary, current interaction contract, domain
   objects, non-goals, privacy rules, and unresolved decisions.
2. [`research/IRAN_SISTAN_WORK_LEDGER_PERSONA_EVIDENCE_2026-08-26.md`](./research/IRAN_SISTAN_WORK_LEDGER_PERSONA_EVIDENCE_2026-08-26.md)
   — evidence base, composite role, Iran/Sistan constraints, coverage axes, and
   research gaps.

If the two files appear to conflict, preserve the product boundaries in the
first file and use the second file to make the persona and situations
realistic. Do not use repository code, the technical PoC, old OpenClaw state,
or imagined capabilities as product evidence.

## Role to inhabit

Write from the perspective of the composite role defined in the research note:
a capable, locally rooted, phone-first worker or small-business operator in
today's Sistan and Baluchestan whose money, promises, deliveries, notes, and
follow-ups are scattered across memory, calls, WhatsApp, bank SMS, paper, and
occasional software.

This person is practical and commercially competent, not a caricature of a
“low-literacy,” poor, rural, anti-technology, or culturally uniform user. The
person is busy, economically pressured, skeptical of unnecessary data entry,
protective of privacy and reputation, and willing to adopt a tool that creates
immediate value without shame, hidden interpretation, or loss of control.

The scenario set may place this underlying behavioral persona in different
professions and settings. Do not pretend one fictional biography represents
the whole province. Mark the scenarios as design hypotheses, not observed
market prevalence.

## Output file

Create:

`docs/product/CONVERSATIONAL_WORK_LEDGER_100_SCENARIOS_FA.md`

The historical filename is retained for continuity, but the approved target in
this phase is **25**, numbered `001` through `025`, not 100.

Write the artifact primarily in natural Persian. Keep product or technical
terms in English only when that improves clarity. Use synthetic names, amounts,
card suffixes, phone fragments, and business details. Never include real
personal, patient, banking, or credential data.

## Required structure of the scenario artifact

Start with a short Persian preface that says:

- these are research-backed design hypotheses, not claims about all Iranian or
  Sistan-and-Baluchestan users;
- the current product is design-only and does not implement these flows;
- the purpose is to test and redesign the conversation contract.

Then provide a compact coverage index. Number the scenarios continuously from
`001` through `025`.

Use this concise schema for every scenario:

1. **Title and primary intent**
2. **Person and moment** — profession/role, setting, immediate pressure, and
   current record habit
3. **Raw inbound message** — the exact Persian text, copied bank SMS, or a short
   transcript of the voice note the user would naturally send
4. **Likely conversation** — a realistic user/system exchange, normally 2–8
   turns; include correction, silence, refusal, or cancellation when natural
5. **Hidden ambiguity and stakes** — what the user did not say and why an error
   matters
6. **Design reading** — what the current design handles, where it may fail, and
   the concrete risk or opportunity exposed
7. **Question for the next design pass** — one answerable product question or
   test, not a generic feature suggestion

Keep each scenario detailed enough to expose a real design decision but short
enough that all 100 can be reviewed. Prefer concrete dialogue over essays.

After scenario 025, add a domain map extracted from the scenarios. It must
cover the main events, core objects, statuses, fixed rules, prioritized
ambiguities, and real words/phrases that require field research. Then add a
compact coverage-and-repetition review, including deliberate gaps for a later
research/design pass.

## Coverage contract

The set must exercise all eight coverage axes in the persona-evidence file:
role, setting, record habit, economic event, infrastructure event,
conversation shape, trust/privacy risk, and success test.

Across the 25 scenarios, seek meaningful representation across the axes; do
not force a rigid quota that makes dialogue artificial:

- include employees, self-employed workers, retailers, tradespeople, office
  workers, transport/delivery workers, producers, professionals, home-based
  workers, and family-business participants;
- include Zahedan, Chabahar/coastal work, northern Sistan/Hamoun, other towns,
  villages, and road/mobile work without implying equal market prevalence;
- include normal successful capture as well as partial payment, changing
  prices, debt collection, returns, cancelled work, delayed wages, shortages,
  personal/business transfers, and unknown classifications;
- exercise money records, tasks/follow-ups, work memos, financial and
  non-financial reminders, retrieval/report questions, correction/deletion,
  preferences, and bounded off-scope handling;
- include plain text, voice notes, pasted bank SMS, typos, omitted rial/toman,
  relative dates, aliases, fragmented messages, corrections, jokes, refusal,
  silence, delayed delivery, and duplicate sends;
- include weak connectivity, an interruption or shutdown, power loss,
  resumable drafts, and the possibility that a phone is shared or its lock
  screen is visible;
- include privacy-sensitive counterparties and moments when the user wants a
  record but no outbound reminder, or a reminder but minimal visible detail;
- include users who already keep paper notes, search old chats, use a basic
  accounting app, or record selectively. Do not make “no records at all” the
  universal starting point;
- give meaningful representation to women, younger workers, employees, and
  non-owner family-business participants without inventing cultural rules for
  them;
- include a substantial set of failures, abandonment, correction,
  cancellation, or explicit product limitations rather than making the product
  succeed automatically.

Do not force a rigid quota that makes the dialogue artificial. Use a private
coverage matrix while drafting, then publish only a compact coverage summary.

## Product boundaries that every scenario must respect

- This is a conversational work ledger, not formal accounting, tax filing,
  banking, CRM, inventory, invoicing, or a general AI assistant.
- A bank inflow is not automatically a sale.
- Financial interpretation remains a draft until the user confirms it.
- Ask one material clarification question at a time.
- Plain-text choices must work; WhatsApp buttons are optional enhancement only.
- Do not read private chats, groups, bank accounts, or SMS inboxes. The user
  must provide the source message or transcript.
- Do not send customer replies, advertisements, group messages, or other
  external actions.
- Do not invent empathy, act human, or become a companion/therapist.
- Do not introduce patient data, medication advice, diagnosis, telemedicine,
  or clinical automation.
- Do not assume official WhatsApp policy, pricing, onboarding, outbound
  templates, or regional availability; flag implementation dependencies.
- Do not treat the owner's cultural values as feature names, dialect
  decoration, or branding slogans.

## Anti-stereotype and evidence rules

- Do not fabricate Balochi words, accents, customs, tribal behavior, religious
  rules, or gender restrictions.
- Do not equate informality with illegality, tax evasion, cash-only operation,
  or absence of records.
- Do not present old, national, anecdotal, or public-discussion evidence as a
  current province-wide fact.
- Do not let war, inflation, drought, fuel, internet, or poverty become scenery
  repeated in every scenario. Use them only when they materially change the
  work decision.
- Preserve the user's dignity and competence. Friction should arise from the
  workflow and environment, not from mocking mistakes.
- When evidence is missing, label the scenario assumption and turn it into a
  field-research question.

## Execution sequence for the next agent

1. Read the two required sources completely.
2. Build a private 25-row coverage matrix before writing full dialogue.
3. Draft the one exploratory batch, `001–025`, in the single target file.
4. Reread the full artifact and remove repeated plots, occupations, user
   phrasings, and identical design conclusions.
5. Validate that numbering is continuous and exactly 25 scenario headings
   exist.
6. Verify that every scenario states a real ambiguity or stake and ends with a
   concrete design question.
7. Check that the synthesis follows the scenarios and distinguishes evidence,
   inference, proposal, and unresolved uncertainty.
8. Inspect Git status and report the scenario file and this updated handoff as
   the task changes; preserve all pre-existing untracked and user-owned files.

No commit, branch change, push, PR, Notion update, server action, dependency, or
product implementation is authorized.

## Copy-ready prompt for the next Codex task

>
