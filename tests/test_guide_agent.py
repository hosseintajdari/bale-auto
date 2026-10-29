"""Agent-layer tests (Part B): section 13 guide spine + section 11 soft layer.

Everything runs on a STUBBED model — no real calls. Covers:
- The guide replaces the /start wall: greeting + one question, buttons for
  choices, resumable across engine restarts, skippable.
- First real entry together completes the guide.
- SoftLayer: polish is used when the stub behaves; a stub that alters a
  figure is rejected verbatim; a dead model falls back to the template.
"""
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from src.agent_layer import ChatModel, SoftLayer, numbers_in
from src.bale_bot import BaleBotEngine


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


def make_msg(chat_id, text):
    return {
        "chat": {"id": chat_id},
        "from": {"id": chat_id, "first_name": "تست", "username": f"user_{chat_id}"},
        "text": text,
    }


def stub_transport(reply=None, error=None, recorder=None):
    def transport(url, api_key, payload, timeout):
        if recorder is not None:
            recorder.append(payload)
        if error is not None:
            raise error
        return {"choices": [{"message": {"content": reply}}]}

    return transport


def stub_model(reply=None, error=None, recorder=None):
    return ChatModel(
        "https://stub.invalid/v1/chat/completions",
        "stub-key",
        "stub-model",
        transport=stub_transport(reply=reply, error=error, recorder=recorder),
    )


class NumbersGuardTest(unittest.TestCase):
    def test_numbers_normalised_across_scripts(self):
        self.assertEqual(numbers_in("مبلغ ۵۰۰٬۰۰۰ تومان و 200,000 ریال"), ["200000", "500000"])
        self.assertEqual(numbers_in("هیچ عددی نیست"), [])


class SoftLayerTest(unittest.TestCase):
    def test_polish_used_when_numbers_intact(self):
        layer = SoftLayer(stub_model(reply="تراکنش شما با موفقیت ثبت شد! مبلغ: 200,000 تومان 🌿"))
        out = layer.polish("تراکنش با موفقیت ثبت شد.\nمبلغ: 200,000 تومان")
        self.assertIn("🌿", out)

    def test_polish_rejected_when_figure_altered(self):
        layer = SoftLayer(stub_model(reply="مبلغ شد 999,999 تومان"))
        original = "مبلغ: 200,000 تومان"
        self.assertEqual(layer.polish(original), original)

    def test_polish_rejected_when_figure_dropped(self):
        layer = SoftLayer(stub_model(reply="حتماً، انجام شد!"))
        original = "مبلغ: 200,000 تومان"
        self.assertEqual(layer.polish(original), original)

    def test_model_down_falls_back_to_template(self):
        layer = SoftLayer(stub_model(error=RuntimeError("quota exhausted")))
        original = "مبلغ: 200,000 تومان"
        self.assertEqual(layer.polish(original), original)

    def test_no_model_is_identity(self):
        self.assertEqual(SoftLayer(None).polish("سلام"), "سلام")
        self.assertFalse(SoftLayer(None).enabled)


class GuideBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.tmp.name) / "guide.sqlite3")
        self.client = MockClient()
        self.engine = BaleBotEngine(self.client, db_path=self.db_path)

    def tearDown(self):
        self.engine.store.close()
        self.tmp.cleanup()

    def say(self, chat_id, text):
        self.engine.handle_message(make_msg(chat_id, text))

    def guide_state(self, chat_id=42):
        state = self.engine.store.load_session(f"bale-session-{chat_id}", str(chat_id))
        return state.get("guide") or {}


