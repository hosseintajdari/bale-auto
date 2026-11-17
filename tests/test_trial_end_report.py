"""End-of-free-month report (production path, step B2).

Before this change an expired user (free month over, plan still
free_full) simply kept getting the regular nightly report — with a
«0 روز مانده» line — forever. Now the FIRST nightly run after the
trial ends sends a one-time end-of-month report instead: his own
month in numbers, the plan ladder, and the supporter continue path.
Everything else about expired users is unchanged.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import sqlite3
import tempfile
import time
import unittest
from unittest.mock import patch

from src.accounts import Accounts
from src.bale_bot import BaleBotEngine

DAY = 86400
TRIAL_END_MARK = "ماه رایگان کاملت تمام شد"


class MockClient:
    def __init__(self):
        self.sent_messages = []
        self.fail_send = False

    def send_message(self, chat_id, text, reply_markup=None, reply_to_message_id=None):
        if self.fail_send:
            return {"ok": False, "description": "simulated delivery failure"}
        self.sent_messages.append({"chat_id": str(chat_id), "text": text})
        return {"ok": True, "result": {"message_id": len(self.sent_messages)}}

    def texts(self, chat_id):
        return [m["text"] for m in self.sent_messages if m["chat_id"] == str(chat_id)]


def make_msg(chat_id, text):
    return {"chat": {"id": chat_id}, "from": {"first_name": "تست"}, "text": text}


def evening(day_offset=0):
    """18:00 UTC == 21:30 Tehran on (real today + day_offset)."""
    base = datetime.now(timezone.utc).date() + timedelta(days=day_offset)
    return datetime(base.year, base.month, base.day, 18, 0, tzinfo=timezone.utc)


class TrialEndReportTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.tmp.name) / "ledger.sqlite3")
        self.client = MockClient()
        self.engine = BaleBotEngine(self.client, db_path=self.db_path)
        self.env = patch.dict(
            os.environ, {"NIGHTLY_REPORT_ENABLED": "1", "NIGHTLY_REPORT_TIME": "21:00"}
        )
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.engine.store.close()
        self.engine.accounts.db.close()
        self.tmp.cleanup()

    def confirm(self, chat_id, text):
        self.engine.handle_message(make_msg(chat_id, text))
        self.engine.handle_message(make_msg(chat_id, "تأیید"))

    def make_expired_user(self, chat_id="42"):
        """Two transactions inside the trial window; the free month
        ended yesterday (activation backdated 31 days)."""
        in_window = datetime.fromtimestamp(time.time() - 20 * DAY, tz=timezone.utc)
        with patch("src.bale_bot._now", return_value=in_window.isoformat()):
            self.confirm(chat_id, "فروش ۲۰۰ هزار تومان")
            self.confirm(chat_id, "فروش نسیه ۵۰۰ هزار تومان به احمدی")
        self.engine.accounts.get_or_create(chat_id)
        self.engine.accounts.db.execute(
            "UPDATE accounts SET activated_at=? WHERE bale_user_id=?",
            (int(time.time()) - 31 * DAY, chat_id),
        )
        self.engine.accounts.db.commit()

    def test_expired_user_gets_trial_end_report_once(self):
        self.make_expired_user()
        sent = self.engine.send_nightly_reports(evening())
        self.assertEqual(sent, 1)
        texts = self.client.texts("42")
        trial_end = [t for t in texts if TRIAL_END_MARK in t]
        self.assertEqual(len(trial_end), 1)
        report = trial_end[0]
        self.assertIn("تعداد تراکنش: 2", report)
        self.assertIn("200,000", report)  # the cash sale, cash truth only
        self.assertIn("طلب‌های باز: 1", report)
        self.assertIn("500,000", report)  # the open receivable
        self.assertIn("دفتر ۴۹۹", report)
        self.assertIn("حسابدار صنف ۹۹۹", report)
        self.assertIn("ارتباطی ۱٬۰۹۹", report)
        self.assertIn("وضعیت من", report)
        # Same evening again: the once-per-day key blocks a resend.
        self.assertEqual(self.engine.send_nightly_reports(evening()), 0)
        # Next evening: no fresh transactions -> nothing at all, and in
        # particular the trial-end report does NOT repeat.
        self.assertEqual(self.engine.send_nightly_reports(evening(1)), 0)
        self.assertEqual(
            len([t for t in self.client.texts("42") if TRIAL_END_MARK in t]), 1
        )
        # A later active day gets the REGULAR report, still no repeat.
        day2 = datetime.fromtimestamp(time.time() + DAY, tz=timezone.utc)
        with patch("src.bale_bot._now", return_value=day2.isoformat()):
            self.confirm("42", "فروش ۱۰۰ هزار تومان")
        self.assertEqual(self.engine.send_nightly_reports(evening(1)), 1)
        texts = self.client.texts("42")
        self.assertTrue(any("گزارش امروز" in t for t in texts))
        self.assertEqual(len([t for t in texts if TRIAL_END_MARK in t]), 1)

    def test_in_trial_user_gets_regular_report_only(self):
        self.confirm("77", "فروش ۲۰۰ هزار تومان")
        sent = self.engine.send_nightly_reports(evening())
        self.assertEqual(sent, 1)
        texts = self.client.texts("77")
        self.assertTrue(any("گزارش امروز" in t for t in texts))
        self.assertFalse(any(TRIAL_END_MARK in t for t in texts))
        row = self.engine.accounts.db.execute(
            "SELECT trial_end_report_sent FROM accounts WHERE bale_user_id='77'"
        ).fetchone()
        self.assertEqual(row[0], 0)

    def test_failed_trial_end_delivery_is_retried(self):
        """Codex P2 (1): a failed send must NOT mark the one-time
        report sent — the user gets it on the next run instead."""
        self.make_expired_user()
        self.client.fail_send = True
        sent = self.engine.send_nightly_reports(evening())
        self.assertEqual(sent, 0)
        # The 4 confirmation texts from make_expired_user are already
        # there; assert no trial-end report was delivered.
        self.assertEqual(
            len([t for t in self.client.texts("42") if TRIAL_END_MARK in t]), 0
        )
        row = self.engine.accounts.db.execute(
            "SELECT trial_end_report_sent FROM accounts WHERE bale_user_id='42'"
        ).fetchone()
        self.assertEqual(row[0], 0)
        # Same evening, delivery working again: the report goes out
        # (proves the nightly key was not set either).
        self.client.fail_send = False
        sent = self.engine.send_nightly_reports(evening())
        self.assertEqual(sent, 1)
        self.assertEqual(
            len([t for t in self.client.texts("42") if TRIAL_END_MARK in t]), 1
        )

    def test_lazy_anchor_includes_first_transaction(self):
        """Codex P2 (2) repro: sale confirmed 09:00, activation first
        observed by the nightly report — the trial-end report must
        still count that first sale."""
        morning = datetime(2026, 11, 1, 9, 0, tzinfo=timezone.utc)
        with patch("src.bale_bot._now", return_value=morning.isoformat()):
            self.confirm("55", "فروش ۲۰۰ هزار تومان")
        # No nightly run in between: the anchor is still uninitialized.
        row = self.engine.accounts.db.execute(
            "SELECT activated_at FROM accounts WHERE bale_user_id='55'"
        ).fetchone()
        self.assertIsNone(row[0])
        trial_night = datetime(2026, 12, 2, 18, 0, tzinfo=timezone.utc)
        sent = self.engine.send_nightly_reports(trial_night)
        self.assertEqual(sent, 1)
        trial_end = [t for t in self.client.texts("55") if TRIAL_END_MARK in t]
        self.assertEqual(len(trial_end), 1)
        self.assertIn("تعداد تراکنش: 1", trial_end[0])
        self.assertIn("200,000", trial_end[0])


class AccountsTrialEndTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.tmp.name) / "acc.sqlite3")
        self.accounts = Accounts(self.path)
        self.now = int(time.time())

    def tearDown(self):
        self.accounts.db.close()
        self.tmp.cleanup()

    def _activate(self, user_id, days_ago):
        self.accounts.get_or_create(user_id)
        self.accounts.db.execute(
            "UPDATE accounts SET activated_at=? WHERE bale_user_id=?",
            (self.now - days_ago * DAY, user_id),
        )
        # is_activated() reads the transactions table; give it its fact.
        self.accounts.db.execute(
            "CREATE TABLE IF NOT EXISTS transactions(user_id TEXT)"
        )
        self.accounts.db.execute(
            "INSERT INTO transactions(user_id) VALUES(?)", (user_id,)
        )
        self.accounts.db.commit()

    def test_pending_only_for_expired_free_plan(self):
        self._activate("u1", 31)
        self.assertTrue(self.accounts.trial_end_report_pending("u1", self.now))
        self.accounts.mark_trial_end_report_sent("u1")
        self.assertFalse(self.accounts.trial_end_report_pending("u1", self.now))

    def test_paid_plan_and_in_trial_are_not_pending(self):
        self._activate("u2", 40)
        self.accounts.set_plan("u2", "ledger_499")
        self.assertFalse(self.accounts.trial_end_report_pending("u2", self.now))
        self._activate("u3", 5)
        self.assertFalse(self.accounts.trial_end_report_pending("u3", self.now))

    def test_activation_anchor_uses_first_transaction_time(self):
        """The lazy anchor is the first confirmed transaction's
        timestamp, not the observation moment."""
        first = self.now - 10 * DAY
        self.accounts.get_or_create("u5")
        self.accounts.db.execute(
            "CREATE TABLE IF NOT EXISTS transactions("
            "user_id TEXT, created_at TEXT, voided INTEGER NOT NULL DEFAULT 0)"
        )
        self.accounts.db.execute(
            "INSERT INTO transactions(user_id, created_at) VALUES(?, ?)",
            ("u5", datetime.fromtimestamp(first, tz=timezone.utc).isoformat()),
        )
        self.accounts.db.commit()
        self.assertEqual(self.accounts.activation_anchor("u5"), first)
        row = self.accounts.db.execute(
            "SELECT activated_at FROM accounts WHERE bale_user_id='u5'"
        ).fetchone()
        self.assertEqual(row[0], first)

    def test_migration_adds_marker_column_to_old_schema(self):
        old_path = str(Path(self.tmp.name) / "old.sqlite3")
        conn = sqlite3.connect(old_path)
        conn.executescript(
            """
            CREATE TABLE accounts(
                bale_user_id TEXT PRIMARY KEY,
                referral_code TEXT UNIQUE NOT NULL,
                referred_by TEXT,
                plan TEXT NOT NULL DEFAULT 'free_full',
                created_at INTEGER NOT NULL,
                activated_at INTEGER
            );
            INSERT INTO accounts(bale_user_id, referral_code, created_at)
            VALUES('u9', 'B0009', 1);
            """
        )
        conn.commit()
        conn.close()
        migrated = Accounts(old_path)
        cols = [r[1] for r in migrated.db.execute("PRAGMA table_info(accounts)")]
        self.assertIn("trial_end_report_sent", cols)
        row = migrated.db.execute(
            "SELECT trial_end_report_sent FROM accounts WHERE bale_user_id='u9'"
        ).fetchone()
        self.assertEqual(row[0], 0)
        migrated.db.close()


if __name__ == "__main__":
    unittest.main()
