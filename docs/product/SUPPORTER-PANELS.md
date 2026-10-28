# Distribution Layer — Supporter & Owner Telegram Panels

Status: built and tested; UNIFIED with the bot's distribution mechanics
(2026-10-28, branch `gorgg/unified-distribution`). Going live needs the
BotFather tokens, entered by the owner (Tier 4).

## What exists

| Piece | File | Level |
|---|---|---|
| Supporter bot | `src/supporter_bot.py` | The local supporter only: define users, see HIS users, attach referral codes, his summary |
| Owner panel bot | `src/owner_panel_bot.py` | Owner only: global stats, all users, supporter management, plan changes |
| Registry | `src/support_store.py` | SQLite `support.db`: supporters + people directory + legacy code map |
| Truth store | `src/accounts.py` | Identity / referral / plan — in the ledger DB, shared with the Bale bot |
| Telegram client | `src/tg_client.py` | Stdlib-only Bot API (long polling, inline keyboards) |

The two bots are separate on purpose: the supporter's bot physically
cannot reach owner functions, and the owner panel never mixes with the
supporter's day-to-day screen.

## Unification — one source of truth

The panels do NOT keep their own referral math. `SupportStore` reads
and writes identity/referral/plan through `Accounts` (ledger DB), so
every surface agrees:

- Defining a user issues his **B-code** (the same code the Bale bot
  shows him) and starts him on the free FULL month (the clock starts
  at his first confirmed transaction).
- A referral link grants nothing by itself: it pays +1 banked free
  month (cap 6) only when the referred user ACTIVATES (first
  confirmed transaction). The second activated referral unlocks
  plan 2 — identical numbers in the bot's «وضعیت من», the supporter
  panel and the owner panel.
- Owner-panel plan changes write through to Accounts — the store the
  bot reads — so they take effect in the product itself.
- User status is derived from facts (defined / Bale-linked /
  activated); there is no status setter.
- Legacy `U…` codes issued before the unification can be mapped to
  their owners (`map_legacy_code`) and keep working as referral codes.

## Run

```bash
# env: SUPPORTER_BOT_TOKEN / OWNER_BOT_TOKEN / OWNER_TELEGRAM_ID
#      SUPPORT_DB_PATH / LEDGER_DB_PATH (the live ledger, for Accounts)
python3 src/supporter_bot.py
python3 src/owner_panel_bot.py
```

Service units: `deploy/supporter-bot.service.example`,
`deploy/owner-panel-bot.service.example`.

First step after deploy: the owner defines the supporter in the owner
panel (telegram id + name); the supporter then opens his bot and starts
defining users. Nothing else is needed from him — tracking, credits and
unlocks are automatic, per the owner's "it must not be hard for the
supporter" rule.
