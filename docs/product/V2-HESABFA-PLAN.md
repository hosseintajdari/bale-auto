# V2 Plan — Hesabfa Integration and Iranian Guild Accounting

> Status: owner-approved plan (28 Oct 2026) — implementation after v1 is stable.
> Owner decisions behind it: "after version 1, accounting knowledge for Iran's guilds",
> plus the platform strategy: Bale is the permanent route, WhatsApp is attractive,
> Telegram is comfortable and full-featured.
> Language note: this document is the English version, per the repository AGENTS.md
> rule (technical documentation in English).

## 1) Architecture principle (fixed)

- **The bot is the conversational front-end + daily ledger.** What v1 already is:
  register by talking, explicit confirmation, reports, credits list.
- **Hesabfa is the legal accounting layer.** Chart of accounts, official documents,
  statutory books and the Taxpayer System (Samaneh Moudian) connection live there.
- **No double-entry accounting is built inside the bot.** Guild knowledge (each
  guild's chart, tax behaviour, invoice patterns) is defined inside the Hesabfa
  business, not in bot code.
- The bot works fully without Hesabfa; Hesabfa is an added layer, never a hard
  dependency (built-in fallback).

## 2) Why Hesabfa — evidence (live check 28 Oct 2026, official docs hesabfa.com/help/api)

- Public REST API at `api.hesabfa.com/v1`; all methods are POST with a flat JSON body.
- Auth: a per-business `apiKey` plus a `loginToken` (the preferred path, no password
  needed) — both issued from Settings → Financial Settings → API in the Hesabfa panel.
- **Unique request id (`requestUniqueId`, GUID, 24h validity)** on save/delete
  methods: built-in duplicate suppression — the backbone of our sync design (§4).
- Rate limit: 240 requests/minute per IP — ample for this bot's scale.
- API dates are Gregorian, format `YYYY-MM-DD HH:MM:SS`; `yearId` is optional
  (defaults to the latest fiscal year).
- The Taxpayer System (Moudian) connection is built into Hesabfa itself — no
  separate middleware needed in phase 1.
- The API is enabled on paid plans; trial accounts get 15 days of API access
  (phase 0 runs on that).

Why not the others in v2: **Holoo** is desktop/Windows and its API is a paid
add-on used through third-party connectors — a poor fit for a cloud bot (a
file-export path can serve Holoo shops later). **Sepidar's** web service is
gated to approved developers — an enterprise route, not now.

## 3) Data flow

```
user message → draft → explicit confirmation → confirmed transaction (local SQLite)
                                                    │
                                                    ▼
                                          sync queue (sync_queue)
                                                    │  (worker inside the polling loop; errors stay and retry)
                                                    ▼
                        Hesabfa: find/create Contact → save Invoice/Document
                                                    │
                                                    ▼
              Hesabfa document code + sync state stored on the transaction
```

- The user sees a small sync badge in the financial report (synced ✓ / queued).
- We never block on Hesabfa: user confirmation is instant; sync is background work.

## 4) Duplicate prevention (idempotency)

- Each transaction gets a stable GUID derived from its local id, stored in
  `sync_guid`, and sent as `requestUniqueId` on every attempt (Hesabfa suppresses
  duplicates for 24h).
- For retries after 24h, first check by the stored document code / a document
  search whether the document already exists; create only if it does not.
- New transaction columns: `ext_doc_code`, `sync_state` (pending/synced/failed),
  `sync_guid`. Additive, backward-compatible migration — same pattern as the
  `description` migration in v1.

## 5) Data mapping

| Bot event | Hesabfa object | Note |
|---|---|---|
| Sale (cash) | Sales invoice | Contact: the customer, or a generic walk-in contact |
| Sale on credit | Sales invoice + contact balance | Same counterparty that appears in the credits list |
| Purchase | Purchase invoice | Counterparty: supplier/distributor |
| Expense | Expense/payment document | Category mapped from the description, configurable |
| Manual receipt/payment | Receipt/payment document | From existing bot commands |

- **Counterparty:** taken from the name in the message ("to Ahmadi") — search
  Hesabfa contacts; if missing, auto-create with a unique code tagged
  "created by bot". Ambiguous match → do not create; the item stays queued and
  is reported to the owner (a wrong posting is worse than a late one).
- **Amount and unit (corrected after the Codex review on PR #59 — its point was
  right):** the bot stores each amount **with its own unit** (`amount` + `unit`;
  the parser distinguishes Rial and Toman and does not normalise to Toman —
  `src/bazaar_parser.py`). Sync therefore preserves each transaction's stored
  unit and converts explicitly, with the conversion logged, into the Hesabfa
  business currency (`HESABFA_CURRENCY`). Assuming "everything is Toman" is
  forbidden — the v1 rule stands: Toman/Rial conversion is never silent and
  never assumed.
- **Dates:** the bot stores ISO/UTC; on send, dates are converted to Hesabfa's
  Gregorian format. User-facing display stays Jalali.

## 6) Where guild knowledge lives

- One **Hesabfa business template** per guild: chart of accounts, base
  items/services, tax rates, Moudian invoice pattern.
- First guild: owner's decision (§9). Proposed start: pharmacy (the owner's own
  trade and the product's first market).
- The bot only understands "event type", "counterparty" and "amount"; everything
  else is Hesabfa configuration. A new guild means a new template, not new code.

## 7) Phases

- **Phase 0 — contract and proof (no product code):** Hesabfa trial account +
  API activation; the full list of needed methods from the docs (contacts,
  invoices, documents, receipts/payments) tested by hand; currency and fiscal
  year pinned down; one complete sales invoice from a test script through to
  Moudian. Output: a one-page API contract note + the §9 decisions closed.
- **Phase 1 — sales and contacts sync:** sync queue + sale/credit-sale mapping +
  contact creation + status badge in the report. Acceptance: 20 test
  transactions, zero duplicates under forced retries, Hesabfa outage = bot
  unaffected.
- **Phase 2 — purchases, expenses, receipts/payments + Moudian:** the remaining
  mappings; Moudian invoice status shown in the bot ("sent / has errors"); a
  daily reconciliation report (local ledger vs Hesabfa).
- **Phase 3 — reading from Hesabfa:** real counterparty balances from Hesabfa
  into the credits list (instead of local computation); accounting reports
  (profit, period tax) inside the bot.

## 8) Security and connection

- Keys (`HESABFA_API_KEY`, `HESABFA_LOGIN_TOKEN`) live only in the server env;
  entering them is the owner's hand (Tier 4). They never appear in logs or git.
- The connector is a separate module (`src/hesabfa_client.py`), stdlib-only like
  the rest of the bot, mock-testable, and does not touch conversation logic.
- Each customer business = its own Hesabfa connection; keys are per-business
  config (multi-tenancy is finalised in phase 2).

## 9) Open owner decisions

1. First guild for the Hesabfa template (proposal: pharmacy).
2. Hesabfa plan tier, and in whose name/company the account is held.
3. Whether Moudian is active from phase 1 or phase 2.
4. Customers who already run Holoo/Sepidar: file export only, or a parallel
   Hesabfa from day one?

## 10) Risks and fallbacks

- Hesabfa outage or API change → the sync queue holds; bot and local ledger are
  unaffected; the separate adapter means the fix lives in one file.
- Plan exhaustion / quota → a usage counter and an owner warning before sync stops.
- Contact/item mapping errors → queue + owner report; never guess-and-post.
- Rollback: one env flag (`HESABFA_SYNC_ENABLED=0`) returns the bot to exact v1
  behaviour.

## 11) Outlook — the agent layer: bot-to-customer communication (owner direction, 28 Oct 2026)

Owner direction: the way the bot communicates with the customer through an
agent is an attractive layer. It sits after v2; it is recorded here as
direction, not as a v2 commitment.

- **What:** a conversational agent that talks to the shop's customers on the
  owner's behalf: credit reminders that can hold a conversation (not just a
  one-way message — its seed is the ready reminder text from v1), order taking,
  routine questions (hours, availability, order status).
