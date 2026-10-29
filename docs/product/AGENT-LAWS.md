# Agent Laws — the agent is not a free chatbot

Owner's laws for the bale-auto agent layer (v2 plan §11/§13), enforced in
code — not prompt wishes. Every law below names where it is enforced and
which test proves it. The deterministic core owns all money truth; the
model is a tone tool behind a gate.

## 1. Role: guide first, then scoped question-support

The agent has exactly two jobs:

1. **Guide (§13):** accompany the user through the first setup messages —
   one short question at a time, buttons over typing, resumable.
2. **Question-support («پشتیبان سوال»):** answer questions about the
   product's own use and the user's **own** ledger.

It is not a companion, not a general assistant, and never a free API for
anyone's anything else (off-topic talk, «درد دل», general knowledge).

## 2. Scope gate — before any model call

`is_scoped_question()` + the dispatch in `BaleBotEngine.handle_message`
(`src/agent_layer.py`, `src/bale_bot.py`):

- The model may be invoked **only** for (a) turns inside the guide flow
  and (b) scoped questions. A message is scoped only when it carries a
  question marker **and** product vocabulary (ثبت، گزارش، طلب، تسویه،
  حذف، پلن، ماه رایگان، کد معرفی، چطور، چرا، یعنی چه…). When in doubt,
  it is **not** scoped.
- Transactions never reach the model: anything the parser can claim
  keeps the pure deterministic path, and transaction confirmations and
  reports are served as core templates verbatim (no polish).
- Off-scope chatter gets **one** fixed template — the model never
  improvises a refusal:

> من فقط برای دفتر و حساب‌وکتابت اینجام؛ بنویس «فروش ۵۰۰ هزار تومان» یا سؤالت را درباره‌ی دفترت بپرس.

## 3. Scoped answers are composed by the core, never by the model

`BaleBotEngine._scoped_answer()` composes the answer from deterministic
sources only: the user's own open credit balances, his own plan/status,
his own ledger totals, and the product facts table
(`PRODUCT_FACTS` in `src/agent_layer.py`). The model may only *rephrase*
that composed text, under the §11 verbatim-numbers guard — any altered
or dropped figure rejects the polish and the core text is sent.

When no deterministic source covers a scoped question, the user gets
one fixed template and the question is **routed to the supporter**:
stored as an open question in the panels' `support.db` and listed in
Shahram's supporter panel («❓ سوال‌های باز», closable there).

> این را نمی‌دانم؛ از پشتیبان بپرس. سؤالت را برای پشتیبان فرستادم تا جوابش را بگیری.

## 4. Data boundary — explicit, per user, own ledger only

- The model layer (`src/agent_layer.py`) receives **no** database
  handle, **no** file paths, **no** other user's data — by
  construction. Its only input is one core-composed text for the
  current user (plus flow constants).
- Scoped answers read only the asking user's own rows.
- Nobody can pull data out through the bot: there is no code path from
  a user message to a dump, a file, or another user's records.

## 5. Extraction attempts — fixed refusal, logged

A hard denylist (`extraction_kind()`) runs **before** any dispatch: a
message asking for the database/dump, other people's data, server
files/source, tokens/keys, or the system prompt is answered by one
fixed refusal and is **never sent to the model at all**:

> به دیتابیس، فایل‌های سرور یا داده‌های بقیه دسترسی ندارم و چنین چیزی نمی‌دهم. من فقط برای دفتر و حساب‌وکتاب خودت اینجام.

The refusal states the truth: the agent has no such access. Each
attempt is logged to `agent_guard_log` in the ledger DB with kind,
user id, timestamp and at most a 40-character snippet — never the full
content. The owner panel's stats show the refused-attempt count.

Weak targets (e.g. «توکن») require a request intent, and a message
carrying an amount is never flagged — a purchase line the parser
claims («خرید توکن اینترنت ۵۰ هزار») is commerce, not an attack.

## 6. Usage caps — the agent cannot be farmed

`BaleBotEngine._polish_gated()` is the only door to the model, and it
consumes from two daily caps persisted in the ledger DB
(`ConversationStore.agent_try_consume`):

- **Per user: 30 model calls/day** (guide turns included).
- **Global: 500 model calls/day** — a circuit breaker.

Both are env-tunable (`AGENT_DAILY_CAP_PER_USER`,
`AGENT_DAILY_CAP_GLOBAL`). Beyond a cap the deterministic template is
served silently — no error, no mention to the user.

## 7. No execution, ever

The agent layer runs nothing: no subprocess, no eval/exec, no shell, no
file writes. Its single network operation is the model endpoint call.
A test greps `src/agent_layer.py` for forbidden primitives
(`subprocess`, `os.system`, `os.popen`, `eval(`, `exec(`, `__import__`,
sockets, a bare `open(` outside `urlopen(`, `sqlite3`) and fails the
suite if any appears.

## Enforcement map

| Law | Enforced in | Proven by |
|---|---|---|
| Scope gate | `is_scoped_question`, fallback dispatch in `handle_message` | `tests/test_agent_laws.py` (transaction → zero model calls; off-topic → fixed template) |
| Core-only answers | `_scoped_answer`, `PRODUCT_FACTS`, numbers guard in `SoftLayer.polish` | scoped-answer tests incl. a number-altering stub |
| Unknown → supporter | `_route_question_to_support`, `open_questions` in `support.db`, supporter panel view | routing test + panel list test |
| Data boundary | `agent_layer` holds no DB/file access (module audit) | grep test (no `sqlite3`, no `open(`) |
| Refusal + log | `extraction_kind`, `AGENT_GUARD_REFUSAL` dispatch, `agent_guard_log` | refusal tests (db / prompt / others' data) |
| Caps | `_polish_gated`, `agent_try_consume` | cap tests (per-user and global) |
| No execution | module audit | grep test |
