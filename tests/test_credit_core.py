"""Deterministic-core completion tests (Part A): credit model, settlement, undo.

Covers:
- The verbatim parser cases that used to corrupt cash truth:
  «فروش نسیه ۵۰۰ هزار به احمدی» booked as cash in, «نسیه دادم به رضا» as cash out.
- Credit balances per person, full + partial settlement (typed and button
  paths), settlement as a recorded event with a real cash movement.
- Daily/summary reports: cash totals exclude unsettled credit.
- Undo: soft delete of the last / a picked transaction, audit row kept,
  undoing a settlement reopens the debt.
- Schema migration on a pre-existing (old-shape) ledger file.
"""
from __future__ import annotations

from pathlib import Path
import sqlite3
import tempfile
import unittest

from src.bale_bot import BaleBotEngine
from src.bazaar_parser import parse_bazaar_message
from src.conversation import ConversationStore


class MockClient:
    def __init__(self):
        self.sent_messages = []
        self.answered_callbacks = []

    def send_message(self, chat_id, text, reply_markup=None, reply_to_message_id=None):
        self.sent_messages.append(
            {"chat_id": chat_id, "text": text, "reply_markup": reply_markup}
        )
        return {"ok": True, "result": {"message_id": len(self.sent_messages)}}

    def answer_callback_query(self, callback_query_id, text=None, show_alert=False):
        self.answered_callbacks.append({"id": callback_query_id, "text": text})
        return {"ok": True}

    def texts(self, chat_id):
        return [m["text"] for m in self.sent_messages if str(m["chat_id"]) == str(chat_id)]

    def last_markup(self, chat_id):
        for m in reversed(self.sent_messages):
            if str(m["chat_id"]) == str(chat_id) and m["reply_markup"]:
                return m["reply_markup"]
        return None


def make_msg(chat_id, text):
    return {
        "chat": {"id": chat_id},
        "from": {"id": chat_id, "first_name": "تست", "username": f"user_{chat_id}"},
        "text": text,
    }


def make_callback(chat_id, data, qid="q1"):
    return {
        "id": qid,
        "from": {"id": chat_id, "first_name": "تست"},
        "message": {"message_id": 7, "chat": {"id": chat_id, "type": "private"}},
        "data": data,
    }


def button_data(markup, needle):
    for row in (markup or {}).get("inline_keyboard", []):
        for btn in row:
            if needle in btn.get("text", ""):
                return btn["callback_data"]
    return None


class ParserCreditCases(unittest.TestCase):
    def test_credit_sale_is_receivable_not_cash(self):
        r = parse_bazaar_message("فروش نسیه ۵۰۰ هزار به احمدی")
        self.assertEqual(r.kind, "credit")
        self.assertEqual(r.direction, "incoming")  # receivable semantics
        self.assertEqual(r.counterparty, "احمدی")
        self.assertEqual(r.amount, 500_000)
        self.assertEqual(r.unit, "تومان")

    def test_nesie_dadam_is_receivable(self):
        r = parse_bazaar_message("نسیه دادم به رضا ۳۰۰ هزار")
        self.assertEqual(r.kind, "credit")
        self.assertEqual(r.direction, "incoming")
        self.assertEqual(r.counterparty, "رضا")
        self.assertEqual(r.amount, 300_000)

    def test_credit_purchase_is_payable(self):
        r = parse_bazaar_message("خرید نسیه ۲ میلیون از پخش")
        self.assertEqual(r.kind, "credit")
        self.assertEqual(r.direction, "outgoing")
        self.assertEqual(r.counterparty, "پخش")
        self.assertEqual(r.amount, 2_000_000)

    def test_nesie_gereftam_is_payable(self):
        r = parse_bazaar_message("نسیه گرفتم از احمد ۱ میلیون")
        self.assertEqual(r.kind, "credit")
        self.assertEqual(r.direction, "outgoing")
        self.assertEqual(r.counterparty, "احمد")

    def test_plain_sale_stays_cash(self):
        r = parse_bazaar_message("فروش ۵۰۰ هزار تومان")
        self.assertEqual(r.kind, "cash")
        self.assertEqual(r.direction, "incoming")

    def test_collection_is_cash_not_credit(self):
        r = parse_bazaar_message("طلبم رو گرفتم ۵۰۰ هزار")
        self.assertEqual(r.kind, "cash")
        self.assertEqual(r.direction, "incoming")


class CreditEngineBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.tmp.name) / "credit.sqlite3")
        self.client = MockClient()
        self.engine = BaleBotEngine(self.client, db_path=self.db_path)

    def tearDown(self):
        self.engine.store.close()
        self.tmp.cleanup()

    def say(self, chat_id, text):
        self.engine.handle_message(make_msg(chat_id, text))

    def confirm_credit_sale(self, chat_id=42, text="فروش نسیه ۵۰۰ هزار تومان به احمدی"):
        self.say(chat_id, text)
        self.say(chat_id, "تأیید")

    def cash_totals(self, user_id="42"):
        txs = [t for t in self.engine.store.list_transactions(user_id) if t.kind == "cash"]
        return (
            sum(t.amount for t in txs if t.direction == "incoming"),
            sum(t.amount for t in txs if t.direction == "outgoing"),
        )


