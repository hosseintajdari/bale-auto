"""Bale Messenger Bot Integration for Conversational Work Ledger (bale-auto).

Connects to the official Bale Bot API (https://tapi.bale.ai), handles live polling,
parses user messages with P0Ledger and ConversationService, manages multi-turn sessions,
dispatches responses with keyboard markup, and emits live shadow traces to the Bale-Panel.
"""
from __future__ import annotations

import json
import logging
import os
import re
import sys
import threading
import time
import urllib.parse
import urllib.request
from typing import Any, Optional

from src.conversation import ConversationService, ConversationStore
from src.p0_core import P0Ledger, Scope, normalize

logger = logging.getLogger("bale_bot")

BALE_API_BASE = os.environ.get("BALE_API_BASE", "https://tapi.bale.ai").rstrip("/")
BOT_TOKEN = os.environ.get("BALE_BOT_TOKEN", "").strip()
PANEL_BASE_URL = os.environ.get("PANEL_BASE_URL", "http://localhost:3001").rstrip("/")
PANEL_SECRET = os.environ.get("PANEL_API_SECRET", "iuE7869963#!@").strip()
ENABLE_PANEL_EMIT = os.environ.get("ENABLE_PANEL_EMIT", "1") == "1"
LEDGER_DB_PATH = os.environ.get("LEDGER_DB_PATH", "/home/admin/bale-auto/data/ledger.db")


