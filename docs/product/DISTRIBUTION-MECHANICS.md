# Distribution Mechanics in the Bot (v2 plan, section 14)

Status: UNIFIED with the supporter/owner panels on branch
`gorgg/unified-distribution` (2026-10-28) — one source of truth,
`src/accounts.py`. Deploy is the owner's separate order, as always.

## What was built

`src/accounts.py` — an accounts layer in the SAME SQLite file as the
ledger (so the nightly backup covers it), wired into `BaleBotEngine`:

- An account is born at first contact, but the free FULL month starts
  at ACTIVATION (the first confirmed transaction) — a stray first
  message never burns the hook month. The daily/nightly report carries
  the countdown line («⏳ از ماه رایگانت X روز مانده»).
- Every user sees his referral code in `/start` and in «وضعیت من»
  (status: plan, free days left, banked months, plan-2 state).
- A referral code is accepted bare, inside a sentence, or as a `/start`
  parameter. Rules: once only, never self, only before the referred user
  activates.
- **Activation = the referred user's first confirmed transaction.** Only
  activated referrals count (owner's rule from the research review).
- Each activated referral banks +1 free month for the referrer (cap 6);
  the second activated referral unlocks plan 2 (guild accountant).
- All numbers are computed from facts (accounts, bot_referrals,
  transactions) — no stored counters to drift.

## Unification with the panels (2026-10-28)

- `accounts.py` is the single source of truth for identity / referral /
  plan on EVERY surface. The Telegram panels (supporter + owner) keep
  only the people directory in `support.db` and read/write through
  Accounts: same B-codes, same activation gating, same cap 6, and
  owner-panel plan changes land in the store the bot actually reads.
- Panel-defined users without a known Bale id get a provisional
  identity (`panel:<id>`) with a real B-code; when the supporter
  supplies the real Bale id, the identities are folded together
  (`Accounts.link_identity`) — referral links, plan and the activation
  anchor move with the person.
- Legacy `U…` codes from the pre-unification panels can be registered
  (`SupportStore.map_legacy_code` / `import_legacy_codes`) and keep
  resolving to the same person.
- User status is derived from facts (defined / linked / active); the
  old never-called status setter is gone.

## Deliberately not here yet

- End-of-free-month report and plan purchase flow (billing arrives with
  the owner's payment route decision).
- The onboarding guide flow (plan section 13) — separate build.

## Tests

`tests/test_distribution_mechanics.py` — code/birth, referral rules
(unknown/self/twice/second referrer), activation gating, bank cap and
free-day math, no-referral-after-activation, the free-month clock
(starts at activation, not at first contact), plus engine end-to-end
(start shows code, bare-code arrival, activation via a confirmed sale,
plan-2 unlock, status text, bad-code rejection).
`tests/test_unified_distribution.py` — cross-surface proofs: raw
referral grants nothing, activation pays exactly one month on both
surfaces, cap 6 holds across panel + bot referrals, legacy U-code
resolution, derived status, identity linking. Full suite: 150 green.
