import tempfile
import unittest
from pathlib import Path

from src.conversation import ConversationService, ConversationStore


class PersistentConversationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.tmp.name) / "ledger.sqlite3")
        self.store = ConversationStore(self.path)
        self.service = ConversationService(self.store)

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_multi_turn_state_survives_new_service_instance(self):
        first = self.service.handle("chat-1", "user-1", "دریافت ۵۰۰۰۰ تومان")
        self.assertEqual("awaiting_unit", first["status"])
        self.store.close()

        reopened = ConversationStore(self.path)
        second_service = ConversationService(reopened)
        second = second_service.handle("chat-1", "user-1", "تومان")
        self.assertEqual("awaiting_confirmation", second["status"])
        third = second_service.handle("chat-1", "user-1", "تأیید")
        self.assertEqual("confirmed", third["status"])
        self.assertEqual(50000, third["transaction"].amount)
        reopened.close()

        final_store = ConversationStore(self.path)
        records = final_store.list_transactions("user-1", "chat-1")
        self.assertEqual(1, len(records))
        self.assertEqual("تومان", records[0].unit)
        self.assertEqual("incoming", records[0].direction)
        final_store.close()

    def test_transaction_is_not_written_before_confirmation(self):
        self.service.handle("chat-2", "user-2", "پرداخت ۱۰۰۰")
        self.service.handle("chat-2", "user-2", "ریال")
        self.assertEqual([], self.store.list_transactions("user-2"))
        with self.assertRaises(ValueError):
            self.service.handle("chat-2", "user-2", "بله")
        self.assertEqual([], self.store.list_transactions("user-2"))

    def test_session_and_transaction_are_isolated_by_user(self):
        self.service.handle("private-chat", "owner", "واریز ۲۰۰۰")
        with self.assertRaises(PermissionError):
            self.service.handle("private-chat", "intruder", "تومان")
        with self.assertRaises(PermissionError):
            self.store.list_messages("private-chat", "intruder")

    def test_save_session_inserts_missing_session(self):
        state = {"pending": {"amount": 25}}
        self.store.save_session("missing-chat", "owner", state)
        self.assertEqual(state, self.store.load_session("missing-chat", "owner"))

    def test_save_session_does_not_overwrite_another_users_session(self):
        original = self.store.load_session("private-chat", "owner")
        with self.assertRaises(PermissionError):
            self.store.save_session("private-chat", "intruder", {"pending": None})
        self.assertEqual(original, self.store.load_session("private-chat", "owner"))

    def test_message_history_contains_every_turn(self):
        self.service.handle("chat-3", "user-3", "دریافت ۳۰۰ تومان")
        self.service.handle("chat-3", "user-3", "تومان")
        self.service.handle("chat-3", "user-3", "تایید و ثبت")
        messages = self.store.list_messages("chat-3", "user-3")
        self.assertEqual(["user", "assistant", "user", "assistant", "user", "assistant"], [m["role"] for m in messages])


if __name__ == "__main__":
    unittest.main()
