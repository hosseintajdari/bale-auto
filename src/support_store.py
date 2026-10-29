"""Supporter / user registry for the distribution layer.

UNIFIED DESIGN (2026-10-28): identity, referral and plan truth lives in
ONE place — src/accounts.py (the Accounts table in the ledger DB), which
the Bale bot itself reads and writes. This store keeps only what the
panels own: the supporters table and the people directory (names,
shops, guilds, phones) plus the link from each directory row to its
Bale identity.

Consequences of the unification:
- Referral codes are the bot's B-codes everywhere. Legacy U-codes from
  the pre-unification panels can be registered in `legacy_codes` and
  keep resolving to the same person (import/mapping path).
- A referral counts ONLY when the referred user activates (first
  confirmed transaction) — the owner's settled rule. Raw links grant
  nothing; each activated referral banks +1 free month, cap 6; the
  second activated referral unlocks plan 2. All of that is computed by
  Accounts from facts, identically on every surface.
- Plan changes made in the owner panel write through to Accounts, the
  store the bot actually reads.
- User status is DERIVED from facts (directory-only / Bale-linked /
  activated); there is deliberately no status setter.

A panel-defined user whose real Bale id is not yet known gets a
provisional Accounts identity "panel:<row id>" so he has a real B-code
from day one; when the supporter supplies the real Bale id, the
provisional identity is folded into it (Accounts.link_identity).
"""
import os
import sqlite3
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from accounts import Accounts


def _now():
    return int(time.time())