class GuideFlowTest(GuideBase):
    def test_start_is_a_greeting_and_one_question_not_a_wall(self):
        self.say(42, "/start")
        last = self.client.sent_messages[-1]
        self.assertIn("دستیار هوشمند", last["text"])
        self.assertIn("کارت چیه", last["text"])
        self.assertIn("B", last["text"])  # referral code still visible
        labels = str(last["reply_markup"])
        for shop_type in ("مغازه و فروشگاه", "داروخانه"):
            self.assertIn(shop_type, labels)
        self.assertNotIn("امکانات سریع", last["text"])  # no feature dump

    def test_full_walk_and_first_entry_completes_guide(self):
        self.say(42, "/start")
        self.say(42, "داروخانه")
        self.assertIn("چی می‌فروشی", self.client.texts(42)[-1])
        self.say(42, "دارو و مکمل")
        self.assertIn("اولین فروشت", self.client.texts(42)[-1])
        self.say(42, "فروش ۲۰۰ هزار تومن")
        self.assertIn("پیش‌نویس", self.client.texts(42)[-1])
        self.say(42, "تأیید")
        texts = self.client.texts(42)
        self.assertTrue(any("تراکنش با موفقیت ثبت شد" in t for t in texts))
        self.assertTrue(any("تمام شد" in t for t in texts))  # guide completion
        self.assertTrue(self.guide_state()["done"])
        self.assertEqual(self.guide_state()["shop_type"], "داروخانه")
        self.assertEqual(self.guide_state()["goods"], "دارو و مکمل")
        txs = self.engine.store.list_transactions("42")
        self.assertEqual(len(txs), 1)
        self.assertEqual(txs[0].amount, 200_000)

    def test_guide_resumes_after_restart(self):
        self.say(42, "/start")
        self.say(42, "مغازه و فروشگاه")
        # new engine on the same DB = a service restart
        self.engine.store.close()
        client2 = MockClient()
        engine2 = BaleBotEngine(client2, db_path=self.db_path)
        try:
            engine2.handle_message(make_msg(42, "سلام"))
            self.assertIn("چی می‌فروشی", client2.texts(42)[-1])
        finally:
            engine2.store.close()
            self.engine = BaleBotEngine(self.client, db_path=self.db_path)

    def test_skip_guide(self):
        self.say(42, "/start")
        self.say(42, "رد کردن راهنما")
        self.assertTrue(self.guide_state()["done"])
        self.assertTrue(self.guide_state()["skipped"])
        self.say(42, "/start")
        self.assertIn("فقط بنویس یا ویس بفرست", self.client.texts(42)[-1])

    def test_goods_step_can_be_skipped(self):
        self.say(42, "/start")
        self.say(42, "سایر")
        self.say(42, "رد کردن این قدم")
        self.assertIn("اولین فروشت", self.client.texts(42)[-1])
        self.assertEqual(self.guide_state()["goods"], "")

    def test_veteran_user_gets_short_menu_not_guide(self):
        self.say(42, "فروش ۱۰۰ هزار تومان")
        self.say(42, "تأیید")
        self.say(42, "/start")
        self.assertIn("فقط بنویس یا ویس بفرست", self.client.texts(42)[-1])


class EnginePolishTest(GuideBase):
    def test_confirmation_polished_by_stub_model(self):
        calls = []
        self.engine.agent = SoftLayer(
            stub_model(reply="تراکنش با موفقیت ثبت شد! 🌿\nمبلغ: 200,000 تومان", recorder=calls)
        )
        self.say(42, "فروش ۲۰۰ هزار تومان")
        self.say(42, "تأیید")
        self.assertTrue(calls)  # the model was actually consulted
        self.assertIn("🌿", self.client.texts(42)[-1])

    def test_confirmation_falls_back_when_model_alters_figure(self):
        self.engine.agent = SoftLayer(stub_model(reply="ثبت شد! مبلغ: 999,999 تومان"))
        self.say(42, "فروش ۲۰۰ هزار تومان")
        self.say(42, "تأیید")
        last = self.client.texts(42)[-1]
        self.assertIn("200,000", last)
        self.assertNotIn("999,999", last)

    def test_confirmation_falls_back_when_model_down(self):
        self.engine.agent = SoftLayer(stub_model(error=RuntimeError("down")))
        self.say(42, "فروش ۲۰۰ هزار تومان")
        self.say(42, "تأیید")
        self.assertIn("تراکنش با موفقیت ثبت شد", self.client.texts(42)[-1])
        self.assertIn("200,000", self.client.texts(42)[-1])

    def test_guide_runs_entirely_on_stub_model(self):
        calls = []

        def echo_transport(url, api_key, payload, timeout):
            calls.append(payload)
            content = payload["messages"][-1]["content"]
            return {"choices": [{"message": {"content": content + " 🌿"}}]}

        self.engine.agent = SoftLayer(
            ChatModel("https://stub.invalid/v1/chat/completions", "k", "m", transport=echo_transport)
        )
        self.say(42, "/start")
        self.assertTrue(calls)  # model consulted, never the network
        self.assertIn("🌿", self.client.texts(42)[-1])  # polish flowed through
        self.say(42, "داروخانه")
        self.assertIn("چی می‌فروشی", self.client.texts(42)[-1])


if __name__ == "__main__":
    unittest.main()
