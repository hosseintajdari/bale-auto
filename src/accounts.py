"""Distribution mechanics for the Bale bot (v2 plan, section 14).

Lives in the SAME SQLite file as the ledger so the nightly backup covers
it. Everything is computed from facts, never stored as drift-prone
counters:

- An account is born at first contact, but its free FULL month does NOT
  start then: the clock starts at ACTIVATION (first confirmed
  transaction), so a stray first message never burns the hook month.
  Before activation the full free period is still ahead of the user.
- Every account has a referral code (B + hex id).
- A referral is recorded once, never self, only before activation.
- A referred user ACTIVATES at his first confirmed transaction (the
  transactions table is the source of truth). Only activated referrals
  count — the owner's rule from the research review.
- Each activated referral banks +1 free month for the referrer, cap 6.
- The second activated referral unlocks plan 2 for the referrer.
- Free period = 30 days + 30 * banked months, counted from activation.

This module is the SINGLE source of truth for identity / referral /
plan across every surface (the Bale bot and the Telegram supporter /
owner panels). The panels keep only the people directory (names,
shops, phones) and read everything else through here.
"""
import sqlite3
import time
from datetime import datetime, timezone

DAY = 86400
FREE_DAYS = 30
BANK_CAP = 6
PLAN_NAMES = {"free_full": "ماه رایگان (فول)", "ledger_499": "دفتر ۴۹۹",
              "accountant_999": "حسابدار صنف ۹۹۹", "agent_1099": "ارتباطی ۱٬۰۹۹"}