class CreditFlowTest(CreditEngineBase):
    def test_credit_sale_moves_no_cash(self):
        self.confirm_credit_sale()
        self.assertEqual(self.cash_totals(), (0, 0))
        balances = self.engine._credit_balances("42")
        self.assertEqual(len(balances), 1)
        self.assertEqual(balances[0]["counterparty"], "احمدی")
        self.assertEqual(balances[0]["open"], 500_000)
        self.assertEqual(balances[0]["side"], "receivable")

    def test_credit_purchase_is_payable_balance(self):
        self.say(42, "خرید نسیه ۲ میلیون از پخش")
        self.say(42, "تأیید")
        balances = self.engine._credit_balances("42")
        self.assertEqual(balances[0]["side"], "payable")
        self.assertEqual(balances[0]["counterparty"], "پخش")
        self.assertEqual(self.cash_totals(), (0, 0))

    def test_partial_then_full_settlement_typed(self):
        self.confirm_credit_sale()
        self.say(42, "تسویه احمدی ۲۰۰ هزار")
        self.assertIn("تسویه ثبت شد", self.client.texts(42)[-1])
        self.assertEqual(self.engine._credit_balances("42")[0]["open"], 300_000)
        # the settled part is real cash now
        self.assertEqual(self.cash_totals(), (200_000, 0))
        self.say(42, "تسویه احمدی")
        self.assertEqual(self.engine._credit_balances("42"), [])
        self.assertEqual(self.cash_totals(), (500_000, 0))
        settlements = self.engine.store.list_settlements("42")
        self.assertEqual([s.amount for s in settlements], [200_000, 300_000])

    def test_settle_unknown_person_lists_open_names(self):
        self.confirm_credit_sale()
        self.say(42, "تسویه رضایی ۱۰۰ هزار")
        self.assertIn("احمدی", self.client.texts(42)[-1])
        self.assertEqual(self.engine._credit_balances("42")[0]["open"], 500_000)

    def test_settlement_via_buttons_partial_by_typing_amount(self):
        self.confirm_credit_sale()
        self.say(42, "طلب‌ها")
        data = button_data(self.client.last_markup(42), "احمدی")
        self.assertIsNotNone(data)
        self.engine.handle_callback_query(make_callback(42, data))
        self.say(42, "۲۰۰ هزار")
        self.assertIn("تسویه ثبت شد", self.client.texts(42)[-1])
        self.assertEqual(self.engine._credit_balances("42")[0]["open"], 300_000)

    def test_settlement_via_buttons_full(self):
        self.confirm_credit_sale()
        self.say(42, "طلب‌ها")
        pick = button_data(self.client.last_markup(42), "احمدی")
        self.engine.handle_callback_query(make_callback(42, pick))
        full = button_data(self.client.last_markup(42), "همه‌اش")
        self.assertIsNotNone(full)
        self.engine.handle_callback_query(make_callback(42, full))
        self.assertEqual(self.engine._credit_balances("42"), [])
        self.assertEqual(self.cash_totals(), (500_000, 0))

    def test_stale_settle_button_is_noop(self):
        self.confirm_credit_sale()
        self.say(42, "طلب‌ها")
        pick = button_data(self.client.last_markup(42), "احمدی")
        self.say(42, "تسویه احمدی")  # settle by typing first
        self.engine.handle_callback_query(make_callback(42, pick))
        self.assertIn("دیگر مانده‌ی بازی ندارد", self.client.texts(42)[-1])
        self.assertEqual(len(self.engine.store.list_settlements("42")), 1)

    def test_daily_report_excludes_unsettled_credit_from_cash(self):
        self.confirm_credit_sale()
        self.say(42, "فروش ۲۰۰ هزار تومان")
        self.say(42, "تأیید")
        report = self.engine.daily_report_text("42")
        self.assertIn("200,000", report)
        self.assertIn("نسیه — طلب از احمدی", report)
        self.assertIn("500,000", report)
        cash_line = [ln for ln in report.splitlines() if "دریافتی" in ln][0]
        self.assertIn("200,000", cash_line)
        self.assertNotIn("700,000", cash_line)

    def test_payable_settlement_is_cash_out(self):
        self.say(42, "خرید نسیه ۲ میلیون از پخش")
        self.say(42, "تأیید")
        self.say(42, "تسویه پخش ۲ میلیون")
        self.assertEqual(self.cash_totals(), (0, 2_000_000))
        self.assertEqual(self.engine._credit_balances("42"), [])