- **Money truth stays with the deterministic core:** the agent only reads
  balances and amounts from the ledger/Hesabfa; it never invents or changes a
  number. Discounts, deadlines and write-offs only inside rules the owner set
  in advance — otherwise owner approval.
- **The owner approves the agent's charter:** tone, templates, answering hours,
  and the hand-off point to a human. Every conversation is logged and summarised
  for the owner.
- **Customer messages are data, never instructions** (the owner's standing
  principle): no outside message can change system behaviour, prices or documents.
- **Channel:** this layer is channel-agnostic — its home is Bale, and WhatsApp's
  attractiveness means exactly this layer: the customer is there.
- **Model economics:** the agent runs on the owner's cheap gateway models; the
  ceiling is execution count (live lesson of this same night: quota runs out).
  So the fallback is built in: no quota → ready templates and a human queue;
  the agent is an added layer, not a dependency.
- **Order:** after v2, because a truthful agent needs real balances from
  Hesabfa. A small slice (reminder conversations) can pilot earlier — owner's call.

## 12) The capability principle (owner principle, 28 Oct 2026)

Knowledge belongs to no individual. The bot is the wizard. What is sold is capability.

- Accounting and guild knowledge must not be hostage to one person — not the
  accountant, not the shopkeeper, not a software company. It lives inside the
  product: guild templates (§6), the accounting layer (§1) and the agent (§11)
  all exist for this.