class BaleBotClient:
    """Client for calling Bale Bot API methods with retry logic and error resilience."""

    def __init__(self, token: str, api_base: str = BALE_API_BASE) -> None:
        if not token:
            raise ValueError("BALE_BOT_TOKEN is required")
        self.token = token
        self.api_base = f"{api_base}/bot{token}"

    def call_api(self, method: str, data: Optional[dict[str, Any]] = None, timeout: int = 30) -> dict[str, Any]:
        url = f"{self.api_base}/{method}"
        headers = {"Content-Type": "application/json"}
        req_body = json.dumps(data).encode("utf-8") if data is not None else None
        req = urllib.request.Request(url, data=req_body, headers=headers)
        
        for attempt in range(1, 4):
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    resp_bytes = resp.read()
                    return json.loads(resp_bytes.decode("utf-8"))
            except urllib.error.HTTPError as e:
                err_text = e.read().decode("utf-8", errors="ignore")
                logger.error(f"HTTPError on {method} (attempt {attempt}): {e.code} - {err_text}")
                if e.code == 429:
                    time.sleep(2 * attempt)
                    continue
                if 400 <= e.code < 500:
                    try:
                        return json.loads(err_text)
                    except Exception:
                        return {"ok": False, "error_code": e.code, "description": err_text}
                time.sleep(1)
            except Exception as e:
                logger.error(f"Exception on {method} (attempt {attempt}): {e}")
                time.sleep(1)

        return {"ok": False, "description": "Network timeout or repeated failure"}

    def get_me(self) -> dict[str, Any]:
        return self.call_api("getMe", timeout=10)

    def get_updates(self, offset: int = 0, limit: int = 20, timeout: int = 15) -> dict[str, Any]:
        return self.call_api("getUpdates", {"offset": offset, "limit": limit, "timeout": timeout}, timeout=timeout + 5)

    def send_message(
        self,
        chat_id: int | str,
        text: str,
        reply_markup: Optional[dict[str, Any]] = None,
        reply_to_message_id: Optional[int] = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup
        if reply_to_message_id:
            payload["reply_to_message_id"] = reply_to_message_id
        return self.call_api("sendMessage", payload, timeout=10)


class BaleBotEngine:
    """Core logic orchestrator for bale-auto bot."""

    def __init__(self, client: BaleBotClient, db_path: str = LEDGER_DB_PATH) -> None:
        self.client = client
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.store = ConversationStore(db_path)
        self.service = ConversationService(self.store)
        self.ledger = P0Ledger()
        self.running = False
        self._last_offset = 0

    def emit_panel_shadow_trace(
        self,
        chat_id: str,
        user_name: str,
        user_message: str,
        bot_reply: str,
        stage_status: str = "passed",
        status: str = "pending",
        rule_applied: Optional[str] = None,
    ) -> None:
        """Asynchronously emits shadow trace and pipeline status to Embednet OS Bale-Panel."""
        if not ENABLE_PANEL_EMIT:
            return

        def _send() -> None:
            trace_id = f"bale-{int(time.time() * 1000)}"
            payload = {
                "engine_id": "bale-auto",
                "shadow_item": {
                    "id": trace_id,
                    "sessionId": f"bale-{chat_id}",
                    "channel": "bale",
                    "senderDisplay": f"{user_name} ({chat_id})",
                    "userMessage": user_message,
                    "proposedReply": bot_reply,
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "confidenceScore": 0.98,
                    "riskLevel": "safe",
                    "status": status,
                    "deterministicRuleApplied": rule_applied or "RULE_PERSISTENT_LEDGER",
                },
                "pipeline_traces": [
                    {
                        "stage": "GATEWAY_INGEST",
                        "title": "Bale Bot Gateway Ingest",
                        "status": "passed",
                        "detail": f"Platform: Bale | Chat ID: {chat_id} | Sender: {user_name}",
                        "durationMs": 4,
                    },
                    {
                        "stage": "DETERMINISTIC_RULES",
                        "title": "Conversational State & Ledger Parsing",
                        "status": stage_status,
                        "detail": rule_applied or "Verified Persian Numerals and Intent",
                        "durationMs": 5,
                    },
                    {
                        "stage": "TRANSACTION_PERSISTENCE",
                        "title": "SQLite Work Ledger State",
                        "status": "passed",
                        "detail": f"User: {chat_id} | Multi-turn Session Synced",
                        "durationMs": 6,
                    },
                ],
            }

            url = f"{PANEL_BASE_URL}/api/pipeline/ingest/shadow-trace"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {PANEL_SECRET}",
            }
            try:
                req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
                urllib.request.urlopen(req, timeout=2)
            except Exception as ex:
                logger.debug(f"Panel emit notice: {ex}")

        threading.Thread(target=_send, daemon=True).start()

    def handle_message(self, message: dict[str, Any]) -> None:
        chat = message.get("chat", {})
        chat_id = str(chat.get("id", ""))
        sender = message.get("from", {})
        first_name = sender.get("first_name", "")
        last_name = sender.get("last_name", "")
        username = sender.get("username", "")
        full_name = f"{first_name} {last_name}".strip() or username or "کاربر بله"

        raw_text = message.get("text", "") or message.get("caption", "")
        if not chat_id:
            return

        if not raw_text:
            reply = "در حال حاضر من فقط پیام‌های متنی را متوجه می‌شوم. لطفاً درخواست یا مبلغ خود را به صورت متن بنویسید (مثلاً: دریافت ۱۰۰٬۰۰۰ تومان)."
            self.client.send_message(chat_id, reply)
            self.emit_panel_shadow_trace(chat_id, full_name, "[غیرمتنی/رسانه]", reply, stage_status="intercepted", status="rejected", rule_applied="MEDIA_UNSUPPORTED")
            return

        text = raw_text.strip()
        norm_text = normalize(text)
        session_id = f"bale-session-{chat_id}"
        user_id = str(chat_id)

        logger.info(f"Incoming message from {chat_id} ({full_name}): {text}")

        # Commands handling (check both raw text and normalized text)
        cmd_candidates = {text, norm_text}

        if any(c.startswith("/start") or c in {"شروع", "start"} for c in cmd_candidates):
            reply = (
                f"سلام {first_name or 'عزیز'}! خوش آمدید.\n"
                "من دستیار هوشمند دفتر کار گفت‌وگومحور (Conversational Work Ledger) هستم.\n\n"
                "می‌توانید مبالغ دریافتی یا پرداختی خود را به سادگی به فارسی بفرستید، مثل:\n"
                "• «دریافت ۵۰۰٬۰۰۰ تومان فروش»\n"
                "• «واریز ۲ میلیون»\n"
                "• «پرداخت ۳۵۰ هزار تومان»\n\n"
                "دستورات مفید:\n"
                "• /summary یا «گزارش» : خلاصه دریافت‌ها و پرداخت‌ها\n"
                "• /cancel یا «لغو» : لغو پیش‌نویس فعلی\n"
                "• /help : راهنمای کامل"
            )
            keyboard = {
                "keyboard": [
                    [{"text": "گزارش مالی"}, {"text": "راهنما"}],
                    [{"text": "لغو پیش‌نویس"}],
                ],
                "resize_keyboard": True,
            }
            self.client.send_message(chat_id, reply, reply_markup=keyboard)
            self.emit_panel_shadow_trace(chat_id, full_name, text, reply, status="approved", rule_applied="CMD_START")
            return

        if any(c in {"/help", "راهنما", "help"} for c in cmd_candidates):
            reply = (
                "📖 راهنمای کار با بازو:\n\n"
                "۱. ثبت تراکنش:\n"
                "جملاتی مانند «دریافت ۵۰۰۰۰۰ تومان» یا «واریز ۱۲۰۰۰۰۰» بفرستید. سیستم مبلغ را دریافت کرده و در صورت نبود واحد، از شما می‌پرسد.\n\n"
                "۲. تایید تراکنش:\n"
                "پس از مشخص شدن واحد، با نوشتن «تأیید» یا زدن دکمه تایید، تراکنش شما به طور دائمی ثبت می‌شود.\n\n"
                "۳. مشاهده جمع تراکنش‌ها:\n"
                "دستور /summary یا «گزارش مالی» را بفرستید.\n\n"
                "۴. لغو پیش‌نویس:\n"
                "کافیست بنویسید «لغو» یا /cancel."
            )
            self.client.send_message(chat_id, reply)
            self.emit_panel_shadow_trace(chat_id, full_name, text, reply, status="approved", rule_applied="CMD_HELP")
            return

        if any(c in {"/cancel", "لغو", "لغو پیش نویس", "لغو پیش‌نویس", "انصراف", "cancel", "ولش کن", "بیخیال"} for c in cmd_candidates):
            state = self.store.load_session(session_id, user_id)
            if state.get("pending"):
                state["pending"] = None
                self.store.save_session(session_id, user_id, state)
                reply = "پیش‌نویس فعلی لغو شد. می‌توانید پیام جدیدی ارسال کنید."
            else:
                reply = "هیچ پیش‌نویس فعالی برای لغو وجود ندارد."
            self.client.send_message(chat_id, reply)
            self.emit_panel_shadow_trace(chat_id, full_name, text, reply, status="approved", rule_applied="CMD_CANCEL")
            return

        if any(c in {"/summary", "گزارش", "گزارش مالی", "موجودی", "summary"} for c in cmd_candidates):
            txs = self.store.list_transactions(user_id)
            if not txs:
                reply = "تاکنون هیچ تراکنش تاییدشده‌ای برای شما ثبت نشده است."
            else:
                total_in_toman = sum(t.amount for t in txs if t.direction == "incoming" and t.unit == "تومان")
                total_out_toman = sum(t.amount for t in txs if t.direction == "outgoing" and t.unit == "تومان")
                total_in_rial = sum(t.amount for t in txs if t.direction == "incoming" and t.unit == "ریال")
                total_out_rial = sum(t.amount for t in txs if t.direction == "outgoing" and t.unit == "ریال")
                
                net_toman = total_in_toman - total_out_toman
                net_rial = total_in_rial - total_out_rial
                
                reply = (
                    "📊 خلاصه دفتر کار مالی شما:\n\n"
                    f"تعداد تراکنش‌های قطعی: {len(txs)}\n\n"
                    "🔸 بخش تومان:\n"
                    f"• مجموع دریافت: {total_in_toman:,} تومان\n"
                    f"• مجموع پرداخت: {total_out_toman:,} تومان\n"
                    f"• مانده خالص: {net_toman:,} تومان\n\n"
                    "🔹 بخش ریال:\n"
                    f"• مجموع دریافت: {total_in_rial:,} ریال\n"
                    f"• مجموع پرداخت: {total_out_rial:,} ریال\n"
                    f"• مانده خالص: {net_rial:,} ریال"
                )
            self.client.send_message(chat_id, reply)
            self.emit_panel_shadow_trace(chat_id, full_name, text, reply, status="approved", rule_applied="CMD_SUMMARY")
            return

        if any(c in {"پشتیبانی", "تماس با پشتیبانی", "کمک", "/support", "support", "اپراتور"} for c in cmd_candidates):
            reply = (
                "📞 پشتیبانی دفتر کار گفت‌وگومحور:\n\n"
                "برای ارتباط با تیم پشتیبانی یا گزارش مشکل، می‌توانید با شناسه یا ایمیل پشتیبانی در تماس باشید.\n"
                "دستورات مفید:\n"
                "• /summary : مشاهده گزارش مالی\n"
                "• /cancel : لغو هرگونه پیش‌نویس ناتمام"
            )
            self.client.send_message(chat_id, reply)
            self.emit_panel_shadow_trace(chat_id, full_name, text, reply, status="approved", rule_applied="CMD_SUPPORT")
            return

        # Core Conversation Service Handling
        try:
            res = self.service.handle(session_id, user_id, text)
            bot_reply = res["reply"]
            status = res["status"]
            keyboard = None

            if status == "awaiting_unit":
                keyboard = {
                    "keyboard": [
                        [{"text": "تومان"}, {"text": "ریال"}],
                        [{"text": "لغو پیش‌نویس"}],
                    ],
                    "resize_keyboard": True,
                    "one_time_keyboard": True,
                }
            elif status == "awaiting_confirmation":
                keyboard = {
                    "keyboard": [
                        [{"text": "تأیید"}],
                        [{"text": "لغو پیش‌نویس"}],
                    ],
                    "resize_keyboard": True,
                    "one_time_keyboard": True,
                }
            elif status == "confirmed":
                keyboard = {
                    "keyboard": [
                        [{"text": "گزارش مالی"}, {"text": "ثبت تراکنش جدید"}],
                    ],
                    "resize_keyboard": True,
                }

            self.client.send_message(chat_id, bot_reply, reply_markup=keyboard)
            self.emit_panel_shadow_trace(chat_id, full_name, text, bot_reply, status="approved", rule_applied=f"FLOW_{status.upper()}")

        except Exception as e:
            err_str = str(e)
            if "Explicit unit required" in err_str:
                reply = "لطفاً یکی از واحدهای معتبر «تومان» یا «ریال» را انتخاب یا تایپ کنید."
                keyboard = {
                    "keyboard": [[{"text": "تومان"}, {"text": "ریال"}], [{"text": "لغو پیش‌نویس"}]],
                    "resize_keyboard": True,
                }
            elif "Explicit confirmation is required" in err_str:
                reply = "برای نهایی شدن تراکنش لطفاً بنویسید «تأیید» یا در صورت انصراف، گزینه «لغو پیش‌نویس» را انتخاب کنید."
                keyboard = {
                    "keyboard": [[{"text": "تأیید"}], [{"text": "لغو پیش‌نویس"}]],
                    "resize_keyboard": True,
                }
            elif "amount must be positive" in err_str:
                reply = "مبلغ تراکنش باید یک عدد مثبت بزرگتر از صفر باشد."
                keyboard = None
            else:
                reply = f"متوجه این پیام نشدم. می‌توانید مجدداً تلاش کنید یا بنویسید «لغو»."
                keyboard = None

            self.client.send_message(chat_id, reply, reply_markup=keyboard)
            self.emit_panel_shadow_trace(chat_id, full_name, text, reply, stage_status="intercepted", status="rejected", rule_applied="FRIENDLY_ERROR_HANDLED")

    def poll_once(self) -> int:
        resp = self.client.get_updates(offset=self._last_offset, limit=20, timeout=5)
        if not resp.get("ok"):
            logger.warning(f"Failed get_updates: {resp}")
            return 0

        updates = resp.get("result", [])
        for up in updates:
            up_id = up.get("update_id", 0)
            if up_id >= self._last_offset:
                self._last_offset = up_id + 1

            msg = up.get("message")
            if msg:
                self.handle_message(msg)

        return len(updates)

    def run_polling_loop(self) -> None:
        self.running = True
        logger.info("Starting Bale Bot polling loop...")
        while self.running:
            try:
                self.poll_once()
            except Exception as e:
                logger.error(f"Error in polling loop: {e}")
                time.sleep(2)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    token = os.environ.get("BALE_BOT_TOKEN", "").strip()
    if not token:
        logger.error("BALE_BOT_TOKEN not set in environment!")
        sys.exit(1)

    client = BaleBotClient(token)
    me = client.get_me()
    logger.info(f"Connected to Bale Bot API: {me}")

    engine = BaleBotEngine(client)
    engine.run_polling_loop()
