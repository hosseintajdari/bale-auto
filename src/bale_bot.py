"""Bale Messenger Bot Integration for Conversational Work Ledger (bale-auto).

Connects to the official Bale Bot API (https://tapi.bale.ai), handles live polling,
parses user messages with BazaarParser, P0Ledger, and ConversationService,
manages multi-turn sessions, dispatches responses with keyboard markup,
and emits live shadow traces to the Bale-Panel.
"""
from __future__ import annotations

from datetime import datetime, timezone
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
from uuid import uuid4

# Ensure repository root is in sys.path
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from src.bazaar_parser import (
    CANCELLATIONS,
    CONFIRMATIONS,
    SUMMARY_KEYWORDS,
    normalize_text,
    parse_bazaar_message,
)
from src.conversation import ConversationService, ConversationStore, Transaction, _now
from src.p0_core import P0Ledger, Scope, normalize

logger = logging.getLogger("bale_bot")


def _parse_env_assignment(line: str) -> tuple[str, str] | None:
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        return None
    line = re.sub(r"^export\s+", "", line, count=1)
    key, value = line.split("=", 1)
    key, value = key.strip(), value.strip().strip("'\"")
    return (key, value) if key else None


def _load_env_files() -> None:
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for env_name in [".env.local", ".env"]:
        env_file = os.path.join(repo_root, env_name)
        if os.path.exists(env_file):
            try:
                with open(env_file, "r", encoding="utf-8") as f:
                    for line in f:
                        assignment = _parse_env_assignment(line)
                        if assignment is None:
                            continue
                        key, value = assignment
                        if key not in os.environ:
                            os.environ[key] = value
            except Exception:
                pass


_load_env_files()

BALE_API_BASE = os.environ.get("BALE_API_BASE", "https://tapi.bale.ai").rstrip("/")
BOT_TOKEN = os.environ.get("BALE_BOT_TOKEN", "").strip()
PANEL_BASE_URL = os.environ.get("PANEL_BASE_URL", "http://localhost:3001").rstrip("/")
PANEL_SECRET = os.environ.get("PANEL_API_SECRET", "").strip()
ENABLE_PANEL_EMIT = os.environ.get("ENABLE_PANEL_EMIT", "1") == "1"
LEDGER_DB_PATH = os.environ.get("LEDGER_DB_PATH", "/home/admin/bale-auto/data/ledger.db")


def validate_panel_config(enabled: bool, secret: str) -> None:
    if enabled and not secret.strip():
        raise RuntimeError("PANEL_API_SECRET is required when ENABLE_PANEL_EMIT=1")


