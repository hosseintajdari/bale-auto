"""Distribution mechanics for the Bale bot (v2 plan, section 14).

Lives in the SAME SQLite file as the ledger so the nightly backup covers
it. Everything is computed from facts, never stored as drift-prone
counters:

- An account is born at first contact; its free FULL month starts then.
- Every account has a referral code (B + hex id).
- A referral is recorded once, never self, only before activation.
- A referred user ACTIVATES at his first confirmed transaction (the
  transactions table is the source of truth). Only activated referrals
  count — the owner's rule from the research review.
- Each activated referral banks +1 free month for the referrer, cap 6.
- The second activated referral unlocks plan 2 for the referrer.
- Free period = 30 days + 30 * banked months, from account birth.
"""
import sqlite3
import time

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
                created_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS bot_referrals(
                id INTEGER PRIMARY KEY,
                referrer_id TEXT NOT NULL,
                referred_id TEXT UNIQUE NOT NULL,
                created_at INTEGER NOT NULL
            );
            """
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

    # -- status ---------------------------------------------------------------
    def free_until(self, bale_user_id):
        acc = self.get_or_create(bale_user_id)
        return acc["created_at"] + (FREE_DAYS + 30 * self.banked_months(bale_user_id)) * DAY

    def free_days_left(self, bale_user_id, now=None):
        now = int(time.time()) if now is None else now
        left = self.free_until(bale_user_id) - now
        return max(0, -(-left // DAY))

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
            f"روزهای رایگان باقی‌مانده: {s['free_days_left']}",
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