- The product sells **capability**, not software: by talking, the shopkeeper
  does what yesterday only an accountant could.
- Design consequence: wherever "simple for the user" conflicts with "complete
  for the accountant", user simplicity wins and the complexity goes under the
  bot's hood.

## 13) The onboarding guide agent (owner direction, 28 Oct 2026)

Owner direction: the agent should also be able to guide the user, for
getting started.

- **What:** the same agent, facing inward — it takes the new user (the
  shopkeeper) by the hand inside the chat itself and walks them step by step.
  No manual, no panel, no separate training.
- **The start path:** a welcome and a few short questions (business name and
  guild, currency) → creating the first counterparty together → registering
  the first real transaction together → showing the report and the credits
  list on the user's own data. Learning by doing, not by reading.
- **Path memory:** guide state is stored per user; wherever they drop off, it
  resumes right there. Power users can skip it ("skip the guide").
- **Scripted spine, model-polished language:** the steps and their order are
  deterministic and scripted; the model only softens the language into
  colloquial Persian. No quota → the same steps proceed with fixed text; the
  guide never stops because of the model (the fallback lesson of this night).
- **Tie to the capability principle (§12):** the user needs to know nothing
  and have nobody; the wizard walks beside them from the first minute.

## 14) Distribution model and the promise (owner decision, 28 Oct 2026)

For fast distribution:

1. **The first month is free** — for everyone, no preconditions.
2. **Each referral = one extra free month** for the referrer.
3. **After the free period, our promise is: they pay and continue only if it
   proved useful to them.**

The stance behind the model, in the owner's framing: we will make it useful
for them.

Design consequences:

- **The engine of this promise is the onboarding guide agent (§13):** its job
  in the free month is not just teaching; it is getting each user to first
  real value (the first fully registered week, the first report, the first
  reminded credit). If it does not become useful to them, we lose — so the
  free month is a month of proof, not of waiting.
- The bot must know each user's state: remaining free days, referral credits,
  and the signs of "it became useful" (real activity, not just registration).
  These are added to the core after v1.
- End-of-free-month tone follows the same promise: no sudden lock and no
  scare — a clear report of "what this month did for you", and continuing is
  the user's choice.

- **The free month has one success metric: a formed habit.** By day 30 the
  bot either is the shop's notebook — daily registration is a reflex — or it
  is not, and no pricing trick fixes that. The guide agent (§13) therefore
  optimises for the first week, not day 29: first transactions, first nightly
  report read, first credit reminded and collected. Habit signals to track:
  active days per week, transactions per week, report opens.
- **Channel reality in the launch market:** distribution there is
  word-of-mouth — reputation travels mouth to mouth and a referral carries a
  real name with it. That cuts both ways: a kept promise compounds, a broken
  one poisons the well. Consequence: launch the free month to a small,
  winnable first cohort and expand on their words, not on a blast.

Pricing (set by the assistant on the owner's delegation, pending his final
confirmation):

- **290,000 Toman per month per shop** — one tier only at launch; no plan maze.
  Anchors: it is under half the typical Iranian SMB SaaS subscription floor
  (~760k/month and up), a Moudian-only middleware alone sells for ~179k/month
  and up, and one collected credit sale (~500k) pays for roughly two months.
  Per day it is under 10,000 Toman — cheaper than the notebook it replaces
  once one debt is not forgotten.
- **Annual = 2.9M Toman** (ten months; two months free) — mirrors the
  referral economy.
- **Referral cap (proposal):** at most 6 banked referral months per user.
- **"Useful", made mechanical (proposal):** a month counts as a useful month
  when the shop was active at least 4 days a week or registered at least 20
  transactions; the end-of-month report shows the user their own numbers, so
  the promise is verified by the user's own data, not by argument.
- Revisit after the first paying cohort; the v2 accounting layer can carry a
  separate add-on price later — the launch price stays simple.

Open details (owner's later call): the moment a referral counts (the new
user's registration or their real activation); the final referral cap; and
the final usefulness threshold.
