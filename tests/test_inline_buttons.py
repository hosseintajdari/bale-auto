"""Inline tap-button tests for the Bale bot (دکمه لمسی داخل پیام).

Covers:
1. Draft preview carries inline ✅ تأیید / ❌ لغو buttons bound to the draft.
2. Direction clarification carries inline direction buttons.
3. A tap runs the exact same commit/cancel path as typing (ledger equality).
4. Conflict classes:
   - stale buttons (after confirm / cancel / replacement) are safe no-ops;
   - double-tap confirms exactly one transaction;
   - cross-user callbacks never touch another chat's draft;
   - tap/type interleaving resolves to one coherent outcome;
   - buttons rendered before a restart still work on the persisted draft.
"""
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from src.bale_bot import BaleBotEngine


class InlineMockClient:
    def __init__(self):
        self.sent_messages = []
        self.answered_callbacks = []

    def send_message(self, chat_id, text, reply_markup=None, reply_to_message_id=None):
        self.sent_messages.append(
            {"chat_id": chat_id, "text": text, "reply_markup": reply_markup}
        )
        return {"ok": True, "result": {"message_id": len(self.sent_messages)}}

    def answer_callback_query(self, callback_query_id, text=None, show_alert=False):
        self.answered_callbacks.append(
            {"id": callback_query_id, "text": text, "show_alert": show_alert}
        )
        return {"ok": True}

    def texts_for(self, chat_id):
        return [m["text"] for m in self.sent_messages if str(m["chat_id"]) == str(chat_id)]


class PollingInlineMockClient(InlineMockClient):
    def __init__(self, updates):
        super().__init__()
        self.updates = updates

    def get_updates(self, offset, limit=20, timeout=5):
        return {"ok": True, "result": self.updates}