class SupportStore:
    def __init__(self, path, ledger_path=None):
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(
            """
            CREATE TABLE IF NOT EXISTS supporters(
                id INTEGER PRIMARY KEY,
                telegram_id INTEGER UNIQUE NOT NULL,
                name TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                created_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS users(
                id INTEGER PRIMARY KEY,
                supporter_id INTEGER NOT NULL REFERENCES supporters(id),
                full_name TEXT NOT NULL,
                shop_name TEXT NOT NULL DEFAULT '',
                guild TEXT NOT NULL DEFAULT '',
                phone TEXT NOT NULL DEFAULT '',
                bale_user_id TEXT NOT NULL DEFAULT '',
                created_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS legacy_codes(
                code TEXT PRIMARY KEY,
                bale_user_id TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS open_questions(
                id INTEGER PRIMARY KEY,
                bale_user_id TEXT NOT NULL,
                name TEXT NOT NULL DEFAULT '',
                question TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'open',
                closed_by INTEGER
            );
            """
        )
        self.db.commit()
        if ledger_path is None:
            ledger_path = f"{path}.ledger.db"
        self.accounts = Accounts(ledger_path)

    # ----- supporters -------------------------------------------------
    def add_supporter(self, telegram_id, name):
        cur = self.db.execute(
            "INSERT OR IGNORE INTO supporters(telegram_id, name, created_at) VALUES(?,?,?)",
            (int(telegram_id), name, _now()),
        )
        self.db.commit()
        return self.get_supporter_by_tg(telegram_id)

    def get_supporter_by_tg(self, telegram_id):
        row = self.db.execute(
            "SELECT * FROM supporters WHERE telegram_id=?", (int(telegram_id),)
        ).fetchone()
        return dict(row) if row else None

    def list_supporters(self):
        rows = self.db.execute("SELECT * FROM supporters ORDER BY id").fetchall()
        return [dict(r) for r in rows]

    def set_supporter_active(self, supporter_id, active):
        self.db.execute(
            "UPDATE supporters SET active=? WHERE id=?",
            (1 if active else 0, int(supporter_id)),
        )
        self.db.commit()

    # ----- users (people directory; truth delegated to Accounts) -------
    def add_user(self, supporter_id, full_name, shop_name="", guild="", phone="", bale_ref=""):
        cur = self.db.execute(
            "INSERT INTO users(supporter_id, full_name, shop_name, guild, phone, bale_user_id,"
            " created_at) VALUES(?,?,?,?,?,?,?)",
            (int(supporter_id), full_name, shop_name, guild, phone, "", _now()),
        )
        uid = cur.lastrowid
        bale_id = (bale_ref or "").strip() or f"panel:{uid}"
        self.accounts.get_or_create(bale_id)
        self.db.execute("UPDATE users SET bale_user_id=? WHERE id=?", (bale_id, uid))
        self.db.commit()
        return self.get_user(uid)

    def _enrich(self, row):
        """Attach the Accounts truth (code, plan, derived status)."""
        if row is None:
            return None
        u = dict(row)
        bale_id = u["bale_user_id"]
        acc = self.accounts.get_or_create(bale_id)
        u["referral_code"] = acc["referral_code"]
        u["plan"] = acc["plan"]
        if self.accounts.is_activated(bale_id):
            u["status"] = "active"
        elif bale_id.startswith("panel:"):
            u["status"] = "defined"
        else:
            u["status"] = "linked"
        return u

    def get_user(self, user_id):
        row = self.db.execute("SELECT * FROM users WHERE id=?", (int(user_id),)).fetchone()
        return self._enrich(row)

    def get_user_by_bale_id(self, bale_user_id):
        row = self.db.execute(
            "SELECT * FROM users WHERE bale_user_id=?", (str(bale_user_id),)
        ).fetchone()
        return self._enrich(row)

    def get_user_by_code(self, code):
        code = (code or "").strip().upper()
        acc = self.accounts.by_code(code)
        if acc:
            return self.get_user_by_bale_id(acc["bale_user_id"])
        row = self.db.execute(
            "SELECT bale_user_id FROM legacy_codes WHERE code=?", (code,)
        ).fetchone()
        if row:
            return self.get_user_by_bale_id(row["bale_user_id"])
        return None

    def list_users(self, supporter_id=None):
        if supporter_id is None:
            rows = self.db.execute("SELECT * FROM users ORDER BY id").fetchall()
        else:
            rows = self.db.execute(
                "SELECT * FROM users WHERE supporter_id=? ORDER BY id", (int(supporter_id),)
            ).fetchall()
        return [self._enrich(r) for r in rows]

    def set_user_plan(self, user_id, plan):
        """Owner-panel plan change — lands in Accounts, the store the
        Bale bot reads, so it takes effect in the product itself."""
        u = self.get_user(user_id)
        if u:
            self.accounts.set_plan(u["bale_user_id"], plan)

    def user_needs_bale_link(self, user):
        return bool(user) and str(user["bale_user_id"]).startswith("panel:")

    def link_user_bale_id(self, user_id, bale_id):
        """Attach the person's real Bale id: the provisional panel
        identity is folded into the real account (referral links, plan
        and activation anchor move with it)."""
        u = self.get_user(user_id)
        if not u:
            return None
        bale_id = str(bale_id).strip()
        if not bale_id:
            return u
        self.accounts.link_identity(u["bale_user_id"], bale_id)
        self.db.execute(
            "UPDATE users SET bale_user_id=? WHERE id=?", (bale_id, int(user_id))
        )
        self.db.commit()
        return self.get_user(user_id)

    # ----- legacy U-code import / mapping -------------------------------
    def map_legacy_code(self, code, user_id):
        """Register a pre-unification U-code for a directory user so old
        printed/shared codes keep resolving to the same person."""
        u = self.get_user(user_id)
        if not u:
            return False
        self.db.execute(
            "INSERT OR REPLACE INTO legacy_codes(code, bale_user_id) VALUES(?,?)",
            ((code or "").strip().upper(), u["bale_user_id"]),
        )
        self.db.commit()
        return True

    def import_legacy_codes(self, mapping):
        """Bulk form of map_legacy_code: {U-code: directory user id}."""
        done = 0
        for code, uid in mapping.items():
            if self.map_legacy_code(code, uid):
                done += 1
        return done

    # ----- referrals (delegated to Accounts — the owner's rule) ----------
    def _resolve_referrer_bale_id(self, code):
        code = (code or "").strip().upper()
        acc = self.accounts.by_code(code)
        if acc:
            return acc["bale_user_id"]
        row = self.db.execute(
            "SELECT bale_user_id FROM legacy_codes WHERE code=?", (code,)
        ).fetchone()
        return row["bale_user_id"] if row else None

    def record_referral(self, referrer_code, referred_user_id):
        """Link a referred user to whoever brought him (B-code or a
        mapped legacy U-code). The link itself grants NOTHING — it pays
        out only when the referred user activates (Accounts rule).

        Returns {"referrer_user_id", "referrer_bale_id",
        "referred_user_id"} or None (unknown code, self-referral,
        already has a referrer, or already activated).
        """
        referred = self.get_user(referred_user_id)
        if not referred:
            return None
        ref_bale_id = self._resolve_referrer_bale_id(referrer_code)
        if not ref_bale_id:
            return None
        ref_code = self.accounts.get_or_create(ref_bale_id)["referral_code"]
        ref = self.accounts.record_referral(ref_code, referred["bale_user_id"])
        if ref is None:
            return None
        referrer_user = self.get_user_by_bale_id(ref_bale_id)
        return {
            "referrer_user_id": referrer_user["id"] if referrer_user else None,
            "referrer_bale_id": ref_bale_id,
            "referred_user_id": referred["id"],
        }

    def referral_count(self, user_id):
        """ACTIVATED referrals only — the owner's rule, on every surface."""
        u = self.get_user(user_id)
        return self.accounts.activated_referrals(u["bale_user_id"]) if u else 0

    def plan2_unlocked(self, user_id):
        u = self.get_user(user_id)
        return self.accounts.plan2_unlocked(u["bale_user_id"]) if u else False

    def free_months_earned(self, user_id):
        """Banked free months: one per ACTIVATED referral, cap 6."""
        u = self.get_user(user_id)
        return self.accounts.banked_months(u["bale_user_id"]) if u else 0

    # ----- routed user questions (agent laws) ---------------------------
    # Scoped questions the bot could not answer from its deterministic
    # sources are routed here for the supporter (Shahram's panel).

    def add_open_question(self, bale_user_id, name, question):
        cur = self.db.execute(
            "INSERT INTO open_questions(bale_user_id, name, question, created_at)"
            " VALUES(?,?,?,?)",
            (str(bale_user_id), name or "", question or "", _now()),
        )
        self.db.commit()
        return cur.lastrowid

    def list_open_questions(self, limit=20):
        rows = self.db.execute(
            "SELECT * FROM open_questions WHERE status='open' ORDER BY id DESC LIMIT ?",
            (int(limit),),
        ).fetchall()
        return [dict(r) for r in rows]

    def close_open_question(self, question_id, supporter_id=None):
        self.db.execute(
            "UPDATE open_questions SET status='closed', closed_by=? WHERE id=?",
            (int(supporter_id) if supporter_id is not None else None, int(question_id)),
        )
        self.db.commit()

    def open_question_count(self):
        row = self.db.execute(
            "SELECT COUNT(*) c FROM open_questions WHERE status='open'"
        ).fetchone()
        return row["c"]

    # ----- stats --------------------------------------------------------
    def supporter_stats(self, supporter_id):
        users = self.list_users(supporter_id)
        return {
            "users_defined": len(users),
            "users_active": sum(1 for u in users if u["status"] == "active"),
            "plan2_unlocked": sum(1 for u in users if self.plan2_unlocked(u["id"])),
        }

    def global_stats(self):
        referrals = self.accounts.db.execute(
            "SELECT COUNT(*) c FROM bot_referrals"
        ).fetchone()["c"]
        try:
            guard_attempts = self.accounts.db.execute(
                "SELECT COUNT(*) c FROM agent_guard_log"
            ).fetchone()["c"]
        except Exception:
            guard_attempts = 0
        return {
            "supporters": len(self.list_supporters()),
            "users": len(self.list_users()),
            "referrals": referrals,
            "guard_attempts": guard_attempts,
            "open_questions": self.open_question_count(),
        }