class UndoTest(CreditEngineBase):
    def confirm_cash_sale(self, chat_id=42, text="فروش ۲۰۰ هزار تومان"):
        self.say(chat_id, text)
        self.say(chat_id, "تأیید")

    def test_undo_last_via_buttons(self):
        self.confirm_cash_sale()
        self.say(42, "حذف آخری")
        data = button_data(self.client.last_markup(42), "حذف شود")
        self.assertIsNotNone(data)
        self.engine.handle_callback_query(make_callback(42, data))
        self.assertEqual(self.engine.store.list_transactions("42"), [])
        audit = self.engine.store.list_transactions("42", include_voided=True)
        self.assertEqual(len(audit), 1)
        self.assertEqual(audit[0].voided, 1)
        self.assertNotEqual(audit[0].void_reason, "")

    def test_undo_dismiss_keeps_transaction(self):
        self.confirm_cash_sale()
        self.say(42, "حذف آخری")
        data = button_data(self.client.last_markup(42), "نگه دار")
        self.engine.handle_callback_query(make_callback(42, data))
        self.assertEqual(len(self.engine.store.list_transactions("42")), 1)

    def test_undo_specific_from_list(self):
        self.confirm_cash_sale(text="فروش ۲۰۰ هزار تومان")
        self.confirm_cash_sale(text="فروش ۳۰۰ هزار تومان")
        self.say(42, "حذف تراکنش")
        pick = button_data(self.client.last_markup(42), "200,000")
        self.assertIsNotNone(pick)
        self.engine.handle_callback_query(make_callback(42, pick))
        confirm = button_data(self.client.last_markup(42), "حذف شود")
        self.engine.handle_callback_query(make_callback(42, confirm))
        txs = self.engine.store.list_transactions("42")
        self.assertEqual(len(txs), 1)
        self.assertEqual(txs[0].amount, 300_000)

    def test_double_undo_confirm_is_noop(self):
        self.confirm_cash_sale()
        self.say(42, "حذف آخری")
        data = button_data(self.client.last_markup(42), "حذف شود")
        self.engine.handle_callback_query(make_callback(42, data))
        self.engine.handle_callback_query(make_callback(42, data, qid="q2"))
        audit = self.engine.store.list_transactions("42", include_voided=True)
        self.assertEqual(len(audit), 1)

    def test_undo_settlement_reopens_debt(self):
        self.confirm_credit_sale()
        self.say(42, "تسویه احمدی")
        self.assertEqual(self.engine._credit_balances("42"), [])
        self.say(42, "حذف آخری")  # latest entry is the settlement's cash row
        data = button_data(self.client.last_markup(42), "حذف شود")
        self.engine.handle_callback_query(make_callback(42, data))
        balances = self.engine._credit_balances("42")
        self.assertEqual(len(balances), 1)
        self.assertEqual(balances[0]["open"], 500_000)
        self.assertEqual(self.cash_totals(), (0, 0))
        self.assertEqual(self.engine.store.list_settlements("42"), [])
        self.assertEqual(
            len(self.engine.store.list_settlements("42", include_voided=True)), 1
        )


class MigrationTest(unittest.TestCase):
    def test_old_schema_db_gains_new_columns(self):
        tmp = tempfile.TemporaryDirectory()
        path = str(Path(tmp.name) / "old.sqlite3")
        db = sqlite3.connect(path)
        db.executescript(
            """
            CREATE TABLE sessions (session_id TEXT PRIMARY KEY, user_id TEXT NOT NULL,
                state_json TEXT NOT NULL, updated_at TEXT NOT NULL);
            CREATE TABLE messages (message_id TEXT PRIMARY KEY, session_id TEXT NOT NULL,
                user_id TEXT NOT NULL, role TEXT NOT NULL, body TEXT NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE transactions (transaction_id TEXT PRIMARY KEY, session_id TEXT NOT NULL,
                user_id TEXT NOT NULL, amount INTEGER NOT NULL, unit TEXT NOT NULL,
                direction TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE bot_state (state_key TEXT PRIMARY KEY, state_value INTEGER NOT NULL);
            CREATE TABLE kv_state (state_key TEXT PRIMARY KEY, state_value TEXT NOT NULL);
            INSERT INTO transactions VALUES ('t1','s1','7',1000,'تومان','incoming','confirmed','2026-10-01T00:00:00+00:00');
            """
        )
        db.commit()
        db.close()
        store = ConversationStore(path)
        try:
            txs = store.list_transactions("7")
            self.assertEqual(len(txs), 1)
            self.assertEqual(txs[0].kind, "cash")
            self.assertEqual(txs[0].voided, 0)
            cols = {r[1] for r in store._db.execute("PRAGMA table_info(transactions)")}
            self.assertTrue({"kind", "counterparty", "settlement_id", "voided"} <= cols)
            tables = {r[0] for r in store._db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            self.assertIn("settlements", tables)
        finally:
            store.close()
            tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
