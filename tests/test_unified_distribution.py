"""Unification proofs (2026-10-28): one source of truth for identity,
referral and plan across the Bale bot and the Telegram panels.

- A raw (non-activated) referral grants nothing, on either surface.
- Activation grants exactly one banked month, on either surface.
- The bank cap of 6 holds when referrals arrive via the panel AND
  when they arrive via the Bale bot.
- An owner-panel plan change lands in Accounts (what the bot reads).
- Legacy U-codes from the pre-unification panels still resolve.
- User status is derived from facts (defined / linked / active).
"""
import os
import sqlite3
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from accounts import Accounts
from support_store import SupportStore


class UnifiedBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ledger_path = os.path.join(self.tmp.name, "ledger.db")
        db = sqlite3.connect(self.ledger_path)
        db.execute("CREATE TABLE transactions(id TEXT PRIMARY KEY, user_id TEXT)")
        db.commit()
        db.close()
        self.store = SupportStore(
            os.path.join(self.tmp.name, "support.db"), self.ledger_path
        )
        self.sup = self.store.add_supporter(111, "Ali Local")

    def tearDown(self):
        self.tmp.cleanup()

    def activate_bale(self, bale_user_id):
        db = sqlite3.connect(self.ledger_path)
        db.execute(
            "INSERT INTO transactions(id, user_id) VALUES(?,?)",
            (str(time.time_ns()), str(bale_user_id)),
        )
        db.commit()
        db.close()


class TestCrossSurface(UnifiedBase):
    def test_activation_pays_exactly_one_month_on_both_surfaces(self):
        a = self.store.add_user(self.sup["id"], "Referrer")
        b = self.store.add_user(self.sup["id"], "Referred")
        self.assertIsNotNone(self.store.record_referral(a["referral_code"], b["id"]))
        # Raw link: nothing, anywhere.
        self.assertEqual(self.store.free_months_earned(a["id"]), 0)
        self.assertEqual(self.store.accounts.banked_months(a["bale_user_id"]), 0)
        self.activate_bale(b["bale_user_id"])
        # Activation: exactly one month, identical on both surfaces.
        self.assertEqual(self.store.free_months_earned(a["id"]), 1)
        self.assertEqual(self.store.accounts.banked_months(a["bale_user_id"]), 1)
        self.assertEqual(self.store.accounts.activated_referrals(a["bale_user_id"]), 1)

    def test_bot_side_referral_pays_panel_referrer(self):
        a = self.store.add_user(self.sup["id"], "Referrer")
        # A walk-in meets the Bale bot and quotes the panel-issued code.
        ref = self.store.accounts.record_referral(a["referral_code"], "9999")
        self.assertIsNotNone(ref)
        self.assertEqual(self.store.free_months_earned(a["id"]), 0)
        self.activate_bale("9999")
        self.assertEqual(self.store.free_months_earned(a["id"]), 1)

    def test_cap_six_holds_across_both_surfaces(self):
        a = self.store.add_user(self.sup["id"], "Referrer")
        # Four referrals arrive via the panel…
        for i in range(4):
            u = self.store.add_user(self.sup["id"], f"Panel{i}")
            self.assertIsNotNone(self.store.record_referral(a["referral_code"], u["id"]))
            self.activate_bale(u["bale_user_id"])
        # …and four more via the Bale bot itself.
        for i in range(4):
            walk_in = f"700{i}"
            self.assertIsNotNone(
                self.store.accounts.record_referral(a["referral_code"], walk_in)
            )
            self.activate_bale(walk_in)
        self.assertEqual(self.store.accounts.activated_referrals(a["bale_user_id"]), 8)
        self.assertEqual(self.store.accounts.banked_months(a["bale_user_id"]), 6)  # cap
        self.assertEqual(self.store.free_months_earned(a["id"]), 6)  # same on panel

    def test_legacy_u_code_still_resolves(self):
        a = self.store.add_user(self.sup["id"], "Referrer")
        b = self.store.add_user(self.sup["id"], "Referred")
        self.assertTrue(self.store.map_legacy_code("U00AA", a["id"]))
        self.assertEqual(self.store.get_user_by_code("U00AA")["id"], a["id"])
        self.assertIsNotNone(self.store.record_referral("U00AA", b["id"]))
        self.activate_bale(b["bale_user_id"])
        self.assertEqual(self.store.free_months_earned(a["id"]), 1)

    def test_status_is_derived_from_facts(self):
        u = self.store.add_user(self.sup["id"], "Shop")
        self.assertEqual(self.store.get_user(u["id"])["status"], "defined")
        u = self.store.link_user_bale_id(u["id"], "31337")
        self.assertEqual(u["status"], "linked")
        self.assertEqual(self.store.supporter_stats(self.sup["id"])["users_active"], 0)
        self.activate_bale("31337")
        self.assertEqual(self.store.get_user(u["id"])["status"], "active")
        self.assertEqual(self.store.supporter_stats(self.sup["id"])["users_active"], 1)

    def test_link_identity_preserves_referrals_and_plan(self):
        a = self.store.add_user(self.sup["id"], "Referrer")
        b = self.store.add_user(self.sup["id"], "Referred")
        self.store.record_referral(a["referral_code"], b["id"])
        self.store.set_user_plan(b["id"], "ledger_499")
        # The referred user turns out to already have a real Bale account.
        self.store.accounts.get_or_create("555")
        self.activate_bale("555")
        merged = self.store.link_user_bale_id(b["id"], "555")
        self.assertEqual(merged["bale_user_id"], "555")
        self.assertEqual(merged["status"], "active")
        # His activation now pays his referrer, and the plan set on the
        # panel identity is carried onto the surviving real account.
        self.assertEqual(self.store.free_months_earned(a["id"]), 1)
        self.assertEqual(
            self.store.accounts.get_or_create("555")["plan"], "ledger_499"
        )
        b2 = self.store.get_user(b["id"])
        self.assertEqual(b2["referral_code"], merged["referral_code"])
        self.assertEqual(b2["plan"], "ledger_499")


if __name__ == "__main__":
    unittest.main()
