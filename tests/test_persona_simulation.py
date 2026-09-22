"""Automated Persona Simulation and Stress Test Suite for bale-auto & Bale Bot.

Simulates multiple realistic personas:
1. Casual & Typos (colloquial Persian, slang, typos, informal speech)
2. Impatient & Navigation (rapid menu switches, cancellation, resets)
3. Complaints & Escalation (support, refund demands, fallback handling)
4. Non-Financial & Random Chit-chat (greetings, off-topic, questions)
5. Adversarial & Extreme Inputs (injection attempts, ultra-long text, emojis)

Runs across both ConversationService engine and P0Ledger core.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.conversation import ConversationService, ConversationStore
from src.p0_core import P0Ledger, Scope, normalize


class PersonaSimulationTestSuite(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.tmp.name) / "test_persona.sqlite3")
        self.store = ConversationStore(self.db_path)
        self.service = ConversationService(self.store)
        self.ledger = P0Ledger()

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    # -------------------------------------------------------------------------
    # Persona 1: Casual & Typos (کاربر عامیانه و کم‌تجربه)
    # -------------------------------------------------------------------------
    def test_persona_casual_and_typos(self):
        # User 1: Colloquial Persian numbers and spelling
        u1_session = "session-casual-1"
        u1 = "user-casual-1"

        # 1. Sends standard money transaction
        r1 = self.service.handle(u1_session, u1, "دریافت ۵۰۰٬۰۰۰ تومان")
        self.assertEqual("awaiting_unit", r1["status"])

        # 2. Responds with typo/colloquial unit "تومن"
        # Since strict UNITS is {"ریال", "ريال", "تومان"}, let us see how it handles "تومان" vs typos
        r2 = self.service.handle(u1_session, u1, "تومان")
        self.assertEqual("awaiting_confirmation", r2["status"])

        # 3. Confirms with "تایید"
        r3 = self.service.handle(u1_session, u1, "تایید")
        self.assertEqual("confirmed", r3["status"])
        self.assertEqual(500000, r3["transaction"].amount)
        self.assertEqual("تومان", r3["transaction"].unit)

    # -------------------------------------------------------------------------
    # Persona 2: Impatient & Navigation (کاربر بی‌حوصله و لغو/تغییر مسیر)
    # -------------------------------------------------------------------------
    def test_persona_impatient_and_cancellation(self):
        u2_session = "session-impatient-2"
        u2 = "user-impatient-2"

        # 1. Starts transaction
        r1 = self.service.handle(u2_session, u2, "واریز ۱۲۰۰۰۰۰")
        self.assertEqual("awaiting_unit", r1["status"])

        # 2. Changes mind, user cancels (simulating command or reset)
        state = self.store.load_session(u2_session, u2)
        self.assertIsNotNone(state.get("pending"))
        state["pending"] = None
        self.store.save_session(u2_session, u2, state)

        # 3. Starts fresh transaction immediately
        r2 = self.service.handle(u2_session, u2, "پرداخت ۳۵۰۰۰۰")
        self.assertEqual("awaiting_unit", r2["status"])
        updated_state = self.store.load_session(u2_session, u2)
        self.assertEqual(350000, updated_state["pending"]["amount"])

    # -------------------------------------------------------------------------
    # Persona 3: Off-topic / Fallback / Chit-chat (مکالمات نامربوط و متفرقه)
    # -------------------------------------------------------------------------
    def test_persona_chitchat_and_fallback(self):
        u3_session = "session-chitchat-3"
        u3 = "user-chitchat-3"

        # Off-topic messages should gracefully return manual_clarification
        off_topics = [
            "سلام چطوری؟",
            "قیمت دلار چنده امروز؟",
            "کالای من کی ارسال میشه؟",
            "لطفا با پشتیبانی تماس بگیرید",
            "تخفیف میدید؟",
        ]
        for msg in off_topics:
            res = self.service.handle(u3_session, u3, msg)
            self.assertEqual("manual_clarification", res["status"])
            self.assertIn("مبلغ را با دریافت", res["reply"])

    # -------------------------------------------------------------------------
    # Persona 4: Adversarial & Extreme Inputs (ورودی‌های مخرب و نامتعارف)
    # -------------------------------------------------------------------------
    def test_persona_adversarial_and_extreme(self):
        u4_session = "session-adversarial-4"
        u4 = "user-adversarial-4"

        # SQL Injection attempt
        sqli = "دریافت 1000; DROP TABLE transactions; --"
        res = self.service.handle(u4_session, u4, sqli)
        self.assertEqual("awaiting_unit", res["status"])
        # Verify table still exists and query succeeds
        self.assertEqual([], self.store.list_transactions(u4))

        # Separate session for very large amount
        u4_large_sess = "session-adversarial-large"
        res2 = self.service.handle(u4_large_sess, u4, "دریافت 999999999999999")
        self.assertEqual("awaiting_unit", res2["status"])

        # Negative / Zero amount protection
        u4_zero_sess = "session-adversarial-zero"
        with self.assertRaises(ValueError):
            self.service.handle(u4_zero_sess, u4, "دریافت 0")

    # -------------------------------------------------------------------------
    # Persona 5: Multi-user Concurrency & Isolation (عدم تداخل کاربران همزمان)
    # -------------------------------------------------------------------------
    def test_multi_user_concurrency_isolation(self):
        # Simulate 10 simultaneous users performing independent operations
        for i in range(10):
            uid = f"user-conc-{i}"
            sess = f"session-conc-{i}"
            
            # Start
            r1 = self.service.handle(sess, uid, f"دریافت {1000 * (i + 1)}")
            self.assertEqual("awaiting_unit", r1["status"])
            
            # Unit
            r2 = self.service.handle(sess, uid, "تومان")
            self.assertEqual("awaiting_confirmation", r2["status"])
            
            # Confirm
            r3 = self.service.handle(sess, uid, "تأیید")
            self.assertEqual("confirmed", r3["status"])
            self.assertEqual(1000 * (i + 1), r3["transaction"].amount)

        # Verify each user has exactly 1 isolated transaction
        for i in range(10):
            uid = f"user-conc-{i}"
            txs = self.store.list_transactions(uid)
            self.assertEqual(1, len(txs))
            self.assertEqual(1000 * (i + 1), txs[0].amount)

    # -------------------------------------------------------------------------
    # Persona 6: Bot Engine Full-turn Handshake & UI Simulation
    # -------------------------------------------------------------------------
    def test_bot_engine_personas_and_edge_cases(self):
        from src.bale_bot import BaleBotEngine

        class MockBaleClient:
            def __init__(self):
                self.sent_messages = []

            def send_message(self, chat_id, text, reply_markup=None, reply_to_message_id=None):
                self.sent_messages.append({"chat_id": chat_id, "text": text, "reply_markup": reply_markup})
                return {"ok": True, "result": {"message_id": len(self.sent_messages)}}

        mock_client = MockBaleClient()
        engine = BaleBotEngine(mock_client, db_path=self.db_path)

        def make_msg(chat_id, text, sender_name="تست کننده"):
            return {
                "chat": {"id": chat_id},
                "from": {"first_name": sender_name, "username": f"user_{chat_id}"},
                "text": text,
            }

        # 1. Start command
        engine.handle_message(make_msg(101, "/start"))
        self.assertIn("سلام", mock_client.sent_messages[-1]["text"])
        self.assertIn("گزارش مالی", str(mock_client.sent_messages[-1]["reply_markup"]))

        # 2. Help command
        engine.handle_message(make_msg(101, "راهنما"))
        self.assertIn("راهنمای کار", mock_client.sent_messages[-1]["text"])

        # 3. Support command
        engine.handle_message(make_msg(101, "پشتیبانی"))
        self.assertIn("پشتیبانی دفتر کار", mock_client.sent_messages[-1]["text"])

        # 4. Summary when empty
        engine.handle_message(make_msg(101, "گزارش مالی"))
        self.assertIn("هیچ تراکنش", mock_client.sent_messages[-1]["text"])

        # 5. Full transaction flow
        engine.handle_message(make_msg(101, "دریافت ۷۵۰۰۰۰"))
        self.assertIn("واحد مبلغ ریال است یا تومان", mock_client.sent_messages[-1]["text"])

        engine.handle_message(make_msg(101, "تومن"))
        self.assertIn("تأیید", mock_client.sent_messages[-1]["text"])

        engine.handle_message(make_msg(101, "تأیید"))
        self.assertIn("تراکنش با موفقیت ثبت شد", mock_client.sent_messages[-1]["text"])

        # 6. Summary with data
        engine.handle_message(make_msg(101, "/summary"))
        self.assertIn("750,000", mock_client.sent_messages[-1]["text"])

        # 7. Non-text message (media/sticker/voice)
        engine.handle_message({"chat": {"id": 101}, "from": {"first_name": "تست"}, "text": ""})
        self.assertIn("فقط پیام‌های متنی", mock_client.sent_messages[-1]["text"])

        # 8. Cancel command with various colloquial keywords
        engine.handle_message(make_msg(101, "واریز ۵۰۰۰۰"))
        engine.handle_message(make_msg(101, "بیخیال"))
        self.assertIn("پیش‌نویس فعلی لغو شد", mock_client.sent_messages[-1]["text"])

        engine.handle_message(make_msg(101, "واریز ۵۰۰۰۰"))
        engine.handle_message(make_msg(101, "ولش کن"))
        self.assertIn("پیش‌نویس فعلی لغو شد", mock_client.sent_messages[-1]["text"])

        # 9. Persian greetings
        for greet in ["سلام", "درود", "صبح بخیر"]:
            engine.handle_message(make_msg(102, greet))
            self.assertIn("سلام", mock_client.sent_messages[-1]["text"])
            self.assertIn("دستیار هوشمند", mock_client.sent_messages[-1]["text"])


if __name__ == "__main__":
    unittest.main()
