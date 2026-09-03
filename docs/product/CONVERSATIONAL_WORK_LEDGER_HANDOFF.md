# Product Design Handoff — Conversational Work Ledger

**Status:** Design direction only. Nothing in this document is implemented or
approved for production.

**Last updated:** 2026-08-26

**Purpose:** Give the next product/design/engineering agent enough context to
continue the product-design work without replaying the conversation. This is a
product handoff, not a replacement for the technical OpenClaw handoff or a
statement of current repository capabilities.

## Project boundary decision

The owner confirmed that the OpenClaw installation and its associated learning
and automation work are complete and closed. This prospective product is **not**
a continuation of OpenClaw, is not an OpenClaw tutorial, and must not depend on
its deployment, server, GitHub roadmap, Notion state, or technical PoC.

The document currently happens to be stored in the `bale-auto` checkout only as
a handoff artifact. The owner plans to take it to a different product-design
chat. A future agent must not inspect, modify, deploy, or describe OpenClaw as
part of this product unless the owner explicitly reopens that separate project.

---

## 1. Product thesis

The commercial direction is not "general automation", a generic AI chatbot, or
formal accounting. It is a **chat-native work ledger** for people who run daily
work through messages, calls, and voice notes but do not reliably use complex
desktop software, spreadsheets, or an assistant.

The first channel under design is **WhatsApp**. The user should be able to use
their ordinary consumer WhatsApp account. The product's own sending number may
later use an official business integration, but consumer users must not need a
Business account, a new app, a dashboard, or command syntax to get value.

Core promise:

> A work-related message that the user chooses to send to the product can be
> turned into a clear, reviewable record and found later. Nothing important is
> finalized, sent, or surfaced externally without the user's explicit choice.

The user is a pharmacist and technology builder in Sistan and Baluchestan. The
product should serve people across professions based on their interaction style
and digital comfort, not a vertical label such as "shop owner" or "doctor".
Doctors, tradespeople, retailers, and office workers can share the same problem:
they are competent at their work but lack a dependable external memory for
money, promises, and follow-ups.

The user's cultural values of keeping commitments, good reputation through
responsiveness, and voluntarily taking responsibility are a **decision lens**.
They are not feature names, phonetic branding, or a superficial cultural theme.

---

## 2. What the product is and is not

### In-scope product outcome

The product receives a user-provided text, voice note, or manually copied bank
SMS; derives a draft; resolves real ambiguity; obtains confirmation; stores a
structured record; and later answers related queries in the same chat.

### Explicit non-goals

- Formal bookkeeping, tax filing, legal financial advice, or an official P&L.
- Reading the user's SMS inbox, bank account, private WhatsApp chats, or groups.
- Sending customer replies, sales messages, advertising, or group messages.
- A free-form companion, therapist, emotional-support agent, or general chat
  product.
- Autonomous actions, silent financial classification, or silent reminders.
- Patient data, diagnosis, medication advice, telemedicine, or any clinical
  automation.
- Multi-user teams, secretary access, CRM, invoices, inventory, and full
  accounting in the first product scope.

The existing bale-auto repository is a completed, separate personal automation
PoC. It does **not** implement this commercial product, WhatsApp integration,
financial records, voice, billing, or multi-tenancy. Do not describe the
current PoC as if those capabilities already exist, and do not use it as a
technical prerequisite for this product.

---

## 3. Domain model: stored objects versus user intents

Do not confuse a user request with a database object.

### Stored objects

1. **Money record** — one confirmed incoming or outgoing payment.
2. **Task / follow-up** — a non-financial action that should be completed or
   checked later.
3. **Work memo** — a short text or voice-derived note the user wants to find
   later.
4. **Reminder** — a separately scheduled prompt linked to a money record,
   task, or memo, or standing on its own.
5. **Counterparty / relationship** — an optional person, business, card suffix,
   or alias linked to relevant records.

### User intents in chat

