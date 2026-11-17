"""Tests for the production features added on gorgg/production-path:
nightly report, monthly CSV export, credit (نسیه/طلب) list, voice & photo input.
"""
from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.bale_bot import BaleBotEngine


class FeatureMockClient:
    def __init__(self):
        self.sent_messages = []
        self.sent_documents = []

    def send_message(self, chat_id, text, reply_markup=None, reply_to_message_id=None):
        self.sent_messages.append({"chat_id": str(chat_id), "text": text})
        return {"ok": True, "result": {"message_id": len(self.sent_messages)}}

    def send_document(self, chat_id, filename, content, caption=""):
        self.sent_documents.append(
            {"chat_id": str(chat_id), "filename": filename, "content": content, "caption": caption}
        )
        return {"ok": True, "result": {"message_id": 1}}

    def texts(self, chat_id=None):
        return [
            m["text"] for m in self.sent_messages if chat_id is None or m["chat_id"] == str(chat_id)
        ]


def make_msg(chat_id, text=None, **extra):
    msg = {
        "chat": {"id": chat_id},
        "from": {"first_name": "تست", "username": "tester"},
    }
    if text is not None:
        msg["text"] = text
    msg.update(extra)
    return msg


class ProductionFeaturesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.tmp.name) / "feat.sqlite3")
        self.client = FeatureMockClient()
        self.engine = BaleBotEngine(self.client, db_path=self.db_path)

    def tearDown(self):
        self.engine.store.close()
        self.tmp.cleanup()

    def confirm_sale(self, chat_id=42, text="فروش ۲۰۰ هزار تومان"):
        self.engine.handle_message(make_msg(chat_id, text))
        self.engine.handle_message(make_msg(chat_id, "تأیید"))

    # --- daily / nightly report ---

    def test_daily_report_only_counts_today(self):
        self.confirm_sale()
        report = self.engine.daily_report_text("42")
        self.assertIsNotNone(report)
        self.assertIn("200,000", report)
        self.assertIn("تعداد تراکنش: 1", report)

    def test_daily_report_empty_day_is_none(self):
        self.assertIsNone(self.engine.daily_report_text("999"))

    def test_nightly_report_sends_once_per_day(self):
        # 21:30 Tehran == 18:00 UTC (offset 210). The calendar date is
        # arbitrary; what matters is that the sale and the report share
        # ONE clock. The engine's confirm path stamps the transaction
        # with the _now helper it imported from src.conversation (bound
        # in src.bale_bot), so pin that clock to the same instant the
        # report is run for — otherwise the sale is stamped with the
        # real calendar day while the report is run for a fixed day,
        # and the two never meet (the old form of this test failed on
        # every date except 2026-10-28).
        evening_utc = datetime(2026, 10, 28, 18, 0, tzinfo=timezone.utc)
        with patch("src.bale_bot._now", return_value=evening_utc.isoformat()):
            self.confirm_sale()
        with patch.dict(os.environ, {"NIGHTLY_REPORT_ENABLED": "1", "NIGHTLY_REPORT_TIME": "21:00"}):
            sent_first = self.engine.send_nightly_reports(evening_utc)
            sent_second = self.engine.send_nightly_reports(evening_utc)
        self.assertEqual(sent_first, 1)
        self.assertEqual(sent_second, 0)
        nightly = [tx for tx in self.client.texts("42") if "گزارش امروز" in tx]
        self.assertEqual(len(nightly), 1)

    def test_nightly_report_respects_time_and_disable(self):
        self.confirm_sale()
        morning_utc = datetime(2026, 10, 28, 5, 0, tzinfo=timezone.utc)  # 08:30 Tehran
        evening_utc = datetime(2026, 10, 28, 18, 0, tzinfo=timezone.utc)
        with patch.dict(os.environ, {"NIGHTLY_REPORT_ENABLED": "1", "NIGHTLY_REPORT_TIME": "21:00"}):
            self.assertEqual(self.engine.send_nightly_reports(morning_utc), 0)
        with patch.dict(os.environ, {"NIGHTLY_REPORT_ENABLED": "0"}):
            self.assertEqual(self.engine.send_nightly_reports(evening_utc), 0)

    def test_daily_report_command(self):
        self.confirm_sale()
        self.engine.handle_message(make_msg(42, "گزارش امروز"))
        self.assertTrue(any("گزارش امروز" in tx for tx in self.client.texts("42")))

    # --- monthly export ---

    def test_month_csv_contains_confirmed_rows_with_description(self):
        self.engine.handle_message(make_msg(42, "فروش نسیه ۵۰۰ هزار تومان به احمدی"))
        self.engine.handle_message(make_msg(42, "تأیید"))
        local = self.engine._local_now()
        csv_text = self.engine.build_month_csv("42", local.year, local.month)
        lines = csv_text.strip().splitlines()
        self.assertEqual(lines[0], "date,direction,amount,unit,description,status")
        self.assertEqual(len(lines), 2)
        self.assertIn("500000", lines[1])
        self.assertIn("نسیه احمدی", lines[1])

    def test_export_command_sends_document(self):
        self.confirm_sale()
        self.engine.handle_message(make_msg(42, "خروجی ماه"))
        self.assertEqual(len(self.client.sent_documents), 1)
        doc = self.client.sent_documents[0]
        self.assertTrue(doc["filename"].startswith("ledger-"))
        self.assertTrue(doc["filename"].endswith(".csv"))

    def test_export_command_without_data_sends_notice(self):
        self.engine.handle_message(make_msg(77, "خروجی ماه"))
        self.assertEqual(len(self.client.sent_documents), 0)
        self.assertTrue(any("هنوز تراکنش" in tx for tx in self.client.texts("77")))

    # --- credit list ---

    def test_credit_list_shows_only_credit_items_with_ready_message(self):
        self.engine.handle_message(make_msg(42, "فروش نسیه ۵۰۰ هزار تومان به احمدی"))
        self.engine.handle_message(make_msg(42, "تأیید"))
        self.confirm_sale()  # normal sale, must not appear as credit
        self.engine.handle_message(make_msg(42, "طلب‌ها"))
        credit_msgs = [tx for tx in self.client.texts("42") if "پیام آماده" in tx]
        self.assertEqual(len(credit_msgs), 1)
        self.assertIn("نسیه احمدی", credit_msgs[0])
        self.assertIn("500,000", credit_msgs[0])

    def test_credit_list_empty_state(self):
        self.engine.handle_message(make_msg(43, "طلب‌ها"))
        self.assertTrue(any("مورد نسیه/طلب ثبت‌شده‌ای نداری" in tx for tx in self.client.texts("43")))

    def test_description_is_persisted_on_transaction(self):
        self.engine.handle_message(make_msg(42, "فروش نسیه ۵۰۰ هزار تومان به احمدی"))
        self.engine.handle_message(make_msg(42, "تأیید"))
        txs = self.engine.store.list_transactions("42")
        self.assertEqual(len(txs), 1)
        self.assertEqual(txs[0].description, "نسیه احمدی")

    # --- media input ---

    def test_voice_without_stt_config_asks_to_type(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("VOICE_STT_URL", None)
            self.engine.handle_message(make_msg(42, voice={"file_id": "v1", "duration": 3}))
        self.assertTrue(any("تبدیل صدا به متن" in tx for tx in self.client.texts("42")))

    def test_voice_with_transcription_flows_into_draft(self):
        with patch.dict(os.environ, {"VOICE_STT_URL": "https://stt.example/transcribe"}):
            with patch.object(self.engine, "_download_bale_file", return_value=b"fake-audio"):
                with patch.object(
                    self.engine, "_transcribe_audio", return_value="فروش ۲۰۰ هزار تومان"
                ):
                    self.engine.handle_message(make_msg(42, voice={"file_id": "v1", "duration": 3}))
        self.assertTrue(any("پیش‌نویس" in tx for tx in self.client.texts("42")))

    def test_voice_fallback_model_retries_on_primary_failure(self):
        import src.bale_bot as bale_bot

        calls = []

        def flaky(url, fields, files, headers=None, timeout=60):
            calls.append(fields["model"])
            if len(calls) == 1:
                raise RuntimeError("primary down")
            return {"text": "فروش ۱۰۰ هزار تومان"}

        env = {
            "VOICE_STT_URL": "https://stt.example/transcribe",
            "VOICE_STT_MODEL": "small-x",
            "VOICE_STT_FALLBACK_MODEL": "medium-x",
        }
        with patch.dict(os.environ, env):
            with patch.object(bale_bot, "_post_multipart", side_effect=flaky):
                text = self.engine._transcribe_audio(b"fake-audio")
        self.assertEqual(text, "فروش ۱۰۰ هزار تومان")
        self.assertEqual(calls, ["small-x", "medium-x"])

    def test_voice_no_fallback_configured_single_attempt(self):
        import src.bale_bot as bale_bot

        calls = []

        def down(url, fields, files, headers=None, timeout=60):
            calls.append(fields["model"])
            raise RuntimeError("down")

        env = {"VOICE_STT_URL": "https://stt.example/transcribe", "VOICE_STT_MODEL": "small-x"}
        with patch.dict(os.environ, env):
            os.environ.pop("VOICE_STT_FALLBACK_MODEL", None)
            with patch.object(bale_bot, "_post_multipart", side_effect=down):
                self.assertIsNone(self.engine._transcribe_audio(b"fake-audio"))
        self.assertEqual(calls, ["small-x"])

    def test_photo_without_ocr_config_asks_to_type(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("PHOTO_OCR_URL", None)
            self.engine.handle_message(
                make_msg(42, photo=[{"file_id": "p1", "file_size": 10}, {"file_id": "p2", "file_size": 99}])
            )
        self.assertTrue(any("خواندن خودکار عکس" in tx for tx in self.client.texts("42")))

    def test_photo_with_extraction_flows_into_draft(self):
        with patch.dict(os.environ, {"PHOTO_OCR_URL": "https://ocr.example/chat"}):
            with patch.object(self.engine, "_download_bale_file", return_value=b"fake-image"):
                with patch.object(
                    self.engine, "_extract_photo_text", return_value="خرید ۳۰۰ هزار تومان بابت بار"
                ):
                    self.engine.handle_message(
                        make_msg(42, photo=[{"file_id": "p2", "file_size": 99}])
                    )
        self.assertTrue(any("پیش‌نویس" in tx for tx in self.client.texts("42")))


if __name__ == "__main__":
    unittest.main()
