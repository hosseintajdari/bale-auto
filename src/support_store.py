"""Supporter / user registry for the distribution layer.

Stdlib-only SQLite store, separate from the ledger DB. Holds the people
side of distribution: supporters (local promoters), the shop users they
define, and user-to-user referrals (the +1 free month / plan-2 unlock
mechanics from the v2 plan, section 14).

A supporter only ever sees rows with his own supporter_id; the owner
panel queries without that filter. The store enforces nothing about
Telegram — identity arrives as a telegram_id integer.
"""
import sqlite3
import time


def _now():
    return int(time.time())


class SupportStore:
    def __init__(self, path):
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
                bale_ref TEXT NOT NULL DEFAULT '',
                referral_code TEXT UNIQUE NOT NULL,
                plan TEXT NOT NULL DEFAULT 'free_full',
                status TEXT NOT NULL DEFAULT 'defined',
                created_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS referrals(
                id INTEGER PRIMARY KEY,
                referrer_user_id INTEGER NOT NULL REFERENCES users(id),
                referred_user_id INTEGER UNIQUE NOT NULL REFERENCES users(id),
                created_at INTEGER NOT NULL
            );
            """
        )
        self.db.commit()

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

    # ----- users ------------------------------------------------------
    def add_user(self, supporter_id, full_name, shop_name="", guild="", phone="", bale_ref=""):
        cur = self.db.execute(
            "INSERT INTO users(supporter_id, full_name, shop_name, guild, phone, bale_ref,"
            " referral_code, created_at) VALUES(?,?,?,?,?,?,?,?)",
            (int(supporter_id), full_name, shop_name, guild, phone, bale_ref, "PENDING", _now()),
        )
        uid = cur.lastrowid
        code = "U" + format(uid, "x").upper().zfill(4)
        self.db.execute("UPDATE users SET referral_code=? WHERE id=?", (code, uid))
        self.db.commit()
        return self.get_user(uid)

    def get_user(self, user_id):
        row = self.db.execute("SELECT * FROM users WHERE id=?", (int(user_id),)).fetchone()
        return dict(row) if row else None

    def get_user_by_code(self, code):
        row = self.db.execute(
            "SELECT * FROM users WHERE referral_code=?", (code.strip().upper(),)
        ).fetchone()
        return dict(row) if row else None

    def list_users(self, supporter_id=None):
        if supporter_id is None:
            rows = self.db.execute("SELECT * FROM users ORDER BY id").fetchall()
        else:
            rows = self.db.execute(
                "SELECT * FROM users WHERE supporter_id=? ORDER BY id", (int(supporter_id),)
            ).fetchall()
        return [dict(r) for r in rows]

    def set_user_plan(self, user_id, plan):
        self.db.execute("UPDATE users SET plan=? WHERE id=?", (plan, int(user_id)))
        self.db.commit()

    def set_user_status(self, user_id, status):
        self.db.execute("UPDATE users SET status=? WHERE id=?", (status, int(user_id)))
        self.db.commit()

    # ----- referrals ----------------------------------------------------
    def record_referral(self, referrer_code, referred_user_id):
        """Link a referred user to the user whose code brought him.

        Returns the referral row, or None when the code is unknown, the
        referred user already has a referrer, or it is a self-referral.
        """
        ref = self.get_user_by_code(referrer_code)
        if not ref:
            return None
        referred = self.get_user(int(referred_user_id))
        if not referred or referred["id"] == ref["id"]:
            return None
        try:
            cur = self.db.execute(
                "INSERT INTO referrals(referrer_user_id, referred_user_id, created_at)"
                " VALUES(?,?,?)",
                (ref["id"], referred["id"], _now()),
            )
            self.db.commit()
        except sqlite3.IntegrityError:
            return None
        return {"id": cur.lastrowid, "referrer_user_id": ref["id"],
                "referred_user_id": referred["id"]}

    def referral_count(self, user_id):
        row = self.db.execute(
            "SELECT COUNT(*) c FROM referrals WHERE referrer_user_id=?", (int(user_id),)
        ).fetchone()
        return row["c"]

    def plan2_unlocked(self, user_id):
        """Plan 2 activates when the user has referred a second person."""
        return self.referral_count(user_id) >= 2

    def free_months_earned(self, user_id):
        """One extra free month per referral (cap applied at billing)."""
        return self.referral_count(user_id)

    # ----- stats --------------------------------------------------------
    def supporter_stats(self, supporter_id):
        users = self.list_users(supporter_id)
        return {
            "users_defined": len(users),
            "users_active": sum(1 for u in users if u["status"] == "active"),
            "plan2_unlocked": sum(1 for u in users if self.plan2_unlocked(u["id"])),
        }

    def global_stats(self):
        return {
            "supporters": len(self.list_supporters()),
            "users": len(self.list_users()),
            "referrals": self.db.execute("SELECT COUNT(*) c FROM referrals").fetchone()["c"],
        }