1. Register money received.
2. Register money paid.
3. Retrieve, inspect, or follow up on the ledger.
4. Capture a text or voice work memo.
5. Create a financial reminder, such as collecting a receivable or making a
   payment.
6. Create a non-financial reminder, such as calling someone or checking a
   delivery.
7. Ask a report or aggregate question.
8. Correct, delete, or change a preference for a previously created item.

A report is a read-only query over confirmed records; it is not a new record.
"Follow up on the incoming ledger" is similarly a retrieval/action intent, not
another kind of financial event.

---

## 4. Minimum money taxonomy

An incoming bank transfer is not automatically a sale. To answer a question
such as "What were my sales this month?" honestly, the system needs a simple,
editable business meaning for every confirmed incoming record:

- Sale
- Receivable collection
- Personal or inter-account transfer
- Loan or capital
- Other
- Unknown / decide later

The equivalent outgoing classifications can remain intentionally light in the
first version: operating expense, purchase, debt payment, transfer, other, or
unknown.

If no meaning is known, the record may still be stored as an incoming payment,
but it must remain excluded from any claimed sales total. A response should make
the denominator clear, for example: "Confirmed sales total: X; four unknown
incoming records are excluded." Never call total incoming transfers "sales"
without this classification.

This is a lightweight operational ledger, not statutory accounting.

---

## 5. Conversation contract

### Immediate acknowledgement

For every processable inbound message, first reply in Persian with a short
status acknowledgement:

> پیام دریافت شد. چند لحظه صبر کنید…

This confirms delivery; it must not imply that a human is reading or that an
unbounded social conversation has started.

### Parse, then draft

After processing, return a compact, editable draft. Example for a copied bank
SMS:

> پیش‌نویس دریافت وجه آماده است.
> مبلغ: ۵۰۰٬۰۰۰ تومان
> زمان: امروز، ۱۳:۲۰
> مبدا: کارت با پایان ۹۴۲۱
> نام و بابت: مشخص نیست
>
> تأیید و ثبت / اصلاح / ثبت نکن

The user can confirm through plain text in all cases. If official WhatsApp
interactive controls are available, buttons are only progressive enhancement;
they must never be a requirement.

### Ambiguity protocol

Ask **one direct question at a time** when a material field is ambiguous. Do
not invent or silently convert a meaning.

Example:

> مبلغ پیام ۵٬۰۰۰٬۰۰۰ است. واحد را انتخاب کنید: ریال یا تومان؟

Preserve the original amount/unit from the source and show any conversion
explicitly. A confirmed convention can become a user preference for similar
messages, but every preference must be visible, reversible, and treated as a
suggestion rather than an immutable rule.

### Unknown or off-scope message protocol

The product must not pretend to be a human companion. It may be polite and
lightly warm, but it must not offer emotional interpretation, claim to
understand feelings, or begin an open-ended chat.

If a message cannot be classified, ask:

> این مورد را برای ثبت در کدام دسته می‌فرستید؟
> ۱. دریافت وجه
> ۲. پرداخت وجه
> ۳. کار یا پیگیری
> ۴. یادداشت کاری
>
> یا بنویسید: «ثبت نکن».

If the response is a joke or unrelated message, reply once with a light,
role-consistent template and repeat the choice:

> 🙂 برای ثبت، شمارهٔ ۱ تا ۴ را بفرستید؛ یا بگویید «ثبت نکن».

After a second non-answer, close the draft without storing it:

> ثبت نشد. هر وقت خواستید، مورد بعدی را بفرستید.

This bounded retry rule avoids user confusion, anthropomorphic deception,
unnecessary model cost, and infinite conversational loops.

---

## 6. Voice memo behavior

A voice note is first transcribed, then treated as candidate data, not as a
standing instruction. Example:

> پیش‌نویس یادداشت کاری
> موضوع: قیمت قطعهٔ کرمی از سعید
> نکته: احتمال رسیدن در هفتهٔ آینده
>
> ثبت یادداشت / تبدیل به یادآوری / اصلاح / ثبت نکن