class InlineButtonsTestSuite(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.tmp.name) / "test_inline.sqlite3")
        self.client = InlineMockClient()
        self.engine = BaleBotEngine(self.client, db_path=self.db_path)

    def tearDown(self):
        self.engine.store.close()
        self.tmp.cleanup()

    # -- helpers -----------------------------------------------------------
    def make_msg(self, chat_id: int, text: str):
        return {
            "chat": {"id": chat_id},
            "from": {"id": chat_id, "first_name": "حاجی بازاری", "username": f"user_{chat_id}"},
            "text": text,
        }

    def make_callback(self, chat_id: int, data: str, sender_id: int | None = None, qid: str = "q1"):
        return {
            "id": qid,
            "from": {
                "id": chat_id if sender_id is None else sender_id,
                "first_name": "حاجی بازاری",
            },
            "message": {"message_id": 42, "chat": {"id": chat_id, "type": "private"}},
            "data": data,
        }

    def pending(self, chat_id: int):
        state = self.engine.store.load_session(f"bale-session-{chat_id}", str(chat_id))
        return state.get("pending")

    def txs(self, chat_id: int):
        return self.engine.store.list_transactions(str(chat_id))

    def button_data(self, chat_id: int, label_part: str):
        """Find callback_data of the latest inline button whose text contains label_part."""
        for msg in reversed(self.client.sent_messages):
            if str(msg["chat_id"]) != str(chat_id):
                continue
            markup = msg.get("reply_markup") or {}
            for row in markup.get("inline_keyboard", []):
                for btn in row:
                    if label_part in btn.get("text", ""):
                        return btn["callback_data"]
        return None

    def make_confirm_draft(self, chat_id: int, text: str = "فروش ۳ میلیون تومان"):
        self.engine.handle_message(self.make_msg(chat_id, text))
        return self.button_data(chat_id, "تأیید")

    def make_direction_draft(self, chat_id: int):
        self.engine.handle_message(self.make_msg(chat_id, "۵۰۰ هزار تومان علی"))
        return self.pending(chat_id)

    # -- feature: buttons are rendered, bound to the draft -----------------
    def test_preview_carries_inline_confirm_and_cancel_bound_to_draft(self):
        user = 900
        self.engine.handle_message(self.make_msg(user, "فروش ۳ میلیون تومان"))
        last = self.client.sent_messages[-1]
        self.assertIn("پیش‌نویس تراکنش آماده ثبت", last["text"])
        markup = last["reply_markup"]
        self.assertIn("inline_keyboard", markup)
        datas = [b["callback_data"] for row in markup["inline_keyboard"] for b in row]
        draft_id = self.pending(user)["draft_id"]
        self.assertIn(f"cfm:{draft_id}", datas)
        self.assertIn(f"cnl:{draft_id}", datas)

    def test_direction_question_carries_inline_direction_buttons(self):
        user = 901
        pending = self.make_direction_draft(user)
        self.assertEqual("awaiting_direction", pending["status"])
        last = self.client.sent_messages[-1]
        datas = [
            b["callback_data"]
            for row in last["reply_markup"]["inline_keyboard"]
            for b in row
        ]
        self.assertIn(f"din:{pending['draft_id']}", datas)
        self.assertIn(f"dou:{pending['draft_id']}", datas)

    # -- feature: taps run the same paths as typing -------------------------
    def test_callback_confirm_commits_identically_to_typing(self):
        typed_user, tap_user = 910, 911
        self.engine.handle_message(self.make_msg(typed_user, "فروش ۳ میلیون تومان"))
        self.engine.handle_message(self.make_msg(typed_user, "تأیید"))

        cfm = self.make_confirm_draft(tap_user)
        self.engine.handle_callback_query(self.make_callback(tap_user, cfm))

        typed_txs, tap_txs = self.txs(typed_user), self.txs(tap_user)
        self.assertEqual(1, len(typed_txs))
        self.assertEqual(1, len(tap_txs))
        for attr in ("amount", "unit", "direction", "description", "status"):
            self.assertEqual(getattr(typed_txs[0], attr), getattr(tap_txs[0], attr))
        self.assertIsNone(self.pending(tap_user))
        self.assertIn("تراکنش با موفقیت ثبت شد", self.client.texts_for(tap_user)[-1])
        # The tap was answered so the client does not spin.
        self.assertEqual(1, len(self.client.answered_callbacks))

    def test_callback_cancel_discards_draft_like_typing(self):
        user = 912
        cfm = self.make_confirm_draft(user)
        cnl = cfm.replace("cfm:", "cnl:")
        self.engine.handle_callback_query(self.make_callback(user, cnl))
        self.assertEqual([], self.txs(user))
        self.assertIsNone(self.pending(user))
        self.assertIn("پیش‌نویس فعلی لغو شد", self.client.texts_for(user)[-1])

    def test_callback_direction_buttons_resolve_then_confirm(self):
        for user, action, direction in ((920, "din", "incoming"), (921, "dou", "outgoing")):
            pending = self.make_direction_draft(user)
            data = self.button_data(user, "دریافت" if action == "din" else "پرداخت")
            self.assertTrue(data.startswith(f"{action}:"))
            self.engine.handle_callback_query(self.make_callback(user, data))
            resolved = self.pending(user)
            self.assertEqual("awaiting_confirmation", resolved["status"])
            self.assertEqual(direction, resolved["direction"])
            # Same draft identity across the stage transition.
            self.assertEqual(pending["draft_id"], resolved["draft_id"])
            cfm = self.button_data(user, "تأیید")
            self.engine.handle_callback_query(self.make_callback(user, cfm, qid="q2"))
            txs = self.txs(user)
            self.assertEqual(1, len(txs))
            self.assertEqual(500000, txs[0].amount)
            self.assertEqual(direction, txs[0].direction)

    # -- conflict 1: stale buttons ------------------------------------------
    def test_stale_confirm_after_typed_cancel_is_noop(self):
        user = 930
        cfm = self.make_confirm_draft(user)
        self.engine.handle_message(self.make_msg(user, "لغو"))
        self.assertIsNone(self.pending(user))
        self.engine.handle_callback_query(self.make_callback(user, cfm))
        self.assertEqual([], self.txs(user))
        self.assertIn("دیگر فعال نیست", self.client.texts_for(user)[-1])

    def test_stale_confirm_after_replacement_commits_only_new_draft(self):
        user = 931
        old_cfm = self.make_confirm_draft(user, "فروش ۲ میلیون تومان")
        # A fresh typed transaction replaces the pending draft.
        new_cfm = self.make_confirm_draft(user, "فروش ۳ میلیون تومان")
        self.assertNotEqual(old_cfm, new_cfm)
        self.engine.handle_callback_query(self.make_callback(user, old_cfm))
        self.assertEqual([], self.txs(user))
        self.assertEqual(3_000_000, self.pending(user)["amount"])
        self.engine.handle_callback_query(self.make_callback(user, new_cfm, qid="q2"))
        txs = self.txs(user)
        self.assertEqual(1, len(txs))
        self.assertEqual(3_000_000, txs[0].amount)

    # -- conflict 2: double-tap ----------------------------------------------
    def test_double_tap_confirm_commits_exactly_once(self):
        user = 940
        cfm = self.make_confirm_draft(user)
        self.engine.handle_callback_query(self.make_callback(user, cfm, qid="q1"))
        self.engine.handle_callback_query(self.make_callback(user, cfm, qid="q2"))
        self.assertEqual(1, len(self.txs(user)))
        self.assertEqual(2, len(self.client.answered_callbacks))
        self.assertIn("دیگر فعال نیست", self.client.answered_callbacks[-1]["text"] or "")

    # -- conflict 3: cross-user -----------------------------------------------
    def test_cross_user_tap_cannot_touch_another_chats_draft(self):
        owner, stranger = 950, 951
        cfm = self.make_confirm_draft(owner)
        sent_before = len(self.client.sent_messages)
        # Callback replayed in the owner's chat but carrying a stranger's id.
        forged = self.make_callback(owner, cfm, sender_id=stranger)
        self.engine.handle_callback_query(forged)
        self.assertEqual([], self.txs(owner))
        self.assertIsNotNone(self.pending(owner))
        # No message was injected into the owner's chat.
        self.assertEqual(sent_before, len(self.client.sent_messages))

        # The stranger tapping with the owner's token in their own chat is
        # just a stale tap on an empty session.
        self.engine.handle_callback_query(self.make_callback(stranger, cfm, qid="q9"))
        self.assertEqual([], self.txs(stranger))
        self.assertEqual([], self.txs(owner))
        self.assertIsNotNone(self.pending(owner))

    # -- conflict 4: interleaving taps and typing ------------------------------
    def test_interleave_tap_direction_then_type_new_transaction(self):
        user = 960
        pending = self.make_direction_draft(user)
        din = self.button_data(user, "دریافت")
        self.engine.handle_callback_query(self.make_callback(user, din))
        self.assertEqual("awaiting_confirmation", self.pending(user)["status"])
        old_cfm = self.button_data(user, "تأیید")
        # User changes their mind and types a brand-new transaction instead.
        new_cfm = self.make_confirm_draft(user, "فروش ۳ میلیون تومان")
        self.engine.handle_callback_query(self.make_callback(user, old_cfm, qid="q-old"))
        self.assertEqual([], self.txs(user))
        self.engine.handle_callback_query(self.make_callback(user, new_cfm, qid="q-new"))
        txs = self.txs(user)
        self.assertEqual(1, len(txs))
        self.assertEqual(3_000_000, txs[0].amount)

    def test_interleave_type_direction_then_stale_direction_tap(self):
        user = 961
        self.make_direction_draft(user)
        din = self.button_data(user, "دریافت")
        self.engine.handle_message(self.make_msg(user, "دریافت"))
        self.assertEqual("awaiting_confirmation", self.pending(user)["status"])
        # The old direction button is now stale: tapping it changes nothing.
        self.engine.handle_callback_query(self.make_callback(user, din))
        pending = self.pending(user)
        self.assertEqual("awaiting_confirmation", pending["status"])
        self.assertEqual("incoming", pending["direction"])
        self.engine.handle_message(self.make_msg(user, "تأیید"))
        txs = self.txs(user)
        self.assertEqual(1, len(txs))
        self.assertEqual("incoming", txs[0].direction)

    # -- conflict 5: buttons rendered before a restart --------------------------
    def test_buttons_survive_restart_via_persisted_draft(self):
        user = 970
        cfm = self.make_confirm_draft(user)
        self.engine.store.close()
        client2 = InlineMockClient()
        self.engine = BaleBotEngine(client2, db_path=self.db_path)
        self.engine.handle_callback_query(self.make_callback(user, cfm))
        txs = self.txs(user)
        self.assertEqual(1, len(txs))
        self.assertEqual(3_000_000, txs[0].amount)

    # -- routing: poll_once delivers callback_query updates ----------------------
    def test_poll_once_routes_callback_query_and_advances_offset(self):
        user = 980
        cfm = self.make_confirm_draft(user)
        callback = self.make_callback(user, cfm)
        polling_client = PollingInlineMockClient(
            [{"update_id": 77, "callback_query": callback}]
        )
        self.engine.client = polling_client
        processed = self.engine.poll_once()
        self.assertEqual(1, processed)
        self.assertEqual(78, self.engine._last_offset)
        self.assertEqual(1, len(self.txs(user)))


if __name__ == "__main__":
    unittest.main()
