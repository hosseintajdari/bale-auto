import os
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from support_store import SupportStore
from supporter_bot import SupporterPanel
from owner_panel_bot import OwnerPanel


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.store = SupportStore(self.tmp.name)
        self.sup = self.store.add_supporter(111, "Ali Local")
        self.owner = OwnerPanel(self.store, 999)
        self.panel = SupporterPanel(self.store)

    def tearDown(self):
        os.unlink(self.tmp.name)
        for suffix in (".ledger.db", ".ledger.db-wal", ".ledger.db-shm"):
            try:
                os.unlink(self.tmp.name + suffix)
            except OSError:
                pass

    def activate(self, user):
        """Simulate the user's first confirmed transaction in the ledger
        (the one and only activation event, owner's rule)."""
        db = self.store.accounts.db
        db.execute("CREATE TABLE IF NOT EXISTS transactions(id TEXT PRIMARY KEY, user_id TEXT)")
        db.execute(
            "INSERT INTO transactions(id, user_id) VALUES(?,?)",
            (str(time.time_ns()), user["bale_user_id"]),
        )
        db.commit()

    def define_user(self, name="Reza Shop"):
        p = self.panel
        p.handle_callback(111, "new_user")
        p.handle_text(111, name)
        p.handle_text(111, "Shop " + name)
        p.handle_text(111, "pharmacy")
        p.handle_text(111, "09150000000")
        out = p.handle_text(111, "-")
        return out


class TestStore(Base):
    def test_referral_code_format(self):
        # Unified scheme: panel users carry the bot's B-codes.
        u = self.store.add_user(self.sup["id"], "A")
        self.assertTrue(u["referral_code"].startswith("B"))
        self.assertEqual(self.store.get_user_by_code(u["referral_code"])["id"], u["id"])

    def test_referral_rules(self):
        a = self.store.add_user(self.sup["id"], "A")
        b = self.store.add_user(self.sup["id"], "B")
        c = self.store.add_user(self.sup["id"], "C")
        self.assertIsNone(self.store.record_referral("NOPE", b["id"]))
        self.assertIsNone(self.store.record_referral(a["referral_code"], a["id"]))
        self.assertIsNotNone(self.store.record_referral(a["referral_code"], b["id"]))
        self.assertIsNone(self.store.record_referral(a["referral_code"], b["id"]))  # dup
        # A raw (not yet activated) referral grants NOTHING — owner's rule.
        self.assertEqual(self.store.referral_count(a["id"]), 0)
        self.assertEqual(self.store.free_months_earned(a["id"]), 0)
        self.assertFalse(self.store.plan2_unlocked(a["id"]))
        self.assertIsNotNone(self.store.record_referral(a["referral_code"], c["id"]))
        # Activation is what pays out: B's first transaction banks month 1.
        self.activate(b)
        self.assertEqual(self.store.referral_count(a["id"]), 1)
        self.assertEqual(self.store.free_months_earned(a["id"]), 1)
        self.assertFalse(self.store.plan2_unlocked(a["id"]))
        self.activate(c)
        self.assertEqual(self.store.referral_count(a["id"]), 2)
        self.assertTrue(self.store.plan2_unlocked(a["id"]))
        self.assertEqual(self.store.free_months_earned(a["id"]), 2)


class TestSupporterPanel(Base):
    def test_denied_for_stranger(self):
        out = self.panel.handle_text(555, "/start")
        self.assertIn("پشتیبان", out[0][0])
        self.assertNotIn("پنل پشتیبان", out[0][0])

    def test_define_user_flow(self):
        out = self.define_user()
        text = out[0][0]
        self.assertIn("کاربر تعریف شد", text)
        self.assertIn("کد معرفی", text)
        users = self.store.list_users(self.sup["id"])
        self.assertEqual(len(users), 1)
        self.assertEqual(users[0]["guild"], "pharmacy")

    def test_scope_isolation(self):
        other = self.store.add_supporter(222, "Other")
        self.store.add_user(other["id"], "NotMine")
        txt = self.panel.handle_callback(111, "my_users")[0][0]
        self.assertIn("هنوز کاربری", txt)  # supporter 111 has none of his own

    def test_attach_referral_flow(self):
        self.define_user("First")
        self.define_user("Second")
        users = self.store.list_users(self.sup["id"])
        first, second = users[0], users[1]
        p = self.panel
        p.handle_callback(111, "attach_ref")
        p.handle_text(111, str(second["id"]))
        p.handle_text(111, "777")  # second's real Bale id (link step)
        out = p.handle_text(111, first["referral_code"])
        self.assertIn("ثبت شد", out[0][0])
        self.assertEqual(self.store.get_user(second["id"])["bale_user_id"], "777")
        # Linked but not activated yet: counts nothing (owner's rule).
        self.assertEqual(self.store.referral_count(first["id"]), 0)


class TestOwnerPanel(Base):
    def test_denied_for_non_owner(self):
        out = self.owner.handle_text(111, "/start")
        self.assertIn("فقط برای مالک", out[0][0])

    def test_define_supporter_and_toggle(self):
        o = self.owner
        o.handle_callback(999, "new_supporter")
        o.handle_text(999, "333")
        out = o.handle_text(999, "New Sup")
        self.assertIn("پشتیبان تعریف شد", out[0][0])
        sup = self.store.get_supporter_by_tg(333)
        self.assertIsNotNone(sup)
        out = o.handle_callback(999, f"sup_toggle:{sup['id']}")
        self.assertIn("غیرفعال", out[0][0])
        # deactivated supporter loses panel access
        denied = self.panel.handle_text(333, "/start")
        self.assertNotIn("پنل پشتیبان", denied[0][0])

    def test_change_plan(self):
        u = self.store.add_user(self.sup["id"], "A")
        o = self.owner
        o.handle_callback(999, "change_plan")
        out = o.handle_text(999, str(u["id"]))
        self.assertIsNotNone(out[0][1])  # plan keyboard offered
        out = o.handle_callback(999, "plan:accountant_999")
        self.assertIn("حسابدار صنف", out[0][0])
        self.assertEqual(self.store.get_user(u["id"])["plan"], "accountant_999")
        # The change lands in Accounts — the store the Bale bot reads.
        self.assertEqual(
            self.store.accounts.get_or_create(u["bale_user_id"])["plan"],
            "accountant_999",
        )

    def test_global_stats(self):
        self.store.add_user(self.sup["id"], "A")
        out = self.owner.handle_callback(999, "stats")
        self.assertIn("کاربر: 1", out[0][0])


if __name__ == "__main__":
    unittest.main()
