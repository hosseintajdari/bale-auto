"""Regression tests for the photo-OCR hardening on gorgg/photo-html-timeout:

- HTML markup in the vision model's output (e.g. <div dir="rtl">...</div>)
  is stripped before the text is parsed/stored, so it can never leak into a
  transaction's «بابت» shown to users.
- The photo path uses a 100s timeout (a cold first vision call takes ~80s)
  and retries exactly once on timeout; the warm retry lands fast.
"""
from __future__ import annotations

import io
import json
import os
from pathlib import Path
import tempfile
import unittest
import urllib.error
from unittest.mock import patch

from src.bale_bot import BaleBotEngine


class _FakeResp:
    """Minimal stand-in for the urlopen context manager."""

    def __init__(self, content_text: str):
        body = json.dumps(
            {"choices": [{"message": {"content": content_text}}]}
        ).encode("utf-8")
        self._buf = io.BytesIO(body)

    def read(self, *args):
        return self._buf.read()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _MockClient:
    def __init__(self):
        self.sent_messages = []

    def send_message(self, chat_id, text, reply_markup=None, reply_to_message_id=None):
        self.sent_messages.append({"chat_id": str(chat_id), "text": text})
        return {"ok": True, "result": {"message_id": len(self.sent_messages)}}

    def texts(self, chat_id=None):
        return [
            m["text"]
            for m in self.sent_messages
            if chat_id is None or m["chat_id"] == str(chat_id)
        ]


def _photo_msg(chat_id=42):
    return {
        "chat": {"id": chat_id},
        "from": {"first_name": "تست", "username": "tester"},
        "photo": [{"file_id": "p2", "file_size": 99}],
    }


OCR_ENV = {"PHOTO_OCR_URL": "https://ocr.example/chat"}
CLEAN = "خرید ۳۰۰ هزار تومان بابت بار"
DIV_WRAPPED = '<div dir="rtl">' + CLEAN + "</div>"


class PhotoOcrHardeningTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.tmp.name) / "photo.sqlite3")
        self.client = _MockClient()
        self.engine = BaleBotEngine(self.client, db_path=self.db_path)

    def tearDown(self):
        self.engine.store.close()
        self.tmp.cleanup()

    def test_extract_strips_div_wrapper(self):
        with patch.dict(os.environ, OCR_ENV):
            with patch(
                "urllib.request.urlopen", return_value=_FakeResp(DIV_WRAPPED)
            ):
                text = self.engine._extract_photo_text(b"fake-image")
        self.assertEqual(text, CLEAN)

    def test_div_markup_does_not_leak_into_draft(self):
        with patch.dict(os.environ, OCR_ENV):
            with patch.object(
                self.engine, "_download_bale_file", return_value=b"fake-image"
            ):
                with patch(
                    "urllib.request.urlopen", return_value=_FakeResp(DIV_WRAPPED)
                ):
                    self.engine.handle_message(_photo_msg())
        joined = "\n".join(self.client.texts("42"))
        self.assertIn("بابت: بار", joined)
        self.assertNotIn("<div", joined)
        self.assertNotIn("dir=", joined)
        self.assertNotIn("</div>", joined)

    def test_timeout_retries_once_then_succeeds(self):
        timeouts = []

        def flaky(req, timeout=None, **kwargs):
            timeouts.append(timeout)
            if len(timeouts) == 1:
                raise urllib.error.URLError(TimeoutError("timed out"))
            return _FakeResp("فروش ۱۰۰ هزار تومان")

        with patch.dict(os.environ, OCR_ENV):
            with patch("urllib.request.urlopen", side_effect=flaky):
                text = self.engine._extract_photo_text(b"fake-image")
        self.assertEqual(text, "فروش ۱۰۰ هزار تومان")
        self.assertEqual(len(timeouts), 2)
        self.assertEqual(timeouts, [100, 100])

    def test_timeout_gives_up_after_exactly_one_retry(self):
        calls = []

        def always_timeout(req, timeout=None, **kwargs):
            calls.append(timeout)
            raise urllib.error.URLError(TimeoutError("timed out"))

        with patch.dict(os.environ, OCR_ENV):
            with patch("urllib.request.urlopen", side_effect=always_timeout):
                text = self.engine._extract_photo_text(b"fake-image")
        self.assertIsNone(text)
        self.assertEqual(len(calls), 2)


if __name__ == "__main__":
    unittest.main()