A confirmed memo must be retrievable by natural-language search later. It may
be surfaced when the user asks a related question, asks for their requested
daily view, or explicitly asks what they said about a topic. It must not appear
spontaneously in unrelated conversations, especially when privacy may matter.

---

## 7. Reminder engine is a separate subsystem

Recording a past event and scheduling a future prompt are different jobs.
Model reminders independently rather than as a boolean on a transaction.

### Reminder classes

- **Financial reminder:** collect a receivable, make a payment, review an
  outstanding incoming/outgoing item.
- **Non-financial reminder:** call, deliver, ask, check, or any other task.

### Mandatory reminder fields

- Clear title/action
- Due date and time (or explicit no-time)
- Link to a relevant money record, task, or memo when available
- Delivery preference
- Privacy level
- Confirmation state

### Privacy levels per reminder

1. **Detailed:** notification may include title, amount, counterparty, and
   time.
2. **Private:** an outbound notification reveals no title, person, amount, or
   business detail; it can say only that a private reminder exists.
3. **Silent / pull-only:** no WhatsApp message is sent. The item is shown only
   when the user asks for reminders or their daily view.

Do not assume phone lock-screen or WhatsApp notification previews are private.
Automatic WhatsApp reminders require explicit opt-in and must respect current
WhatsApp rules, including the customer-service window and approved templates
outside it. Reminder delivery is a later implementation risk, not a reason to
send unsolicited messages in the first release.

---

## 8. Queries and reports stay in chat

The initial reporting surface is the same WhatsApp chat. A separate dashboard
is optional later and must not be required for basic value.

Natural queries include:

- "فروش این ماه چقدر بوده؟"
- "مجموع دریافت‌ها چقدر بوده؟"
- "پرداخت‌های این هفته چه بوده؟"
- "چه طلب‌هایی هنوز پیگیری نشده؟"
- "یادآوری‌های امروز چیست؟"
- "آخرین یادداشت دربارهٔ سعید چه بود؟"

Every answer must state the data basis and known exclusions. If the user asks
for "sales" but only unknown inflows exist, ask whether they mean all incoming
payments or only records classified as sales.

---

## 9. Learning and data architecture

Do not start with a graph database. The product needs a graph-shaped domain
model, not necessarily graph-database operational complexity.

Start with a simple relational datastore and explicit links:

```text
Inbound message (immutable source)
  -> interpretation draft
      -> confirmed record
          -> counterparty / alias
          -> optional linked memo, task, and reminder
```

Keep these layers distinct:

- **Source message:** exact user-provided message or transcript, protected and
  governed by retention rules.
- **Interpretation:** extracted candidate fields, uncertainty, and reason for
  clarification.
- **Confirmed record:** the durable user-approved data.
- **Preference / learned pattern:** user-confirmed conventions such as a bank
  SMS pattern, unit display preference, alias, or category correction.

Learning may prefill or suggest; it may never bypass confirmation for a
financial record or an externally visible action. Design explicit correction,
deletion, retention, and audit behavior before storing real financial data.

Important technical/product safeguards to design before implementation:

- Idempotency and duplicate detection for copied/forwarded bank SMS messages.
- Exact raw-unit preservation and transparent rial/toman conversion.
- Per-user and per-record privacy settings.
- Minimal raw-content retention, encryption, access control, and deletion
  behavior.
- Clear distinction between a draft, a confirmed item, and a cancelled item.

---

## 10. WhatsApp constraints

Do not rely on users having WhatsApp Business. Users should interact through
ordinary WhatsApp.

The WhatsApp Business app's "quick replies" are saved shortcuts for the
business operator; they are not a reliable user-facing choice mechanism. The
official Business Platform can provide interactive reply buttons or lists to
ordinary WhatsApp users, but it requires an official business integration and
platform-compliant lifecycle.

Therefore the interaction standard is:

> Plain language and simple text choices are the required path. Buttons are an
> optional enhancement.

For example, the category question must accept `۱`, `یک`, `دریافت`,
`دریافت وجه`, `ثبت نکن`, and `بی‌خیال`, even if reply buttons are available.

Verify current WhatsApp policy, onboarding, template, pricing, and regional
availability before implementing outbound reminder delivery or any production
integration. Do not use unofficial WhatsApp automation as a product decision.

---

## 11. Product risks and corresponding scope decisions

| Risk | Product decision |
| --- | --- |
| Scope explosion into CRM/accounting/general AI | Keep only capture, confirm, retrieve, remind, and query. |
| Wrong unit, amount, or duplicate financial data | Preserve source, ask on ambiguity, detect duplicates, require confirmation. |
| "All deposits equal sales" reporting error | Require/edit a lightweight business meaning; disclose excluded records. |
| Privacy leaks in notifications | Make privacy per reminder; default conservative; provide pull-only mode. |
| User believes the bot is a real empathic person | Bound off-topic conversation; no emotional role-play or human claims. |
| Cost from irrelevant chat loops | Template-based bounded retry; close after the second non-answer. |
| Channel lock-in | Keep domain logic independent of WhatsApp adapter. |
| Unsupported current PoC claims | Treat commercial product direction as design-only until built and tested. |

---

## 12. Recommended now-next-later plan

### Now: validate the narrow interaction

- Prototype the chat flow with text and manually pasted SMS examples.
- Test all drafts, ambiguity prompts, correction paths, cancellation, and
  duplicate scenarios with synthetic data.
- Conduct a small concierge/design-partner test with five users. Observe actual
  messages and corrections; do not ask only for feature opinions.
- Measure: confirmed records per week, time to confirm, correction rate,
  abandoned drafts, and whether users can retrieve a prior item unaided.

### Next: make reminders safe and useful

- Add financial and non-financial reminders only after the capture/confirmation
  loop is understood.
- Test detailed, private, and pull-only delivery choices.
- Validate WhatsApp opt-in, template, timing, and notification behavior before
  enabling automatic outbound reminders.

### Later: add carefully earned capabilities

- Read-only daily view and report queries.
- A minimal optional web view for search, correction, export, privacy settings,
  and recovery; it must not replace chat capture.
- Multi-user or vertical features only after evidence shows a retained core
  workflow and a specific unmet need.

---

## 13. Decisions still required from the owner

1. Raw-message retention policy: how long may original bank SMS text and voice
   transcripts be retained, and how should deletion work?
2. First reminder delivery policy: should the first trial support only pull-only
   reminders, or opt-in private/detailed WhatsApp reminders as well?
3. Minimum classification rule: must every incoming payment be marked Sale /
   Collection / Transfer / Other at confirmation, or can it remain Unknown?
4. Definition of a "sale": cash received, invoice/order value, or both? These
   differ and must not be conflated.
5. What exact evidence should qualify a user as a design partner, and what
   privacy agreement is appropriate before real financial messages are used?

---

## 14. Instructions for the next agent

- Speak to the owner in Persian unless a higher-priority environment rule says
  otherwise. Keep this document and technical implementation documents in
  English.
- Do not restart from "what business vertical should we target?" The agreed
  segment is chat-native, low-tool users across professions.
- Do not reduce the product to accounting, or expand it into a general agent.
- Do not call the user's cultural values product feature names or branding
  decorations.
- Treat every financial claim, customer-facing message, reminder, privacy
  decision, and WhatsApp capability as consequential.
- Before coding, turn this handoff into a reviewable PRD/spec with concrete
  acceptance criteria, privacy/retention rules, state transitions, and test
  cases. Obtain owner approval before implementation.
- Treat the bale-auto/OpenClaw work as closed and unrelated. Do not touch its
  code, server, GitHub, Notion, or deployment in the course of this product
  work unless the owner explicitly asks to reopen it.
