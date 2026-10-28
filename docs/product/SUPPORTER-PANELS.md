# Distribution Layer — Supporter & Owner Telegram Panels

Status: built and tested (branch gorgg/supporter-bot). Going live needs two
BotFather tokens, entered by the owner (Tier 4).

## What exists

| Piece | File | Level |
|---|---|---|
| Supporter bot | `src/supporter_bot.py` | The local supporter only: define users, see HIS users, attach referral codes, his summary |
| Owner panel bot | `src/owner_panel_bot.py` | Owner only: global stats, all users, supporter management, plan changes |
| Registry | `src/support_store.py` | SQLite `support.db`: supporters, users, referrals |
| Telegram client | `src/tg_client.py` | Stdlib-only Bot API (long polling, inline keyboards) |

The two bots are separate on purpose: the supporter's bot physically
cannot reach owner functions, and the owner panel never mixes with the
supporter's day-to-day screen.

## Mechanics wired to the v2 plan (section 14)

- Defining a user issues his referral code and starts him on the free FULL
  month.
- A referral is recorded once, never self, never twice: +1 free month each.
- The second referral unlocks plan 2 (guild accountant, 999k) for the
  referrer — `SupportStore.plan2_unlocked`.
- Deactivating a supporter in the owner panel cuts his bot access at once.

## Run

```bash
# env: SUPPORTER_BOT_TOKEN / OWNER_BOT_TOKEN / OWNER_TELEGRAM_ID / SUPPORT_DB_PATH
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
