"""Distribution mechanics: accounts, referrals, activation gating."""
from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.accounts import Accounts
from src.bale_bot import BaleBotEngine


class AccountsUnit(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        # minimal ledger table, same name/column the real store uses
        db = sqlite3.connect(self.tmp.name)
        db.execute("CREATE TABLE transactions(id TEXT PRIMARY KEY, user_id TEXT)")
        db.commit(); db.close()
        self.acc = Accounts(self.tmp.name)

    def tearDown(self):
        os.unlink(self.tmp.name)

    def activate(self, uid):
        db = sqlite3.connect(self.tmp.name)
        db.execute("INSERT INTO transactions(id, user_id) VALUES(?,?)", (str(time.time_ns()), uid))
        db.commit(); db.close()

    def test_code_and_birth(self):
        a = self.acc.get_or_create("100")
        self.assertTrue(a["referral_code"].startswith("B"))
        self.assertEqual(a["plan"], "free_full")
        self.assertEqual(self.acc.get_or_create("100")["referral_code"], a["referral_code"])

    def test_referral_rules(self):
        a = self.acc.get_or_create("100")
        self.assertIsNone(self.acc.record_referral("BFFFF", "200"))       # unknown code
        self.assertIsNone(self.acc.record_referral(a["referral_code"], "100"))  # self
        self.assertIsNotNone(self.acc.record_referral(a["referral_code"], "200"))
        self.assertIsNone(self.acc.record_referral(a["referral_code"], "200"))  # twice
        b = self.acc.get_or_create("300")
        self.assertIsNone(self.acc.record_referral(b["referral_code"], "200"))  # already has referrer

    def test_activation_gates_counting(self):
        a = self.acc.get_or_create("100")
        self.acc.record_referral(a["referral_code"], "200")
        self.acc.record_referral(a["referral_code"], "300")
        self.assertEqual(self.acc.activated_referrals("100"), 0)
        self.assertFalse(self.acc.plan2_unlocked("100"))
        self.activate("200")
        self.assertEqual(self.acc.activated_referrals("100"), 1)
        self.assertEqual(self.acc.banked_months("100"), 1)
        self.activate("300")
        self.assertTrue(self.acc.plan2_unlocked("100"))
        self.assertEqual(self.acc.banked_months("100"), 2)

    def test_bank_cap_and_free_days(self):
        a = self.acc.get_or_create("100")
        for i in range(8):
            uid = str(200 + i)
            self.acc.record_referral(a["referral_code"], uid)
            self.activate(uid)
        self.assertEqual(self.acc.banked_months("100"), 6)  # cap
        st = self.acc.status("100", now=int(time.time()))
        self.assertEqual(st["free_days_left"], 30 + 6 * 30)

    def test_no_referral_after_activation(self):
        a = self.acc.get_or_create("100")
        self.activate("200")
        self.assertIsNone(self.acc.record_referral(a["referral_code"], "200"))


class MockClient:
    def __init__(self):
        self.sent = []

    def send_message(self, chat_id, text, reply_markup=None, reply_to_message_id=None):
        self.sent.append((str(chat_id), text))
        return {"ok": True, "result": {"message_id": len(self.sent)}}

    def send_document(self, chat_id, filename, content, caption=""):
        return {"ok": True, "result": {"message_id": 1}}

    def texts(self, chat_id):
        return [t for c, t in self.sent if c == str(chat_id)]


def msg(chat_id, text):
    return {"chat": {"id": chat_id}, "from": {"first_name": "تست"}, "text": text}


class EngineFlow(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.client = MockClient()
        self.engine = BaleBotEngine(self.client, db_path=str(Path(self.tmp.name) / "e.sqlite3"))

    def tearDown(self):
        self.engine.store.close()
        self.tmp.cleanup()

    def test_start_shows_code_and_status_works(self):
        self.engine.handle_message(msg(42, "/start"))
        joined = chr(10).join(self.client.texts(42))
        code = self.engine.accounts.get_or_create("42")["referral_code"]
        self.assertIn(code, joined)
        self.engine.handle_message(msg(42, "وضعیت من"))
        status = self.client.texts(42)[-1]
        self.assertIn("وضعیت تو", status)
        self.assertIn(code, status)

    def test_referral_end_to_end(self):
        e = self.engine
        e.handle_message(msg(42, "/start"))
        code_a = e.accounts.get_or_create("42")["referral_code"]
        # user 77 arrives with the code as a bare message
        e.handle_message(msg(77, code_a))
        self.assertEqual(e.accounts.get_or_create("77")["referred_by"], "42")
        # not counted until 77 activates (first confirmed transaction)
        self.assertEqual(e.accounts.activated_referrals("42"), 0)
        e.handle_message(msg(77, "فروش ۲۰۰ هزار تومان"))
        e.handle_message(msg(77, "تأیید"))
        self.assertEqual(e.accounts.activated_referrals("42"), 1)
        # second activated referral unlocks plan 2
        e.handle_message(msg(88, code_a))
        e.handle_message(msg(88, "فروش ۱۰۰ هزار تومان"))
        e.handle_message(msg(88, "تأیید"))
        self.assertTrue(e.accounts.plan2_unlocked("42"))
        e.handle_message(msg(42, "وضعیت من"))
        self.assertIn("پلن ۲", self.client.texts(42)[-1])

    def test_bare_bad_code_rejected(self):
        self.engine.handle_message(msg(55, "BFFFF"))
        self.assertIn("ثبت نشد", self.client.texts(55)[-1])


if __name__ == "__main__":
    unittest.main()
