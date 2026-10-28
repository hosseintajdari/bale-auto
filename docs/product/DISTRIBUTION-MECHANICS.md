# Distribution Mechanics in the Bot (v2 plan, section 14)

Status: built on branch `gorgg/distribution-mechanics`, NOT deployed.
Deploy is the owner's separate order, as always.

## What was built

`src/accounts.py` — an accounts layer in the SAME SQLite file as the
ledger (so the nightly backup covers it), wired into `BaleBotEngine`:

- An account is born at first contact; the free FULL month starts then.
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

## Deliberately not here yet

- Importing supporter-registry codes (the `U…` codes in support.db) into
  the bot, so a supporter-defined user is recognised on first contact.
- End-of-free-month report and plan purchase flow (billing arrives with
  the owner's payment route decision).
- The onboarding guide flow (plan section 13) — separate build.

## Tests

`tests/test_distribution_mechanics.py` — 8 tests: code/birth, referral
rules (unknown/self/twice/second referrer), activation gating, bank cap
and free-day math, no-referral-after-activation, plus engine end-to-end
(start shows code, bare-code arrival, activation via a confirmed sale,
plan-2 unlock, status text, bad-code rejection). Full suite: 128 green.