class Accounts:
    def __init__(self, path):
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(
            """
            CREATE TABLE IF NOT EXISTS accounts(
                bale_user_id TEXT PRIMARY KEY,
                referral_code TEXT UNIQUE NOT NULL,
                referred_by TEXT,
                plan TEXT NOT NULL DEFAULT 'free_full',
                created_at INTEGER NOT NULL,
                activated_at INTEGER
            );
            CREATE TABLE IF NOT EXISTS bot_referrals(
                id INTEGER PRIMARY KEY,
                referrer_id TEXT NOT NULL,
                referred_id TEXT UNIQUE NOT NULL,
                created_at INTEGER NOT NULL
            );
            """
        )
        cols = [r[1] for r in self.db.execute("PRAGMA table_info(accounts)")]
        if "activated_at" not in cols:
            self.db.execute("ALTER TABLE accounts ADD COLUMN activated_at INTEGER")
        if "trial_end_report_sent" not in cols:
            self.db.execute(
                "ALTER TABLE accounts ADD COLUMN trial_end_report_sent INTEGER NOT NULL DEFAULT 0"
            )
        self.db.commit()

    # -- accounts ---------------------------------------------------------
    def get_or_create(self, bale_user_id):
        row = self.db.execute(
            "SELECT * FROM accounts WHERE bale_user_id=?", (str(bale_user_id),)
        ).fetchone()
        if row:
            return dict(row)
        cur = self.db.execute(
            "INSERT INTO accounts(bale_user_id, referral_code, created_at) VALUES(?,?,?)",
            (str(bale_user_id), "PENDING", int(time.time())),
        )
        code = "B" + format(cur.lastrowid, "x").upper().zfill(4)
        self.db.execute(
            "UPDATE accounts SET referral_code=? WHERE bale_user_id=?",
            (code, str(bale_user_id)),
        )
        self.db.commit()
        return self.get_or_create(bale_user_id)

    def by_code(self, code):
        row = self.db.execute(
            "SELECT * FROM accounts WHERE referral_code=?", (code.strip().upper(),)
        ).fetchone()
        return dict(row) if row else None

    def set_plan(self, bale_user_id, plan):
        self.db.execute(
            "UPDATE accounts SET plan=? WHERE bale_user_id=?", (plan, str(bale_user_id))
        )
        self.db.commit()

    # -- referrals ----------------------------------------------------------
    def record_referral(self, referrer_code, referred_user_id):
        """Link a new account to its referrer. Once, never self, and only
        while the referred account has not activated yet."""
        ref = self.by_code(referrer_code)
        referred = self.get_or_create(referred_user_id)
        if not ref or ref["bale_user_id"] == referred["bale_user_id"]:
            return None
        if referred["referred_by"]:
            return None
        if self.is_activated(referred["bale_user_id"]):
            return None
        try:
            self.db.execute(
                "INSERT INTO bot_referrals(referrer_id, referred_id, created_at) VALUES(?,?,?)",
                (ref["bale_user_id"], referred["bale_user_id"], int(time.time())),
            )
            self.db.execute(
                "UPDATE accounts SET referred_by=? WHERE bale_user_id=?",
                (ref["bale_user_id"], referred["bale_user_id"]),
            )
            self.db.commit()
        except sqlite3.IntegrityError:
            return None
        return ref

    def is_activated(self, bale_user_id):
        """Activation = at least one confirmed transaction in the ledger."""
        try:
            row = self.db.execute(
                "SELECT COUNT(*) c FROM transactions WHERE user_id=?", (str(bale_user_id),)
            ).fetchone()
        except sqlite3.OperationalError:
            return False
        return row["c"] > 0

    def activated_referrals(self, bale_user_id):
        rows = self.db.execute(
            "SELECT referred_id FROM bot_referrals WHERE referrer_id=?", (str(bale_user_id),)
        ).fetchall()
        return sum(1 for r in rows if self.is_activated(r["referred_id"]))

    def banked_months(self, bale_user_id):
        return min(BANK_CAP, self.activated_referrals(bale_user_id))

    def plan2_unlocked(self, bale_user_id):
        return self.activated_referrals(bale_user_id) >= 2

    # -- activation clock ---------------------------------------------------
    def activation_anchor(self, bale_user_id):
        """Epoch when this account's free-month clock started, or None if
        it has not activated yet. Anchored lazily: the first time an
        account that already has confirmed transactions is observed, the
        timestamp of its FIRST confirmed transaction is stored as its
        activation time — never the observation moment, so the trial
        window includes the activity that activated the user."""
        acc = self.get_or_create(bale_user_id)
        if acc["activated_at"]:
            return acc["activated_at"]
        if self.is_activated(bale_user_id):
            first = self._first_transaction_epoch(bale_user_id)
            anchor = first if first is not None else int(time.time())
            self.db.execute(
                "UPDATE accounts SET activated_at=? WHERE bale_user_id=?",
                (anchor, str(bale_user_id)),
            )
            self.db.commit()
            return anchor
        return None

    def _first_transaction_epoch(self, bale_user_id):
        """Epoch of the user's earliest non-voided transaction, or None
        when there is none (or the ledger has no usable timestamp)."""
        try:
            row = self.db.execute(
                "SELECT created_at FROM transactions WHERE user_id=? AND voided=0 "
                "ORDER BY created_at ASC LIMIT 1",
                (str(bale_user_id),),
            ).fetchone()
        except sqlite3.OperationalError:
            return None
        if row is None or not row[0]:
            return None
        try:
            created = datetime.fromisoformat(row[0])
        except ValueError:
            return None
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        return int(created.timestamp())

    # -- identity linking ---------------------------------------------------
    def link_identity(self, old_id, new_id):
        """Fold a provisional identity (e.g. a panel-created "panel:<n>"
        account) into the person's real Bale account once it is known.

        Referral links, the referrer pointer and the activation anchor
        move with the identity. If the real account does not exist yet,
        the provisional row is simply renamed. Returns the surviving
        account dict.
        """
        old_id, new_id = str(old_id), str(new_id)
        if old_id == new_id:
            return self.get_or_create(new_id)
        old = self.db.execute(
            "SELECT * FROM accounts WHERE bale_user_id=?", (old_id,)
        ).fetchone()
        if old is None:
            return self.get_or_create(new_id)
        new = self.db.execute(
            "SELECT * FROM accounts WHERE bale_user_id=?", (new_id,)
        ).fetchone()
        if new is None:
            self.db.execute(
                "UPDATE accounts SET bale_user_id=? WHERE bale_user_id=?", (new_id, old_id)
            )
            self.db.execute(
                "UPDATE bot_referrals SET referrer_id=? WHERE referrer_id=?", (new_id, old_id)
            )
            self.db.execute(
                "UPDATE bot_referrals SET referred_id=? WHERE referred_id=?", (new_id, old_id)
            )
            self.db.execute(
                "UPDATE accounts SET referred_by=? WHERE referred_by=?", (new_id, old_id)
            )
            self.db.commit()
            return self.get_or_create(new_id)
        # Both exist: move old's outgoing referral links to new, skipping
        # any referred user already linked from new (UNIQUE constraint).
        rows = self.db.execute(
            "SELECT referred_id FROM bot_referrals WHERE referrer_id=?", (old_id,)
        ).fetchall()
        for r in rows:
            try:
                self.db.execute(
                    "UPDATE bot_referrals SET referrer_id=? WHERE referrer_id=? AND referred_id=?",
                    (new_id, old_id, r["referred_id"]),
                )
            except sqlite3.IntegrityError:
                self.db.execute(
                    "DELETE FROM bot_referrals WHERE referrer_id=? AND referred_id=?",
                    (old_id, r["referred_id"]),
                )
        self.db.execute("DELETE FROM bot_referrals WHERE referrer_id=?", (old_id,))
        self.db.execute("DELETE FROM bot_referrals WHERE referred_id=?", (old_id,))
        if not new["referred_by"] and old["referred_by"]:
            self.db.execute(
                "UPDATE accounts SET referred_by=? WHERE bale_user_id=?",
                (old["referred_by"], new_id),
            )
            self.db.execute(
                "INSERT OR IGNORE INTO bot_referrals(referrer_id, referred_id, created_at) VALUES(?,?,?)",
                (old["referred_by"], new_id, int(time.time())),
            )
        if new["plan"] == "free_full" and old["plan"] != "free_full":
            self.db.execute(
                "UPDATE accounts SET plan=? WHERE bale_user_id=?",
                (old["plan"], new_id),
            )
        if old["activated_at"] and (not new["activated_at"] or old["activated_at"] < new["activated_at"]):
            self.db.execute(
                "UPDATE accounts SET activated_at=? WHERE bale_user_id=?",
                (old["activated_at"], new_id),
            )
        self.db.execute("DELETE FROM accounts WHERE bale_user_id=?", (old_id,))
        self.db.commit()
        return self.get_or_create(new_id)

    # -- status ---------------------------------------------------------------
    def free_until(self, bale_user_id):
        """Epoch when the free period ends, or None while the clock has
        not started yet (account not activated)."""
        anchor = self.activation_anchor(bale_user_id)
        if anchor is None:
            return None
        return anchor + (FREE_DAYS + 30 * self.banked_months(bale_user_id)) * DAY

    def free_days_left(self, bale_user_id, now=None):
        now = int(time.time()) if now is None else now
        until = self.free_until(bale_user_id)
        if until is None:
            # Clock not started: the whole free period is still ahead.
            return FREE_DAYS + 30 * self.banked_months(bale_user_id)
        left = until - now
        return max(0, -(-left // DAY))

    # -- trial end ----------------------------------------------------------
    def trial_end_report_pending(self, bale_user_id, now=None):
        """True when the free period has ended, the plan is still the
        free one, and the one-time end-of-free-month report has not
        been sent yet. Accounts the owner already moved to a paid plan
        never get the report; unactivated accounts have no clock, so
        their trial never "ends"."""
        acc = self.get_or_create(bale_user_id)
        if acc["plan"] != "free_full":
            return False
        if acc.get("trial_end_report_sent"):
            return False
        # Initialize the anchor here too: an account whose clock was
        # never observed (no nightly report ran since activation) must
        # still get its one-time report on the first run after expiry,
        # not a night late.
        if self.activation_anchor(bale_user_id) is None:
            return False
        until = self.free_until(bale_user_id)
        if until is None:
            return False
        now = int(time.time()) if now is None else now
        return now >= until

    def mark_trial_end_report_sent(self, bale_user_id):
        self.db.execute(
            "UPDATE accounts SET trial_end_report_sent=1 WHERE bale_user_id=?",
            (str(bale_user_id),),
        )
        self.db.commit()

    def status(self, bale_user_id, now=None):
        acc = self.get_or_create(bale_user_id)
        return {
            "code": acc["referral_code"],
            "plan": acc["plan"],
            "plan_name": PLAN_NAMES.get(acc["plan"], acc["plan"]),
            "free_days_left": self.free_days_left(bale_user_id, now),
            "banked_months": self.banked_months(bale_user_id),
            "activated_referrals": self.activated_referrals(bale_user_id),
            "plan2_unlocked": self.plan2_unlocked(bale_user_id),
            "activated": self.is_activated(bale_user_id),
        }

    def status_text(self, bale_user_id, now=None):
        s = self.status(bale_user_id, now)
        lines = [
            "📊 وضعیت تو",
            f"پلن: {s['plan_name']}",
            f"روزهای رایگان باقی‌مانده: {s['free_days_left']}" + ("" if s["activated"] else " (ماه رایگان از اولین تراکنشت شروع می‌شود)"),
            f"کد معرفی تو: {s['code']}",
            f"معرفی‌های فعال‌شده: {s['activated_referrals']} (ماه رایگان ذخیره: {s['banked_months']})",
        ]
        if s["plan2_unlocked"]:
            lines.append("🎉 پلن ۲ (حسابدار صنف) برایت باز شده.")
        else:
            left = 2 - s["activated_referrals"]
            lines.append(f"برای بازشدن پلن ۲ (حسابدار صنف)، {left} معرفیِ فعال دیگر لازم است.")
        lines.append("هر کس با کد تو بیاید و اولین تراکنشش را ثبت کند، یک ماه رایگان به تو می‌رسد.")
        return chr(10).join(lines)