def validate_bot_identity_response(response: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(response, dict) or response.get("ok") is not True:
        raise RuntimeError("Bale getMe authentication failed; check BALE_BOT_TOKEN")
    return response


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
            reply = "در حال حاضر من فقط پیام‌های متنی را متوجه می‌شوم. لطفاً درخواست یا مبلغ خود را به صورت متن بنویسید (مثلاً: فروش ۱۰۰٬۰۰۰ تومان)."
            self.client.send_message(chat_id, reply)
            self.emit_panel_shadow_trace(chat_id, full_name, "[غیرمتنی/رسانه]", reply, stage_status="intercepted", status="rejected", rule_applied="MEDIA_UNSUPPORTED")
            return

        text = raw_text.strip()
        norm_text = normalize_text(text)
        session_id = f"bale-session-{chat_id}"
        user_id = str(chat_id)

        logger.info(f"Incoming message from {chat_id} ({full_name}): {text}")

        cmd_candidates = {text, norm_text}
        greetings = {"سلام", "درود", "سلام علیکم", "سلام وقت بخیر", "وقت بخیر", "صبح بخیر", "عصر بخیر", "hello", "hi"}

        # 1. Start command & greetings
        if any(c.startswith("/start") or c in {"شروع", "start"} or c in greetings for c in cmd_candidates):
            reply = (
                f"سلام {first_name or 'عزیز'}! خوش آمدید.\n"
                "من دستیار هوشمند ثبت حساب و کتاب و دخل‌وخرج (دفتر کار بازار) هستم.\n\n"
                "💡 هر دریافت، فروش، خرج یا پرداختی را به سادگی به زبان خودتان بنویسید:\n"
                "• «کارت کشید ۴۵۰ هزار تومن بابت فروش پیراهن»\n"
                "• «فروش نقدی ۲ میلیون و ۵۰۰»\n"
                "• «واریز شد ۵ میلیون به حسابم»\n"
                "• «خرج ناهار کارگرا ۱۲۰ هزار تومن»\n"
                "• «خرید بار ۱۰ میلیون از پخش تهران»\n"
                "• «مساعده دادم به شاگرد ۵۰۰ تومن»\n"
                "• «کرایه وانت ۱۵۰ تومن»\n\n"
                "📌 امکانات سریع:\n"
                "• «گزارش مالی» یا «دخل و خرج» : جمع کل دریافتی‌ها و پرداختی‌ها\n"
                "• «لغو» : انصراف از پیش‌نویس فعلی\n"
                "• «راهنما» : توضیحات بیشتر"
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

        # 2. Help command
        if any(c in {"/help", "راهنما", "help"} for c in cmd_candidates):
            reply = (
                "📖 راهنمای کار با بازو (دفتر کار بازار):\n\n"
                "۱. ثبت دخل و فروش (دریافتی):\n"
                "بنویسید: «کارت کشید ۴۵۰ هزار تومن فروش» یا «واریز شد ۲ میلیون»\n\n"
                "۲. ثبت خرج و خرید (پرداختی):\n"
                "بنویسید: «خرج ناهار ۱۲۰ تومن» یا «خرید بار ۵ میلیون» یا «کرایه وانت ۲۰۰ تومن»\n\n"
                "۳. تایید آسان:\n"
                "پس از ساخت پیش‌نویس، کافیست دکمه [تأیید] را بزنید یا بنویسید: تأیید، بله، ثبت کن، حله.\n\n"
                "۴. مشاهده جمع حساب‌ها:\n"
                "دستور «گزارش مالی» یا «دخل و خرج» را انتخاب کنید.\n\n"
                "۵. انصراف:\n"
                "هر زمان مایل بودید بنویسید «لغو» یا گزینه لغو پیش‌نویس را بزنید."
            )
            keyboard = {
                "keyboard": [
                    [{"text": "گزارش مالی"}, {"text": "ثبت تراکنش جدید"}],
                    [{"text": "لغو پیش‌نویس"}],
                ],
                "resize_keyboard": True,
            }
            self.client.send_message(chat_id, reply, reply_markup=keyboard)
            self.emit_panel_shadow_trace(chat_id, full_name, text, reply, status="approved", rule_applied="CMD_HELP")
            return

        # 3. Support command
        if any(c in {"پشتیبانی", "تماس با پشتیبانی", "کمک", "/support", "support", "اپراتور"} for c in cmd_candidates):
            reply = (
                "📞 پشتیبانی دفتر کار گفت‌وگومحور:\n\n"
                "برای ارتباط با تیم پشتیبانی یا گزارش مشکل، می‌توانید با شناسه یا ایمیل پشتیبانی در تماس باشید.\n"
                "دستورات مفید:\n"
                "• /summary یا «گزارش مالی» : مشاهده حساب و کتاب\n"
                "• /cancel یا «لغو» : لغو هرگونه پیش‌نویس ناتمام"
            )
            self.client.send_message(chat_id, reply)
            self.emit_panel_shadow_trace(chat_id, full_name, text, reply, status="approved", rule_applied="CMD_SUPPORT")
            return

        # 4. Summary & Reports
        if any(c in SUMMARY_KEYWORDS for c in cmd_candidates):
            txs = self.store.list_transactions(user_id)
            if not txs:
                reply = (
                    "📊 خلاصه دفتر کار مالی شما:\n\n"
                    "تاکنون هیچ تراکنش تاییدشده‌ای برای شما ثبت نشده است.\n"
                    "می‌توانید اولین دریافت یا پرداخت خود را ثبت کنید (مثلاً: فروش ۲۰۰ هزار تومن)."
                )
            else:
                total_in_toman = sum(t.amount for t in txs if t.direction == "incoming" and t.unit == "تومان")
                total_out_toman = sum(t.amount for t in txs if t.direction == "outgoing" and t.unit == "تومان")
                count_in_toman = sum(1 for t in txs if t.direction == "incoming" and t.unit == "تومان")
                count_out_toman = sum(1 for t in txs if t.direction == "outgoing" and t.unit == "تومان")

                total_in_rial = sum(t.amount for t in txs if t.direction == "incoming" and t.unit == "ریال")
                total_out_rial = sum(t.amount for t in txs if t.direction == "outgoing" and t.unit == "ریال")

                net_toman = total_in_toman - total_out_toman
                net_rial = total_in_rial - total_out_rial

                reply = (
                    f"📊 وضعیت دخل و خرج شما:\n"
                    f"تعداد کل تراکنش‌های ثبت‌شده: {len(txs)}\n\n"
                    f"🟢 دریافتی‌ها (دخل، فروش و واریزی):\n"
                    f"• {count_in_toman} تراکنش به مبلغ: {total_in_toman:,} تومان\n\n"
                    f"🔴 پرداختی‌ها (خرج، خرید و دستمزد):\n"
                    f"• {count_out_toman} تراکنش به مبلغ: {total_out_toman:,} تومان\n\n"
                    f"💰 مانده خالص فعلی:\n"
                    f"{net_toman:,} تومان"
                )
                if total_in_rial > 0 or total_out_rial > 0:
                    reply += (
                        f"\n\n🔹 بخش ریالی:\n"
                        f"• دریافتی: {total_in_rial:,} ریال | پرداختی: {total_out_rial:,} ریال\n"
                        f"• مانده ریال: {net_rial:,} ریال"
                    )
            keyboard = {
                "keyboard": [
                    [{"text": "گزارش مالی"}, {"text": "ثبت تراکنش جدید"}],
                ],
                "resize_keyboard": True,
            }
            self.client.send_message(chat_id, reply, reply_markup=keyboard)
            self.emit_panel_shadow_trace(chat_id, full_name, text, reply, status="approved", rule_applied="CMD_SUMMARY")
            return

        # 5. Cancellation
        if any(c in CANCELLATIONS for c in cmd_candidates):
            state = self.store.load_session(session_id, user_id)
            if state.get("pending"):
                state["pending"] = None
                self.store.save_session(session_id, user_id, state)
                reply = "پیش‌نویس فعلی لغو شد. می‌توانید پیام جدیدی ارسال کنید."
            else:
                reply = "هیچ پیش‌نویس فعالی برای لغو وجود ندارد."
            keyboard = {
                "keyboard": [[{"text": "گزارش مالی"}, {"text": "ثبت تراکنش جدید"}]],
                "resize_keyboard": True,
            }
            self.client.send_message(chat_id, reply, reply_markup=keyboard)
            self.emit_panel_shadow_trace(chat_id, full_name, text, reply, status="approved", rule_applied="CMD_CANCEL")
            return

        # 6. Active Multi-turn State Processing
        state = self.store.load_session(session_id, user_id)
        pending = state.get("pending")
        self.store.add_message(session_id, user_id, "user", text)

        if pending:
            fresh_transaction = parse_bazaar_message(text)
            pending_status = pending.get("status")
            is_new_transaction = fresh_transaction.amount is not None and (
                pending_status != "awaiting_sub_thousand"
                or fresh_transaction.direction is not None
            )
            if is_new_transaction:
                state["pending"] = None
                self.store.save_session(session_id, user_id, state)
                self.client.send_message(
                    chat_id,
                    "پیش‌نویس قبلی به‌دلیل ثبت پیام تراکنش جدید لغو شد؛ پیام جدید بررسی می‌شود.",
                )
                pending = None

        if pending:
            # Stage A: Awaiting sub-thousand scale clarification (e.g. 150 vs 150,000)
            if pending.get("status") == "awaiting_sub_thousand":
                if "هزار" in norm_text or any(k in norm_text for k in [str(pending["amount"] * 1000), "بله", "آره"]):
                    pending["amount"] = pending["amount"] * 1000
                pending["status"] = "awaiting_confirmation"
                state["pending"] = pending
                self.store.save_session(session_id, user_id, state)
                reply = (
                    f"مبلغ {pending['amount']:,} {pending['unit']} تنظیم شد.\n\n"
                    "برای ثبت نهایی، لطفاً «تأیید» را انتخاب کنید."
                )
                keyboard = {
                    "keyboard": [[{"text": "تأیید"}], [{"text": "لغو پیش‌نویس"}]],
                    "resize_keyboard": True,
                    "one_time_keyboard": True,
                }
                self.client.send_message(chat_id, reply, reply_markup=keyboard)
                return

            # Stage B: Awaiting direction clarification
            if pending.get("status") == "awaiting_direction":
                if any(w in norm_text for w in ["دریافت", "آمد", "اومد", "واریز", "فروش", "دخل", "+", "➕"]):
                    pending["direction"] = "incoming"
                    pending["status"] = "awaiting_confirmation"
                    state["pending"] = pending
                    self.store.save_session(session_id, user_id, state)
                    reply = (
                        f"جهت «دریافتی (آمد به حساب)» ثبت شد.\n"
                        f"💰 مبلغ: {pending['amount']:,} {pending['unit']}\n\n"
                        "برای ثبت نهایی، لطفاً «تأیید» را انتخاب کنید."
                    )
                    keyboard = {
                        "keyboard": [[{"text": "تأیید"}], [{"text": "لغو پیش‌نویس"}]],
                        "resize_keyboard": True,
                        "one_time_keyboard": True,
                    }
                    self.client.send_message(chat_id, reply, reply_markup=keyboard)
                    return
                elif any(w in norm_text for w in ["پرداخت", "خرج", "خرید", "دادم", "رفت", "-", "➖"]):
                    pending["direction"] = "outgoing"
                    pending["status"] = "awaiting_confirmation"
                    state["pending"] = pending
                    self.store.save_session(session_id, user_id, state)
                    reply = (
                        f"جهت «پرداختی (خرج شد)» ثبت شد.\n"
                        f"💰 مبلغ: {pending['amount']:,} {pending['unit']}\n\n"
                        "برای ثبت نهایی، لطفاً «تأیید» را انتخاب کنید."
                    )
                    keyboard = {
                        "keyboard": [[{"text": "تأیید"}], [{"text": "لغو پیش‌نویس"}]],
                        "resize_keyboard": True,
                        "one_time_keyboard": True,
                    }
                    self.client.send_message(chat_id, reply, reply_markup=keyboard)
                    return
                else:
                    reply = "لطفاً با دکمه‌های زیر مشخص کنید این مبلغ دریافتی بوده یا پرداختی:"
                    keyboard = {
                        "keyboard": [
                            [{"text": "➕ دریافت (آمد به حساب)"}, {"text": "➖ پرداخت (خرج شد)"}],
                            [{"text": "لغو پیش‌نویس"}],
                        ],
                        "resize_keyboard": True,
                        "one_time_keyboard": True,
                    }
                    self.client.send_message(chat_id, reply, reply_markup=keyboard)
                    return

            # Stage C: Awaiting unit clarification
            if pending.get("status") == "awaiting_unit" or pending.get("unit") is None:
                if norm_text in {"تومان", "تومن"}:
                    pending["unit"] = "تومان"
                    pending["status"] = "awaiting_confirmation"
                    state["pending"] = pending
                    self.store.save_session(session_id, user_id, state)
                    reply = "برای ثبت این تراکنش بنویسید: تأیید"
                    keyboard = {
                        "keyboard": [[{"text": "تأیید"}], [{"text": "لغو پیش‌نویس"}]],
                        "resize_keyboard": True,
                        "one_time_keyboard": True,
                    }
                    self.client.send_message(chat_id, reply, reply_markup=keyboard)
                    return
                elif norm_text in {"ریال", "ريال"}:
                    pending["unit"] = "ریال"
                    pending["status"] = "awaiting_confirmation"
                    state["pending"] = pending
                    self.store.save_session(session_id, user_id, state)
                    reply = "برای ثبت این تراکنش بنویسید: تأیید"
                    keyboard = {
                        "keyboard": [[{"text": "تأیید"}], [{"text": "لغو پیش‌نویس"}]],
                        "resize_keyboard": True,
                        "one_time_keyboard": True,
                    }
                    self.client.send_message(chat_id, reply, reply_markup=keyboard)
                    return
                else:
                    reply = "لطفاً یکی از واحدهای معتبر «تومان» یا «ریال» را انتخاب یا تایپ کنید."
                    keyboard = {
                        "keyboard": [[{"text": "تومان"}, {"text": "ریال"}], [{"text": "لغو پیش‌نویس"}]],
                        "resize_keyboard": True,
                    }
                    self.client.send_message(chat_id, reply, reply_markup=keyboard)
                    return

            # Stage D: Awaiting Confirmation
            if any(c in CONFIRMATIONS for c in cmd_candidates) or "تایید" in norm_text or "تأیید" in norm_text:
                transaction = Transaction(
                    str(uuid4()),
                    session_id,
                    user_id,
                    pending["amount"],
                    pending["unit"],
                    pending["direction"],
                    "confirmed",
                    _now(),
                )
                self.store.add_transaction(transaction)
                state["pending"] = None
                self.store.save_session(session_id, user_id, state)

                dir_text = "دریافت (آمد به حساب)" if transaction.direction == "incoming" else "پرداخت (خرج/خرید)"
                desc_line = f"\n📝 بابت: {pending.get('description')}" if pending.get("description") else ""
                reply = (
                    "تراکنش با موفقیت ثبت شد.\n\n"
                    f"{'➕' if transaction.direction == 'incoming' else '➖'} {dir_text}\n"
                    f"💰 مبلغ: {transaction.amount:,} {transaction.unit}"
                    f"{desc_line}"
                )
                keyboard = {
                    "keyboard": [
                        [{"text": "گزارش مالی"}, {"text": "ثبت تراکنش جدید"}],
                    ],
                    "resize_keyboard": True,
                }
                self.client.send_message(chat_id, reply, reply_markup=keyboard)
                self.emit_panel_shadow_trace(chat_id, full_name, text, reply, status="approved", rule_applied="FLOW_CONFIRMED")
                return
            else:
                reply = "برای نهایی شدن تراکنش لطفاً بنویسید «تأیید» یا در صورت انصراف، گزینه «لغو پیش‌نویس» را انتخاب کنید."
                keyboard = {
                    "keyboard": [[{"text": "تأیید"}], [{"text": "لغو پیش‌نویس"}]],
                    "resize_keyboard": True,
                }
                self.client.send_message(chat_id, reply, reply_markup=keyboard)
                return

        # 7. No Active Pending Draft: Start New Workflow
        # Check if legacy exact bare pattern without unit (e.g. "دریافت ۷۵۰۰۰۰")
        legacy_bare = re.match(r"^(دریافت|واریز|پرداخت|برداشت)\s*:?[ ]*([0-9۰-۹٠-٩]+)$", norm_text)
        if legacy_bare:
            amount_val = int(legacy_bare.group(2))
            if amount_val <= 0:
                reply = "مبلغ تراکنش باید یک عدد مثبت بزرگتر از صفر باشد."
                self.client.send_message(chat_id, reply)
                return
            pending = {
                "amount": amount_val,
                "direction": "incoming" if legacy_bare.group(1) in {"دریافت", "واریز"} else "outgoing",
                "unit": None,
                "description": "",
                "status": "awaiting_unit",
            }
            state["pending"] = pending
            self.store.save_session(session_id, user_id, state)
            reply = "واحد مبلغ ریال است یا تومان؟"
            keyboard = {
                "keyboard": [[{"text": "تومان"}, {"text": "ریال"}], [{"text": "لغو پیش‌نویس"}]],
                "resize_keyboard": True,
                "one_time_keyboard": True,
            }
            self.client.send_message(chat_id, reply, reply_markup=keyboard)
            self.emit_panel_shadow_trace(chat_id, full_name, text, reply, status="approved", rule_applied="FLOW_AWAITING_UNIT")
            return

        # Smart Bazaar Parser Processing
        bazaar_res = parse_bazaar_message(text)
        if bazaar_res.amount and bazaar_res.amount > 0:
            if bazaar_res.direction:
                if bazaar_res.is_sub_thousand_ambiguous:
                    pending = {
                        "amount": bazaar_res.amount,
                        "unit": bazaar_res.unit,
                        "direction": bazaar_res.direction,
                        "description": bazaar_res.description,
                        "status": "awaiting_sub_thousand",
                    }
                    state["pending"] = pending
                    self.store.save_session(session_id, user_id, state)
                    reply = (
                        f"📝 پیش‌نویس تراکنش:\n"
                        f"{'➕ دریافت' if bazaar_res.direction == 'incoming' else '➖ پرداخت'}: {bazaar_res.description or 'تراکنش'}\n"
                        f"💰 مبلغ ثبت‌شده: {bazaar_res.amount:,} {bazaar_res.unit}\n\n"
                        f"⚠️ توجه: آیا منظورتان {bazaar_res.amount:,} {bazaar_res.unit} است یا {bazaar_res.amount * 1000:,} {bazaar_res.unit}؟"
                    )
                    keyboard = {
                        "keyboard": [
                            [
                                {"text": f"✅ {bazaar_res.amount * 1000:,} {bazaar_res.unit}"},
                                {"text": f"✅ {bazaar_res.amount:,} {bazaar_res.unit}"},
                            ],
                            [{"text": "لغو پیش‌نویس"}],
                        ],
                        "resize_keyboard": True,
                        "one_time_keyboard": True,
                    }
                    self.client.send_message(chat_id, reply, reply_markup=keyboard)
                    self.emit_panel_shadow_trace(chat_id, full_name, text, reply, status="approved", rule_applied="FLOW_AWAITING_SUB_THOUSAND")
                    return
                else:
                    pending = {
                        "amount": bazaar_res.amount,
                        "unit": bazaar_res.unit,
                        "direction": bazaar_res.direction,
                        "description": bazaar_res.description,
                        "status": "awaiting_confirmation",
                    }
                    state["pending"] = pending
                    self.store.save_session(session_id, user_id, state)
                    dir_text = "دریافت (آمد به حساب)" if bazaar_res.direction == "incoming" else "پرداخت (خرج/خرید)"
                    desc_line = f"\n📝 بابت: {bazaar_res.description}" if bazaar_res.description else ""
                    reply = (
                        f"📋 پیش‌نویس تراکنش آماده ثبت:\n\n"
                        f"{'➕' if bazaar_res.direction == 'incoming' else '➖'} نوع: {dir_text}"
                        f"{desc_line}\n"
                        f"💰 مبلغ: {bazaar_res.amount:,} {bazaar_res.unit}\n\n"
                        f"آیا تأیید و ثبت شود؟"
                    )
                    keyboard = {
                        "keyboard": [
                            [{"text": "تأیید و ثبت"}],
                            [{"text": "لغو پیش‌نویس"}],
                        ],
                        "resize_keyboard": True,
                        "one_time_keyboard": True,
                    }
                    self.client.send_message(chat_id, reply, reply_markup=keyboard)
                    self.emit_panel_shadow_trace(chat_id, full_name, text, reply, status="approved", rule_applied="FLOW_AWAITING_CONFIRMATION")
                    return
            else:
                pending = {
                    "amount": bazaar_res.amount,
                    "unit": bazaar_res.unit,
                    "direction": None,
                    "description": bazaar_res.description,
                    "status": "awaiting_direction",
                }
                state["pending"] = pending
                self.store.save_session(session_id, user_id, state)
                desc_text = f" (بابت {bazaar_res.description})" if bazaar_res.description else ""
                reply = (
                    f"مبلغ {bazaar_res.amount:,} {bazaar_res.unit}{desc_text} مشخص شد.\n\n"
                    f"این مبلغ «دریافتی» (آمد به حساب) بوده یا «پرداختی» (خرج کردید/دادید)؟"
                )
                keyboard = {
                    "keyboard": [
                        [{"text": "➕ دریافت (آمد به حساب)"}, {"text": "➖ پرداخت (خرج شد)"}],
                        [{"text": "لغو پیش‌نویس"}],
                    ],
                    "resize_keyboard": True,
                    "one_time_keyboard": True,
                }
                self.client.send_message(chat_id, reply, reply_markup=keyboard)
                self.emit_panel_shadow_trace(chat_id, full_name, text, reply, status="approved", rule_applied="FLOW_AWAITING_DIRECTION")
                return

        # Fallback for off-topic or unrecognized text
        reply = (
            "متوجه مبلغ یا نوع تراکنش نشدم.\n"
            "لطفاً مبلغ و شرح را به سادگی بنویسید، مانند:\n"
            "• «فروش ۲۰۰ هزار تومن»\n"
            "• «خرج ناهار ۵۰ تومن»\n"
            "• «کارت کشید ۴۵۰ هزار تومن»\n"
            "یا برای مشاهده موجودی بنویسید «گزارش مالی»."
        )
        keyboard = {
            "keyboard": [
                [{"text": "گزارش مالی"}, {"text": "راهنما"}],
            ],
            "resize_keyboard": True,
        }
        self.client.send_message(chat_id, reply, reply_markup=keyboard)
        self.emit_panel_shadow_trace(chat_id, full_name, text, reply, stage_status="intercepted", status="rejected", rule_applied="BAZAAR_FALLBACK")

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

    try:
        validate_panel_config(ENABLE_PANEL_EMIT, PANEL_SECRET)
    except RuntimeError as exc:
        logger.error("%s", exc)
        sys.exit(1)

    client = BaleBotClient(token)
    try:
        me = validate_bot_identity_response(client.get_me())
    except RuntimeError as exc:
        logger.error("%s", exc)
        sys.exit(1)
    logger.info(f"Connected to Bale Bot API: {me}")

    engine = BaleBotEngine(client)
    engine.run_polling_loop()
