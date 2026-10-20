"""Automated Test Suite for Bazaar Merchants and Laborers (بازاریان و کارگران).

Validates:
1. Bazaar colloquial shopkeeper terms (کارت کشید, فروش نقدی, خرید بار, دخل مغازه, خرج ناهار)
2. Worker and laborer phrases (اوستا ریخت, دستمزد گرفتم, انعام, مساعده, خرید ابزار, کرایه)
3. Persian numbers and compound words (میلیون, هزار, نیم میلیون, پونصد, دویست)
4. Multi-turn single-tap confirmation workflows
5. Direction and scale ambiguity safety guardrails
6. Accurate ledger calculations and bazaar financial reports
"""
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from src.bale_bot import BaleBotEngine, _parse_env_assignment, validate_panel_config
from src.bazaar_parser import parse_bazaar_message
from src.conversation import ConversationStore


class MockBaleClient:
    def __init__(self):
        self.sent_messages = []

    def send_message(self, chat_id, text, reply_markup=None, reply_to_message_id=None):
        self.sent_messages.append({"chat_id": chat_id, "text": text, "reply_markup": reply_markup})
        return {"ok": True, "result": {"message_id": len(self.sent_messages)}}


class BazaarWorkerTestSuite(unittest.TestCase):
    def test_env_parser_accepts_export_prefix(self):
        self.assertEqual(_parse_env_assignment("export FOO=bar\n"), ("FOO", "bar"))
        self.assertEqual(_parse_env_assignment("  export\tFOO='bar baz'  "), ("FOO", "bar baz"))
        self.assertIsNone(_parse_env_assignment("# export FOO=bar"))

    def test_panel_emission_requires_explicit_secret(self):
        with self.assertRaisesRegex(RuntimeError, "PANEL_API_SECRET is required"):
            validate_panel_config(True, " ")

        validate_panel_config(True, "configured-secret")
        validate_panel_config(False, "")

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.tmp.name) / "test_bazaar.sqlite3")
        self.client = MockBaleClient()
        self.engine = BaleBotEngine(self.client, db_path=self.db_path)

    def tearDown(self):
        self.engine.store.close()
        self.tmp.cleanup()

    def make_msg(self, chat_id: int, text: str, sender_name: str = "حاجی بازاری"):
        return {
            "chat": {"id": chat_id},
            "from": {"first_name": sender_name, "username": f"user_{chat_id}"},
            "text": text,
        }

    # -------------------------------------------------------------------------
    # 1. Direct Parser Validation for Bazaar and Worker Phrases
    # -------------------------------------------------------------------------
    def test_bazaar_parser_shopkeeper_scenarios(self):
        cases = [
            ("کارت کشید ۴۵۰ هزار تومن بابت فروش پیراهن", 450000, "تومان", "incoming", "فروش پیراهن"),
            ("فروش نقدی ۲ میلیون و ۵۰۰ هزار تومان", 2500000, "تومان", "incoming", ""),
            ("واریز شد ۵ میلیون به حسابم", 5000000, "تومان", "incoming", "حسابم"),
            ("دخل امروز ۱ و نیم میلیون", 1500000, "تومان", "incoming", ""),
            ("خرید بار ۱۰ میلیون از پخش تهران", 10000000, "تومان", "outgoing", "پخش تهران"),
            ("خرج ناهار کارگرا ۱۲۰ هزار تومن", 120000, "تومان", "outgoing", "کارگرا"),
            ("کرایه وانت ۱۵۰ هزار تومن", 150000, "تومان", "outgoing", ""),
            ("مساعده دادم به شاگرد ۵۰۰ هزار تومن", 500000, "تومان", "outgoing", "شاگرد"),
            ("قبض برق مغازه ۳۲۰ هزار تومن", 320000, "تومان", "outgoing", "مغازه"),
            ("طلبم رو داد حاج رضا ۱ میلیون", 1000000, "تومان", "incoming", "حاج رضا"),
        ]
        for text, exp_amt, exp_unit, exp_dir, exp_sub_desc in cases:
            res = parse_bazaar_message(text)
            self.assertEqual(exp_amt, res.amount, f"Failed amount for: {text}")
            self.assertEqual(exp_unit, res.unit, f"Failed unit for: {text}")
            self.assertEqual(exp_dir, res.direction, f"Failed direction for: {text}")
            if exp_sub_desc:
                self.assertIn(exp_sub_desc, res.description, f"Failed desc for: {text}")

    def test_bazaar_parser_worker_scenarios(self):
        cases = [
            ("اوستا ۱ میلیون ریخت به حسابم بابت بنایی", 1000000, "تومان", "incoming", "بنایی"),
            ("دستمزد کارگر ۵۰۰ هزار گرفتم", 500000, "تومان", "incoming", ""),
            ("انعام گرفتم ۲۰۰ هزار تومن از صاحبکار", 200000, "تومان", "incoming", "صاحبکار"),
            ("خرید ماله و کمچه ۱۲۰ هزار تومن", 120000, "تومان", "outgoing", "ماله و کمچه"),
            ("کرایه اسنپ ۵۰ هزار تومن", 50000, "تومان", "outgoing", ""),
            ("قسط وام ۱ میلیون و ۲۰۰ دادم", 1200000, "تومان", "outgoing", ""),
        ]
        for text, exp_amt, exp_unit, exp_dir, exp_sub_desc in cases:
            res = parse_bazaar_message(text)
            self.assertEqual(exp_amt, res.amount, f"Failed amount for: {text}")
            self.assertEqual(exp_unit, res.unit, f"Failed unit for: {text}")
            self.assertEqual(exp_dir, res.direction, f"Failed direction for: {text}")
            if exp_sub_desc:
                self.assertIn(exp_sub_desc, res.description, f"Failed desc for: {text}")

    # -------------------------------------------------------------------------
    # 2. End-to-End Single-Tap Flow with Various Persian Affirmations
    # -------------------------------------------------------------------------
    def test_e2e_single_tap_flow_various_confirmations(self):
        confirmations = ["تأیید", "تایید", "بله", "آره", "اره", "ثبت", "ثبت کن", "حله", "درسته", "دمت گرم", "باشه"]
        for idx, conf_word in enumerate(confirmations):
            user_id = 200 + idx
            # Step 1: User sends single natural message
            self.engine.handle_message(self.make_msg(user_id, f"کارت کشید {100 * (idx + 1)} هزار تومن بابت فروش پیراهن"))
            last_msg = self.client.sent_messages[-1]
            self.assertIn("پیش‌نویس تراکنش آماده ثبت", last_msg["text"])
            self.assertIn("دریافت", last_msg["text"])
            self.assertIn(f"{100000 * (idx + 1):,}", last_msg["text"])

            # Step 2: User confirms with colloquial word
            self.engine.handle_message(self.make_msg(user_id, conf_word))
            confirm_msg = self.client.sent_messages[-1]
            self.assertIn("تراکنش با موفقیت ثبت شد", confirm_msg["text"])

            # Verify transaction in SQLite store
            txs = self.engine.store.list_transactions(str(user_id))
            self.assertEqual(1, len(txs))
            self.assertEqual(100000 * (idx + 1), txs[0].amount)
            self.assertEqual("تومان", txs[0].unit)
            self.assertEqual("incoming", txs[0].direction)

    # -------------------------------------------------------------------------
    # 3. Guardrail: Direction Ambiguity Handling
    # -------------------------------------------------------------------------
    def test_direction_ambiguity_guardrail(self):
        user_id = 501
        # User sends amount and memo without any indication of incoming or outgoing
        self.engine.handle_message(self.make_msg(user_id, "۵۰۰ هزار تومان علی"))
        last_msg = self.client.sent_messages[-1]
        self.assertIn("این مبلغ «دریافتی» (آمد به حساب) بوده یا «پرداختی»", last_msg["text"])

        # User taps 'دریافت'
        self.engine.handle_message(self.make_msg(user_id, "دریافت"))
        # Now awaiting confirmation
        self.engine.handle_message(self.make_msg(user_id, "تأیید"))
        txs = self.engine.store.list_transactions(str(user_id))
        self.assertEqual(1, len(txs))
        self.assertEqual(500000, txs[0].amount)
        self.assertEqual("incoming", txs[0].direction)

    # -------------------------------------------------------------------------
    # 4. Guardrail: Sub-Thousand Ambiguity Handling
    # -------------------------------------------------------------------------
    def test_sub_thousand_ambiguity_guardrail(self):
        user_id = 601
        # User types '۱۵۰ تومن' (colloquially can mean 150 Tomans or 150,000 Tomans)
        self.engine.handle_message(self.make_msg(user_id, "خرج کرایه وانت ۱۵۰ تومن"))
        last_msg = self.client.sent_messages[-1]
        self.assertIn("150,000 تومان", last_msg["text"])

        # User confirms 150 thousand
        self.engine.handle_message(self.make_msg(user_id, "۱۵۰ هزار تومان"))
        # Then confirms
        self.engine.handle_message(self.make_msg(user_id, "تأیید"))
        txs = self.engine.store.list_transactions(str(user_id))
        self.assertEqual(1, len(txs))
        self.assertEqual(150000, txs[0].amount)
        self.assertEqual("outgoing", txs[0].direction)

    def test_sub_thousand_keyboard_uses_detected_rial_unit(self):
        self.engine.handle_message(self.make_msg(602, "فروش ۱۵۰ ریال"))
        keyboard = self.client.sent_messages[-1]["reply_markup"]["keyboard"]
        labels = [button["text"] for row in keyboard for button in row]
        self.assertIn("✅ 150,000 ریال", labels)
        self.assertIn("✅ 150 ریال", labels)

    # -------------------------------------------------------------------------
    # 5. Financial Summary / دخل و خرج
    # -------------------------------------------------------------------------
    def test_bazaar_financial_summary(self):
        user_id = 701
        # Add multiple transactions: 2 incoming, 1 outgoing
        self.engine.handle_message(self.make_msg(user_id, "فروش نقدی ۲ میلیون تومان"))
        self.engine.handle_message(self.make_msg(user_id, "تأیید"))

        self.engine.handle_message(self.make_msg(user_id, "کارت کشید ۵۰۰ هزار تومن"))
        self.engine.handle_message(self.make_msg(user_id, "تأیید"))

        self.engine.handle_message(self.make_msg(user_id, "خرج ناهار ۲۰۰ هزار تومن"))
        self.engine.handle_message(self.make_msg(user_id, "تأیید"))

        # Ask for summary in bazaar words
        for query in ["گزارش مالی", "دخل و خرج", "حساب کتاب", "/summary"]:
            self.engine.handle_message(self.make_msg(user_id, query))
            summary_msg = self.client.sent_messages[-1]
            self.assertIn("وضعیت دخل و خرج شما", summary_msg["text"])
            self.assertIn("2,500,000 تومان", summary_msg["text"])  # Total incoming
            self.assertIn("200,000 تومان", summary_msg["text"])    # Total outgoing
            self.assertIn("2,300,000 تومان", summary_msg["text"])  # Net balance


if __name__ == "__main__":
    unittest.main()
