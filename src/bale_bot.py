"""Bale Messenger Bot Integration for Conversational Work Ledger (bale-auto).

Connects to the official Bale Bot API (https://tapi.bale.ai), handles live polling,
parses user messages with BazaarParser, P0Ledger, and ConversationService,
manages multi-turn sessions, dispatches responses with keyboard markup,
and emits live shadow traces to the Bale-Panel.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import base64
import csv
import io
import json
import logging
import os
import re
import sqlite3
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
    extract_amount_and_unit,
    has_transaction_negation,
    normalize_text,
    parse_bazaar_message,
)
from src.conversation import (
    ConversationService,
    ConversationStore,
    Settlement,
    Transaction,
    _now,
)
from src.p0_core import P0Ledger, Scope, normalize
from src.accounts import Accounts
from src.agent_layer import (
    GUIDE_LATER_ENTRY,
    GUIDE_SKIP_ALL,
    GUIDE_SKIP_STEP,
    GUIDE_STEP_FIRST_ENTRY,
    GUIDE_STEP_GOODS,
    GUIDE_STEP_SHOP_TYPE,
    OFF_SCOPE_REPLY,
    REFUSAL_REPLY,
    SHOP_TYPES,
    SoftLayer,
    UNKNOWN_REPLY,
    extraction_kind,
    guide_done_text,
    guide_first_entry_prompt,
    guide_goods_prompt,
    guide_greeting,
    guide_skipped_text,
    is_scoped_question,
    match_product_fact,
    new_guide_state,
)

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


def panel_emission_enabled(value: str | None = None) -> bool:
    return (os.environ.get("ENABLE_PANEL_EMIT", "0") if value is None else value) == "1"


ENABLE_PANEL_EMIT = panel_emission_enabled()
LEDGER_DB_PATH = os.environ.get("LEDGER_DB_PATH", "/home/admin/bale-auto/data/ledger.db")


def validate_panel_config(enabled: bool, secret: str) -> None:
    if enabled and not secret.strip():
        raise RuntimeError("PANEL_API_SECRET is required when ENABLE_PANEL_EMIT=1")


def validate_bot_identity_response(response: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(response, dict) or response.get("ok") is not True:
        raise RuntimeError("Bale getMe authentication failed; check BALE_BOT_TOKEN")
    return response


def _multipart_body(
    fields: dict[str, str],
    files: dict[str, tuple[str, bytes, str]],
    boundary: str,
) -> bytes:
    """Build a multipart/form-data body with the standard library only."""
    out = io.BytesIO()
    for name, value in fields.items():
        out.write(f"--{boundary}\r\n".encode())
        out.write(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        out.write(str(value).encode("utf-8"))
        out.write(b"\r\n")
    for name, (filename, content, content_type) in files.items():
        out.write(f"--{boundary}\r\n".encode())
        out.write(
            f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'.encode()
        )
        out.write(f"Content-Type: {content_type}\r\n\r\n".encode())
        out.write(content)
        out.write(b"\r\n")
    out.write(f"--{boundary}--\r\n".encode())
    return out.getvalue()


def _post_multipart(
    url: str,
    fields: dict[str, str],
    files: dict[str, tuple[str, bytes, str]],
    headers: dict[str, str] | None = None,
    timeout: int = 30,
) -> dict[str, Any]:
    boundary = f"----baleauto{uuid4().hex}"
    body = _multipart_body(fields, files, boundary)
    req_headers = {"Content-Type": f"multipart/form-data; boundary={boundary}"}
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(url, data=body, headers=req_headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


class BaleBotClient:
    """Client for calling Bale Bot API methods with retry logic and error resilience."""

    def __init__(self, token: str, api_base: str = BALE_API_BASE) -> None:
        if not token:
            raise ValueError("BALE_BOT_TOKEN is required")
        self.token = token
        self.api_base = f"{api_base}/bot{token}"
        self.file_base = f"{api_base}/file/bot{token}"

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

    def get_file(self, file_id: str) -> dict[str, Any]:
        return self.call_api("getFile", {"file_id": file_id}, timeout=10)

    def download_file(self, file_path: str) -> bytes:
        url = f"{self.file_base}/{file_path}"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read()

    def send_document(
        self,
        chat_id: int | str,
        filename: str,
        content: bytes,
        caption: str = "",
    ) -> dict[str, Any]:
        fields = {"chat_id": str(chat_id)}
        if caption:
            fields["caption"] = caption
        try:
            return _post_multipart(
                f"{self.api_base}/sendDocument",
                fields,
                {"document": (filename, content, "application/octet-stream")},
                timeout=30,
            )
        except Exception as e:
            logger.error(f"sendDocument failed: {e}")
            return {"ok": False, "description": str(e)}

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

    def answer_callback_query(
        self,
        callback_query_id: str,
        text: Optional[str] = None,
        show_alert: bool = False,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"callback_query_id": callback_query_id}
        if text:
            payload["text"] = text
        if show_alert:
            payload["show_alert"] = True
        return self.call_api("answerCallbackQuery", payload, timeout=10)


# Inline-button callback actions for pending-draft control. Every callback
# carries the draft_id of the pending draft it was rendered for, so a tap on
# a stale message can never commit or cancel a different (newer) draft.
CB_CONFIRM = "cfm"
CB_CANCEL = "cnl"
CB_DIR_INCOMING = "din"
CB_DIR_OUTGOING = "dou"
# Action callbacks (settle / undo) carry a short token bound in the chat's
# session state to their payload, so a stale tap resolves to nothing.
CB_SETTLE_PICK = "stl"
CB_SETTLE_FULL = "sfa"
CB_SETTLE_DISMISS = "scx"
CB_UNDO_PICK = "udp"
CB_UNDO_CONFIRM = "udc"
CB_UNDO_DISMISS = "udx"
_ACTION_CALLBACKS = {
    CB_SETTLE_PICK,
    CB_SETTLE_FULL,
    CB_SETTLE_DISMISS,
    CB_UNDO_PICK,
    CB_UNDO_CONFIRM,
    CB_UNDO_DISMISS,
}


def _new_draft_id() -> str:
    return uuid4().hex[:12]


def draft_confirm_keyboard(draft_id: str) -> dict[str, Any]:
    return {
        "inline_keyboard": [
            [
                {"text": "✅ تأیید", "callback_data": f"{CB_CONFIRM}:{draft_id}"},
                {"text": "❌ لغو", "callback_data": f"{CB_CANCEL}:{draft_id}"},
            ]
        ]
    }


def draft_direction_keyboard(draft_id: str) -> dict[str, Any]:
    return {
        "inline_keyboard": [
            [
                {"text": "➕ دریافت", "callback_data": f"{CB_DIR_INCOMING}:{draft_id}"},
                {"text": "➖ پرداخت", "callback_data": f"{CB_DIR_OUTGOING}:{draft_id}"},
            ],
            [{"text": "❌ لغو", "callback_data": f"{CB_CANCEL}:{draft_id}"}],
        ]
    }


def _agent_cap(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, "") or default)
    except ValueError:
        return default


# Routed-question storage shared with the panels' support store.
# Keep in sync with the open_questions DDL in src/support_store.py.
_OPEN_QUESTIONS_DDL = """
CREATE TABLE IF NOT EXISTS open_questions(
    id INTEGER PRIMARY KEY,
    bale_user_id TEXT NOT NULL,
    name TEXT NOT NULL DEFAULT '',
    question TEXT NOT NULL,
    created_at INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    closed_by INTEGER
);
"""


class BaleBotEngine:
    """Core logic orchestrator for bale-auto bot."""

    def __init__(
        self,
        client: BaleBotClient,
        db_path: str = LEDGER_DB_PATH,
        support_db_path: str | None = None,
    ) -> None:
        self.client = client
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.store = ConversationStore(db_path)
        self.accounts = Accounts(db_path)
        self.service = ConversationService(self.store)
        self.ledger = P0Ledger()
        # Section 11 soft layer: model polish over deterministic texts,
        # template fallback whenever the model is absent or misbehaves.
        # Agent laws: polish is reachable ONLY through _polish_gated
        # (guide turns + scoped answers), under the daily caps below.
        self.agent = SoftLayer.from_env()
        self.agent_user_cap = _agent_cap("AGENT_DAILY_CAP_PER_USER", 30)
        self.agent_global_cap = _agent_cap("AGENT_DAILY_CAP_GLOBAL", 500)
        # Where unanswered scoped questions are routed for the supporter
        # (the panels' support.db). Empty = routing disabled.
        self.support_db_path = (
            support_db_path
            if support_db_path is not None
            else os.environ.get("SUPPORT_DB_PATH", "")
        )
        self.running = False
        self._last_offset = self.store.get_poll_offset()

    # ----- agent laws: gated polish, scoped answers, routing -----------

    def _polish_gated(self, user_id: str, text: str) -> str:
        """The ONLY door to the model (agent laws).

        Reached solely for guide turns and scoped answers. Consumes one
        call against the per-user and global daily caps; beyond a cap —
        or with no model configured — the deterministic text is served
        unchanged and silently.
        """
        if not self.agent.enabled or not text:
            return text
        day = self._local_now().date().isoformat()
        if not self.store.agent_try_consume(
            user_id, day, self.agent_user_cap, self.agent_global_cap
        ):
            return text
        return self.agent.polish(text)

    def _scoped_answer(self, user_id: str, norm_text: str) -> str | None:
        """A deterministic answer for a scoped question, or None.

        Sources, in order: the user's OWN open credit balances, his OWN
        plan/status, his OWN ledger totals — then the product facts
        table. Nothing here touches another user's data, and the model
        never composes any of it (it may only rephrase, upstream).
        """
        t = norm_text
        if any(w in t for w in ("طلب", "بدهی", "بدهکار", "نسیه")):
            balances = self._credit_balances(user_id)
            if not balances:
                return (
                    "الان حساب باز نسیه‌ای نداری؛ نه طلبی از کسی داری، نه بدهی‌ای به کسی.\n"
                    "وقتی فروش نسیه ثبت می‌کنی (مثلاً: «فروش نسیه ۵۰۰ هزار تومان به احمدی») اینجا می‌بینی‌اش."
                )
            lines = ["📒 حساب‌های باز نسیه‌ات:"]
            for b in balances:
                who = b["counterparty"] or "نامشخص"
                label = f"طلب از {who}" if b["side"] == "receivable" else f"بدهی به {who}"
                lines.append(f"• {label}: {b['open']:,} {b['unit']}")
            lines.append("با «طلب‌ها» می‌بینی و تسویه‌اش می‌کنی.")
            return "\n".join(lines)
        if any(w in t for w in ("پلن", "ماه رایگان", "کد معرفی", "روز مانده", "روز مونده")):
            return self.accounts.status_text(user_id)
        if any(w in t for w in ("موجودی", "دخل", "گزارشم", "فروختم", "فروشم", "درآمدم", "درامدم")):
            if "امروز" in t:
                return self.daily_report_text(user_id) or (
                    "امروز هنوز تراکنش تأییدشده‌ای ثبت نکرده‌ای."
                )
            cash = [x for x in self.store.list_transactions(user_id) if x.kind == "cash"]
            if not cash:
                return "هنوز تراکنش تأییدشده‌ای در دفترت نیست؛ اولی را با «فروش ۲۰۰ هزار تومن» ثبت کن."
            return (
                "📊 جمع دفترت تا امروز:\n"
                + self._sum_by_unit(cash)
                + "\nبرای جزئیات بنویس «گزارش مالی»."
            )
        return match_product_fact(t)

    def _route_question_to_support(self, user_id: str, full_name: str, text: str) -> None:
        """Store an unanswered scoped question for the supporter panel.

        Writes the panels' support.db directly (same table the panels
        create — see _OPEN_QUESTIONS_DDL). A failure here never breaks
        the user's answer; the fixed template is sent regardless.
        """
        if not self.support_db_path:
            logger.warning("agent: question not routed (SUPPORT_DB_PATH unset)")
            return
        try:
            conn = sqlite3.connect(self.support_db_path, timeout=5)
            try:
                conn.execute("PRAGMA busy_timeout=5000")
                conn.execute(_OPEN_QUESTIONS_DDL)
                conn.execute(
                    "INSERT INTO open_questions(bale_user_id, name, question, created_at)"
                    " VALUES(?,?,?,?)",
                    (str(user_id), full_name or "", text, int(time.time())),
                )
                conn.commit()
            finally:
                conn.close()
        except Exception as e:
            logger.warning(f"agent: routing question to support failed: {e}")

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

    # ----- production features: reports, export, credits, media -----

    CREDIT_MARKERS = ("نسیه", "طلب", "قرض", "دفتری", "حساب باز")

    def _local_now(self, now_utc: datetime | None = None) -> datetime:
        try:
            offset = int(os.environ.get("REPORT_UTC_OFFSET_MINUTES", "210"))
        except ValueError:
            offset = 210
        base = now_utc or datetime.now(timezone.utc)
        if base.tzinfo is None:
            base = base.replace(tzinfo=timezone.utc)
        return base + timedelta(minutes=offset)

    def _tx_local_date(self, tx: Transaction):
        try:
            created = datetime.fromisoformat(tx.created_at)
        except ValueError:
            return None
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        return self._local_now(created).date()

    def _sum_by_unit(self, txs: list[Transaction]) -> str:
        lines = []
        for unit in ("تومان", "ریال"):
            total_in = sum(x.amount for x in txs if x.direction == "incoming" and x.unit == unit)
            total_out = sum(x.amount for x in txs if x.direction == "outgoing" and x.unit == unit)
            if total_in or total_out:
                lines.append(
                    f"🟢 دریافتی: {total_in:,} {unit} | 🔴 پرداختی: {total_out:,} {unit} | 💰 مانده: {total_in - total_out:,} {unit}"
                )
        return "\n".join(lines)

    def daily_report_text(self, user_id: str, day=None) -> str | None:
        day = day or self._local_now().date()
        txs = [x for x in self.store.list_transactions(user_id) if self._tx_local_date(x) == day]
        if not txs:
            return None
        # Cash truth: unsettled credit never enters the cash sums.
        cash = [x for x in txs if x.kind == "cash"]
        credits = [x for x in txs if x.kind == "credit"]
        lines = [
            f"🌙 گزارش امروز ({day.isoformat()}):",
            f"تعداد تراکنش: {len(txs)}",
        ]
        if cash:
            lines.append(self._sum_by_unit(cash))
        for x in credits:
            who = x.counterparty or "نامشخص"
            label = (
                f"🧾 نسیه — طلب از {who}"
                if x.direction == "incoming"
                else f"🧾 نسیه — بدهی به {who}"
            )
            lines.append(f"{label}: {x.amount:,} {x.unit} (نقدی حساب نشده)")
        balances = self._credit_balances(user_id)
        if balances:
            top = balances[0]
            lines.append(
                f"📒 بزرگ‌ترین حساب باز: {top['counterparty']} — {top['open']:,} {top['unit']} "
                "(با «طلب‌ها» ببین و تسویه کن)"
            )
        if self.accounts.is_activated(user_id):
            lines.append(f"⏳ از ماه رایگانت {self.accounts.free_days_left(user_id)} روز مانده")
        return "\n".join(lines)

    def send_nightly_reports(self, now_utc: datetime | None = None) -> int:
        """Send each active user their daily report once, after the set local time."""
        if os.environ.get("NIGHTLY_REPORT_ENABLED", "1") != "1":
            return 0
        local = self._local_now(now_utc)
        raw_time = os.environ.get("NIGHTLY_REPORT_TIME", "21:00")
        try:
            hh, mm = (int(part) for part in raw_time.split(":", 1))
        except ValueError:
            hh, mm = 21, 0
        if (local.hour, local.minute) < (hh, mm):
            return 0
        sent = 0
        for session in self.store.list_sessions():
            user_id = session["user_id"]
            key = f"nightly:{user_id}:{local.date().isoformat()}"
            if self.store.get_kv(key):
                continue
            text = self.daily_report_text(user_id, local.date())
            if not text:
                continue
            self.client.send_message(user_id, text)
            self.store.set_kv(key, "sent")
            sent += 1
        return sent

    def build_month_csv(self, user_id: str, year: int, month: int) -> str:
        rows = [
            x
            for x in self.store.list_transactions(user_id)
            if (d := self._tx_local_date(x)) is not None and (d.year, d.month) == (year, month)
        ]
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["date", "direction", "amount", "unit", "description", "status"])
        for x in rows:
            writer.writerow(
                [self._tx_local_date(x).isoformat(), x.direction, x.amount, x.unit, x.description, x.status]
            )
        return buf.getvalue()

    def send_monthly_export(self, chat_id: str, user_id: str) -> None:
        local = self._local_now()
        csv_text = self.build_month_csv(user_id, local.year, local.month)
        if len(csv_text.strip().splitlines()) <= 1:
            self.client.send_message(chat_id, "برای این ماه هنوز تراکنش تأییدشده‌ای نداری که خروجی بگیرم.")
            return
        filename = f"ledger-{local.year}-{local.month:02d}.csv"
        caption = f"📤 خروجی تراکنش‌های {local.year}-{local.month:02d}"
        sender = getattr(self.client, "send_document", None)
        if callable(sender):
            resp = sender(chat_id, filename, ("\ufeff" + csv_text).encode("utf-8"), caption)
            if isinstance(resp, dict) and resp.get("ok"):
                return
        # Fallback: deliver the CSV as text chunks.
        self.client.send_message(chat_id, caption + " (ارسال فایل نشد؛ متن CSV):")
        for i in range(0, len(csv_text), 3000):
            self.client.send_message(chat_id, csv_text[i : i + 3000])

    # ----- credit (نسیه): balances, settlement, undo -----

    def list_credit_items(self, user_id: str) -> list[Transaction]:
        """Live credit entries (kind='credit', not voided)."""
        return [x for x in self.store.list_transactions(user_id) if x.kind == "credit"]

    def _credit_balances(self, user_id: str) -> list[dict[str, Any]]:
        """Open credit per person/unit/side: credit entries minus settlements."""
        bal: dict[tuple[str, str, str], int] = {}
        for x in self.list_credit_items(user_id):
            side = "receivable" if x.direction == "incoming" else "payable"
            key = (x.counterparty or "نامشخص", x.unit, side)
            bal[key] = bal.get(key, 0) + x.amount
        for s in self.store.list_settlements(user_id):
            key = (s.counterparty, s.unit, s.side)
            if key in bal:
                bal[key] -= s.amount
        out = [
            {"counterparty": cp, "unit": unit, "side": side, "open": amount}
            for (cp, unit, side), amount in bal.items()
            if amount > 0
        ]
        out.sort(key=lambda b: (-b["open"], b["counterparty"]))
        return out

    def _open_balance(self, user_id: str, counterparty: str, unit: str, side: str) -> int:
        for b in self._credit_balances(user_id):
            if (b["counterparty"], b["unit"], b["side"]) == (counterparty, unit, side):
                return b["open"]
        return 0

    @staticmethod
    def _bind(state: dict[str, Any], payload: dict[str, Any]) -> str:
        token = uuid4().hex[:8]
        bindings = state.setdefault("cb_bindings", {})
        bindings[token] = payload
        while len(bindings) > 24:
            bindings.pop(next(iter(bindings)))
        return token

    @staticmethod
    def _binding(state: dict[str, Any], token: str) -> dict[str, Any] | None:
        return (state.get("cb_bindings") or {}).get(token)

    def credit_report_text(self, user_id: str) -> str:
        text, _ = self.credit_report(user_id, None)
        return text

    def credit_report(
        self, user_id: str, state: dict[str, Any] | None
    ) -> tuple[str, dict[str, Any] | None]:
        balances = self._credit_balances(user_id)
        if not balances:
            has_history = bool(self.list_credit_items(user_id)) or bool(
                self.store.list_settlements(user_id)
            )
            if has_history:
                return ("🧾 حساب باز نسیه‌ای نداری؛ همه تسویه شده‌اند. 🎉", None)
            return (
                "🧾 مورد نسیه/طلب ثبت‌شده‌ای نداری.\n"
                "وقتی فروش نسیه ثبت می‌کنی (مثلاً: «فروش نسیه ۵۰۰ هزار تومان به احمدی») اینجا می‌بینی‌اش.",
                None,
            )
        recv = [b for b in balances if b["side"] == "receivable"]
        pay = [b for b in balances if b["side"] == "payable"]
        lines = ["🧾 حساب‌های باز نسیه:"]
        if recv:
            lines.append("\n💰 طلب تو از دیگران:")
            for b in recv:
                lines.append(f"• {b['counterparty']}: {b['open']:,} {b['unit']}")
        if pay:
            lines.append("\n📌 بدهی تو به دیگران:")
            for b in pay:
                lines.append(f"• {b['counterparty']}: {b['open']:,} {b['unit']}")
        # One ready reminder per receivable person, on their latest entry.
        items = self.list_credit_items(user_id)
        for b in recv:
            latest = None
            for x in items:
                if (
                    x.direction == "incoming"
                    and (x.counterparty or "نامشخص") == b["counterparty"]
                    and x.unit == b["unit"]
                ):
                    latest = x
            desc = (latest.description if latest else "") or f"طلب از {b['counterparty']}"
            lines.append(
                f"✉️ پیام آماده برای {b['counterparty']}: «سلام، وقت بخیر. بابت {desc} "
                f"مبلغ {b['open']:,} {b['unit']} هنوز تسویه نشده است؛ "
                "ممنون می‌شم در اولین فرصت پرداخت کنید. 🙏»"
            )
        lines.append("\nبرای تسویه، دکمه‌ی طرف حساب را بزن یا بنویس: «تسویه احمدی ۲۰۰ هزار»")
        keyboard = None
        if state is not None:
            rows = []
            for b in balances[:8]:
                token = self._bind(
                    state,
                    {
                        "act": CB_SETTLE_PICK,
                        "cp": b["counterparty"],
                        "unit": b["unit"],
                        "side": b["side"],
                    },
                )
                label = (
                    f"تسویه طلب {b['counterparty']}"
                    if b["side"] == "receivable"
                    else f"تسویه بدهی {b['counterparty']}"
                )
                rows.append([{"text": label, "callback_data": f"{CB_SETTLE_PICK}:{token}"}])
            if rows:
                keyboard = {"inline_keyboard": rows}
        return "\n".join(lines), keyboard

    def _execute_settlement(
        self, user_id: str, session_id: str, balance: dict[str, Any], amount: int
    ) -> str:
        """Record a settlement event + its real cash movement. Never edits history."""
        cp, unit, side = balance["counterparty"], balance["unit"], balance["side"]
        amount = min(amount, balance["open"])
        settlement_id = str(uuid4())
        self.store.add_settlement(
            Settlement(settlement_id, user_id, cp, unit, side, amount, _now())
        )
        direction = "incoming" if side == "receivable" else "outgoing"
        label = "تسویه طلب" if side == "receivable" else "تسویه بدهی"
        self.store.add_transaction(
            Transaction(
                str(uuid4()),
                session_id,
                user_id,
                amount,
                unit,
                direction,
                "confirmed",
                _now(),
                f"{label} {cp}",
                kind="cash",
                settlement_id=settlement_id,
            )
        )
        remaining = balance["open"] - amount
        reply = f"✅ تسویه ثبت شد: {cp} — {amount:,} {unit}"
        if remaining > 0:
            reply += f"\nمانده‌ی باز {cp}: {remaining:,} {unit}"
        else:
            reply += f"\nحساب {cp} کامل بسته شد. 🎉"
        return reply

    def _settle_command(self, user_id: str, session_id: str, rest: str) -> str:
        balances = self._credit_balances(user_id)
        if not balances:
            return "حساب باز نسیه‌ای نداری که تسویه‌اش کنی."
        amount, unit, amt_str, _ = extract_amount_and_unit(rest)
        name = rest
        if amt_str:
            name = name.replace(amt_str, " ")
        for noise in ("تومان", "تومن", "ریال", "به", "از", "را", "رو"):
            name = re.sub(rf"(?<!\w){noise}(?!\w)", " ", name)
        name = " ".join(name.split()).strip()
        matches = [
            b for b in balances if normalize_text(b["counterparty"]) == normalize_text(name)
        ]
        if not matches:
            names = "، ".join(sorted({b["counterparty"] for b in balances}))
            return f"حساب بازی به اسم «{name}» پیدا نکردم.\nحساب‌های باز: {names}"
        if amount:
            targets = [b for b in matches if b["unit"] == unit] or matches[:1]
            return self._execute_settlement(user_id, session_id, targets[0], amount)
        return "\n".join(
            self._execute_settlement(user_id, session_id, b, b["open"]) for b in matches
        )

    def _undo_prompt(
        self, user_id: str, session_id: str, pick: Transaction | None
    ) -> tuple[str, dict[str, Any] | None]:
        """Ask before voiding: one candidate (the latest, or a picked row)."""
        state = self.store.load_session(session_id, user_id)
        candidate = pick or next(iter(self.store.last_transactions(user_id, 1)), None)
        if candidate is None:
            return ("تراکنش تأییدشده‌ای برای حذف نیست.", None)
        confirm = self._bind(state, {"act": CB_UNDO_CONFIRM, "tx": candidate.transaction_id})
        dismiss = self._bind(state, {"act": CB_UNDO_DISMISS})
        self.store.save_session(session_id, user_id, state)
        reply = (
            "این تراکنش حذف شود؟ (از همه‌ی جمع‌ها کنار می‌رود؛ سابقه‌اش برای حسابرسی می‌ماند)\n"
            f"{self._tx_brief(candidate)}"
        )
        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "🗑 بله، حذف شود", "callback_data": f"{CB_UNDO_CONFIRM}:{confirm}"},
                    {"text": "نگه دار", "callback_data": f"{CB_UNDO_DISMISS}:{dismiss}"},
                ]
            ]
        }
        return reply, keyboard

    def _undo_list(
        self, user_id: str, session_id: str
    ) -> tuple[str, dict[str, Any] | None]:
        """Pick-from-recent delete menu («حذف تراکنش»)."""
        recent = self.store.last_transactions(user_id, 5)
        if not recent:
            return ("تراکنش تأییدشده‌ای برای حذف نیست.", None)
        state = self.store.load_session(session_id, user_id)
        rows = []
        for x in recent:
            token = self._bind(state, {"act": CB_UNDO_PICK, "tx": x.transaction_id})
            rows.append([{"text": self._tx_brief(x), "callback_data": f"{CB_UNDO_PICK}:{token}"}])
        self.store.save_session(session_id, user_id, state)
        return ("کدام تراکنش حذف شود؟", {"inline_keyboard": rows})

    @staticmethod
    def _tx_brief(x: Transaction) -> str:
        arrow = "➕" if x.direction == "incoming" else "➖"
        desc = x.description or "تراکنش"
        credit = ""
        if x.kind == "credit":
            who = x.counterparty or "نامشخص"
            credit = f" (نسیه — {'طلب از' if x.direction == 'incoming' else 'بدهی به'} {who})"
        return f"{arrow} {desc}: {x.amount:,} {x.unit}{credit}"

    # ----- media input (voice / photo), provider-configured, off by default -----

    def _download_bale_file(self, file_id: str) -> bytes | None:
        try:
            resp = self.client.get_file(file_id)
            file_path = (resp.get("result") or {}).get("file_path")
            if not file_path:
                return None
            return self.client.download_file(file_path)
        except Exception as e:
            logger.error(f"media download failed: {e}")
            return None

    def _transcribe_with_model(
        self, url: str, content: bytes, model: str, headers: dict
    ) -> str | None:
        try:
            resp = _post_multipart(
                url,
                {"model": model},
                {"file": ("voice.ogg", content, "audio/ogg")},
                headers=headers,
                timeout=60,
            )
            text = str(resp.get("text", "")).strip()
            return text or None
        except Exception as e:
            logger.error(f"voice transcription failed (model={model}): {e}")
            return None

    def _transcribe_audio(self, content: bytes) -> str | None:
        url = os.environ.get("VOICE_STT_URL", "").strip()
        if not url:
            return None
        headers = {}
        api_key = os.environ.get("VOICE_STT_API_KEY", "").strip()
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        model = os.environ.get("VOICE_STT_MODEL", "whisper-1")
        text = self._transcribe_with_model(url, content, model, headers)
        if text:
            return text
        # Fallback: retry once with the fallback model when one is configured
        # (e.g. primary small model down/empty -> larger model, same server).
        fallback = os.environ.get("VOICE_STT_FALLBACK_MODEL", "").strip()
        if fallback and fallback != model:
            logger.warning(
                f"voice transcription empty/failed with {model}; "
                f"retrying with fallback model {fallback}"
            )
            return self._transcribe_with_model(url, content, fallback, headers)
        return None

    def _extract_photo_text(self, content: bytes) -> str | None:
        url = os.environ.get("PHOTO_OCR_URL", "").strip()
        if not url:
            return None
        headers = {"Content-Type": "application/json"}
        api_key = os.environ.get("PHOTO_OCR_API_KEY", "").strip()
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        model = os.environ.get("PHOTO_OCR_MODEL", "gpt-4o-mini")
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "این عکس یک رسید یا فاکتور است. فقط یک جمله فارسی برگردان که شامل مبلغ، واحد (تومان یا ریال)، جهت (فروش/دریافت یا خرید/پرداخت) و بابت باشد. هیچ توضیح اضافه‌ای نده.",
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": "data:image/jpeg;base64,"
                                + base64.b64encode(content).decode("ascii")
                            },
                        },
                    ],
                }
            ],
        }
        try:
            req = urllib.request.Request(
                url, data=json.dumps(payload).encode("utf-8"), headers=headers
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            text = str(data["choices"][0]["message"]["content"]).strip()
            return text or None
        except Exception as e:
            logger.error(f"photo extraction failed: {e}")
            return None

    def _handle_media_message(
        self, message: dict[str, Any], chat_id: str
    ) -> str | None:
        """Return extracted text, "" when a reply was already sent, or None if not media."""
        voice = message.get("voice") or message.get("audio")
        photo = message.get("photo")
        if not voice and not photo:
            return None
        if voice:
            if not os.environ.get("VOICE_STT_URL", "").strip():
                self.client.send_message(
                    chat_id,
                    "🎙 ویست رسید، ولی تبدیل صدا به متن روی این بات هنوز فعال نشده است. فعلاً مبلغ را تایپ کن (مثلاً: فروش ۲۰۰ هزار تومن).",
                )
                return ""
            content = self._download_bale_file(str(voice.get("file_id", "")))
            text = self._transcribe_audio(content) if content else None
            if not text:
                self.client.send_message(
                    chat_id, "🎙 ویست رسید ولی نتوانستم متنش را بخوانم؛ لطفاً تایپش کن."
                )
                return ""
            return text
        # photo: Bale sends several sizes; take the largest (last).
        sizes = photo if isinstance(photo, list) else [photo]
        file_id = str(sizes[-1].get("file_id", ""))
        if not os.environ.get("PHOTO_OCR_URL", "").strip():
            self.client.send_message(
                chat_id,
                "📷 عکس رسید، ولی خواندن خودکار عکس روی این بات هنوز فعال نشده است. مبلغ و بابت را تایپ کن تا ثبت کنم.",
            )
            return ""
        content = self._download_bale_file(file_id)
        text = self._extract_photo_text(content) if content else None
        if not text:
            self.client.send_message(
                chat_id, "📷 عکس رسید ولی نتوانستم مبلغش را بخوانم؛ لطفاً تایپش کن."
            )
            return ""
        return text

    # ----- section 13: the onboarding guide -----

    def _guide_for(self, state: dict[str, Any], user_id: str) -> dict[str, Any]:
        """Guide state for this chat; users with history are already done."""
        g = state.get("guide")
        if g is None:
            if self.store.list_transactions(user_id, include_voided=True):
                g = {"step": None, "done": True, "skipped": False, "shop_type": "", "goods": ""}
            else:
                g = new_guide_state()
            state["guide"] = g
        return g

    def _send_guide_step(
        self,
        chat_id: str,
        state: dict[str, Any],
        first_name: str,
        account: dict[str, Any],
        extra: str = "",
    ) -> None:
        """Render the guide's current step: one short ask, buttons for choices."""
        step = (state.get("guide") or {}).get("step")
        if step == GUIDE_STEP_GOODS:
            text = guide_goods_prompt()
            keyboard = {
                "keyboard": [[{"text": "رد کردن این قدم"}]],
                "resize_keyboard": True,
            }
        elif step == GUIDE_STEP_FIRST_ENTRY:
            text = guide_first_entry_prompt()
            keyboard = {
                "keyboard": [[{"text": "بعداً ثبت می‌کنم"}]],
                "resize_keyboard": True,
            }
        else:  # shop_type (also the greeting step)
            text = guide_greeting(first_name, account["referral_code"])
            if extra:
                text += extra
            keyboard = {
                "keyboard": [
                    [{"text": SHOP_TYPES[0]}, {"text": SHOP_TYPES[1]}],
                    [{"text": SHOP_TYPES[2]}, {"text": SHOP_TYPES[3]}],
                    [{"text": "گزارش مالی"}, {"text": "رد کردن راهنما"}],
                ],
                "resize_keyboard": True,
            }
        self.client.send_message(chat_id, self._polish_gated(str(chat_id), text), reply_markup=keyboard)

    def _finish_guide(
        self, chat_id: str, state: dict[str, Any], session_id: str, user_id: str, skipped: bool
    ) -> None:
        g = state.get("guide") or {}
        g["done"] = True
        g["step"] = None
        g["skipped"] = skipped
        state["guide"] = g
        self.store.save_session(session_id, user_id, state)
        text = guide_skipped_text() if skipped else guide_done_text()
        keyboard = {
            "keyboard": [
                [{"text": "گزارش مالی"}, {"text": "ثبت تراکنش جدید"}],
                [{"text": "لغو پیش‌نویس"}],
            ],
            "resize_keyboard": True,
        }
        self.client.send_message(chat_id, self._polish_gated(user_id, text), reply_markup=keyboard)

    def _settle_ctx_message(
        self,
        chat_id: str,
        state: dict[str, Any],
        session_id: str,
        user_id: str,
        text: str,
        norm_text: str,
    ) -> bool:
        """Consume a message while a button-first settlement awaits an amount.

        Returns True when the message was the settlement answer. Anything
        else abandons the context and lets the message flow on untouched.
        """
        ctx = state.get("settle_ctx") or {}
        balance = {
            "counterparty": ctx.get("cp", ""),
            "unit": ctx.get("unit", ""),
            "side": ctx.get("side", "receivable"),
            "open": self._open_balance(
                user_id, ctx.get("cp", ""), ctx.get("unit", ""), ctx.get("side", "receivable")
            ),
        }

        def _clear() -> None:
            state["settle_ctx"] = None
            self.store.save_session(session_id, user_id, state)

        if balance["open"] <= 0:
            _clear()
            self.client.send_message(chat_id, "این حساب دیگر مانده‌ی بازی ندارد.")
            return True
        if norm_text in {"همه‌اش", "همه اش", "همه", "کامل"}:
            reply = self._execute_settlement(user_id, session_id, balance, balance["open"])
            _clear()
            self.client.send_message(chat_id, reply)
            return True
        parsed = parse_bazaar_message(text)
        if parsed.amount and parsed.direction:
            # A full transaction phrasing is a new entry, not a bare amount.
            _clear()
            return False
        amount, _unit, _amt_str, _amb = extract_amount_and_unit(norm_text)
        if amount:
            reply = self._execute_settlement(user_id, session_id, balance, amount)
            _clear()
            self.client.send_message(chat_id, reply)
            return True
        if any(c in CANCELLATIONS for c in {text, norm_text}):
            _clear()
            self.client.send_message(chat_id, "تسویه لغو شد.")
            return True
        _clear()
        return False

    def _guide_message(
        self,
        chat_id: str,
        state: dict[str, Any],
        session_id: str,
        user_id: str,
        text: str,
        norm_text: str,
        first_name: str,
        account: dict[str, Any],
    ) -> bool:
        """Consume a message as a guide answer, when it is one.

        The spine is scripted: it only ever consumes its own expected
        answers. Anything else returns False and flows on untouched.
        """
        g = state.get("guide") or {}
        step = g.get("step")
        if norm_text in GUIDE_SKIP_ALL:
            self._finish_guide(chat_id, state, session_id, user_id, skipped=True)
            return True
        if step == GUIDE_STEP_SHOP_TYPE:
            for shop_type in SHOP_TYPES:
                if norm_text == normalize_text(shop_type):
                    g["shop_type"] = shop_type
                    g["step"] = GUIDE_STEP_GOODS
                    state["guide"] = g
                    self.store.save_session(session_id, user_id, state)
                    self._send_guide_step(chat_id, state, first_name, account)
                    return True
            return False
        if step == GUIDE_STEP_GOODS:
            if norm_text in GUIDE_SKIP_STEP:
                g["goods"] = ""
                g["step"] = GUIDE_STEP_FIRST_ENTRY
                state["guide"] = g
                self.store.save_session(session_id, user_id, state)
                self._send_guide_step(chat_id, state, first_name, account)
                return True
            if parse_bazaar_message(text).amount:
                # They jumped straight to a real entry — that IS step three.
                g["step"] = GUIDE_STEP_FIRST_ENTRY
                state["guide"] = g
                self.store.save_session(session_id, user_id, state)
                return False
            g["goods"] = text.strip()[:60]
            g["step"] = GUIDE_STEP_FIRST_ENTRY
            state["guide"] = g
            self.store.save_session(session_id, user_id, state)
            self._send_guide_step(chat_id, state, first_name, account)
            return True
        if step == GUIDE_STEP_FIRST_ENTRY and norm_text in GUIDE_LATER_ENTRY:
            self._finish_guide(chat_id, state, session_id, user_id, skipped=True)
            return True
        return False

    def handle_message(self, message: dict[str, Any]) -> None:
        chat = message.get("chat", {})
        chat_id = str(chat.get("id", ""))
        sender = message.get("from", {})
        first_name = sender.get("first_name", "")
        last_name = sender.get("last_name", "")
        username = sender.get("username", "")
        full_name = f"{first_name} {last_name}".strip() or username or "کاربر بله"

        # Media first: voice/photo are converted to text when configured.
        if not message.get("_from_media"):
            media_text = self._handle_media_message(message, chat_id)
            if media_text is not None:
                if media_text == "":
                    return  # a specific reply was already sent
                forwarded = dict(message)
                forwarded["text"] = media_text
                forwarded["_from_media"] = True
                self.handle_message(forwarded)
                return

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

        # Distribution mechanics (plan section 14): the account is born at
        # first contact; a referral code may arrive bare, after the words
        # for "referral code", or as a /start parameter.
        account = self.accounts.get_or_create(user_id)
        ref_match = re.search(r"\bB[0-9A-Fa-f]{4,}\b", text)
        ref_note = ""
        if ref_match and not any(c in {"وضعیت من", "وضعیت", "/status", "پلن من"} for c in cmd_candidates):
            code = ref_match.group(0).upper()
            if code != account["referral_code"]:
                ref = self.accounts.record_referral(code, user_id)
                if ref is not None:
                    ref_note = "\n🎁 کد معرفی ثبت شد؛ معرف تو مشخص شد."
                elif text.strip().upper() == code:
                    self.client.send_message(chat_id, "این کد معرفی ثبت نشد: یا ناشناخته است، یا قبلاً معرف داری، یا کد خودت است.")
                    return
        # fallthrough note is consumed by the /start branch below

        # Agent laws: an extraction attempt (database, other people's
        # data, secrets, the prompt) is refused by ONE fixed template,
        # is logged for the owner panel, and never reaches the model.
        guard_kind = extraction_kind(norm_text)
        if guard_kind:
            self.store.log_guard_attempt(user_id, guard_kind, text)
            self.client.send_message(chat_id, REFUSAL_REPLY)
            self.emit_panel_shadow_trace(chat_id, full_name, text, REFUSAL_REPLY, stage_status="intercepted", status="rejected", rule_applied="AGENT_GUARD_REFUSAL")
            return

        # 1. Start command & greetings — the section 13 guide owns the start
        # for new users (scripted steps, resumable); veterans get a short menu.
        if any(c.startswith("/start") or c in {"شروع", "start"} or c in greetings for c in cmd_candidates):
            state = self.store.load_session(session_id, user_id)
            guide = self._guide_for(state, user_id)
            self.store.save_session(session_id, user_id, state)
            if not guide.get("done"):
                self._send_guide_step(chat_id, state, first_name, account, extra=ref_note)
                self.emit_panel_shadow_trace(chat_id, full_name, text, "guide-step", status="approved", rule_applied="CMD_START_GUIDE")
                return
            reply = (
                f"سلام {first_name or 'عزیز'}! 👋\n"
                "فقط بنویس یا ویس بفرست؛ ثبتش با من.\n"
                "• «گزارش مالی» : جمع دخل و خرج\n"
                "• «طلب‌ها» : نسیه‌ها و تسویه\n"
                "• «خروجی ماه» : فایل CSV این ماه\n"
                "• «راهنما» : توضیح کامل"
            )
            reply += (
                "\n\n🎁 کد معرفی تو: " + account["referral_code"] +
                "\nهر کس با این کد بیاید و اولین تراکنشش را ثبت کند، یک ماه رایگان می‌گیری؛ با دومی، پلن ۲ (حسابدار صنف) برایت باز می‌شود."
                "\n• «وضعیت من» : پلن و روزهای رایگان باقی‌مانده‌ات"
            )
            if ref_note:
                reply += ref_note
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

        # 1b. Status command (plan, free days, referral code)
        if any(c in {"وضعیت من", "وضعیت", "/status", "پلن من"} for c in cmd_candidates):
            reply = self.accounts.status_text(user_id)
            self.client.send_message(chat_id, reply)
            self.emit_panel_shadow_trace(chat_id, full_name, text, reply, status="approved", rule_applied="CMD_STATUS")
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
            all_txs = self.store.list_transactions(user_id)
            # Cash totals count cash only; credit lives in «طلب‌ها».
            txs = [t for t in all_txs if t.kind == "cash"]
            if not all_txs:
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
                open_balances = self._credit_balances(user_id)
                if open_balances:
                    reply += (
                        f"\n\n🧾 حساب‌های باز نسیه: {len(open_balances)} مورد "
                        "(جدا از جمع نقدی بالا — با «طلب‌ها» ببین)"
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

        # 4b. Daily report (on demand), monthly export, credit list
        if any(c in {"گزارش امروز", "گزارش روزانه", "/today"} for c in cmd_candidates):
            reply = self.daily_report_text(user_id) or (
                "🌙 گزارش امروز:\nهنوز امروز تراکنش تأییدشده‌ای ثبت نکرده‌ای."
            )
            self.client.send_message(chat_id, reply)
            self.emit_panel_shadow_trace(chat_id, full_name, text, reply, status="approved", rule_applied="CMD_DAILY_REPORT")
            return

        if any(c in {"خروجی ماه", "خروجی", "/export", "اکسل", "گزارش ماهانه"} for c in cmd_candidates):
            self.send_monthly_export(chat_id, user_id)
            self.emit_panel_shadow_trace(chat_id, full_name, text, "monthly-export", status="approved", rule_applied="CMD_EXPORT")
            return

        if any(c in {"طلب‌ها", "طلب ها", "طلبها", "بدهکارها", "بدهکاران", "/credits"} for c in cmd_candidates):
            state = self.store.load_session(session_id, user_id)
            reply, credit_keyboard = self.credit_report(user_id, state)
            self.store.save_session(session_id, user_id, state)
            self.client.send_message(chat_id, reply, reply_markup=credit_keyboard)
            self.emit_panel_shadow_trace(chat_id, full_name, text, reply, status="approved", rule_applied="CMD_CREDITS")
            return

        # 4c. Settlement command: «تسویه احمدی» (full) / «تسویه احمدی ۲۰۰ هزار» (partial)
        settle_match = re.match(r"^تسویه\s+(.+)$", norm_text)
        if settle_match and not norm_text.startswith(("تسویه کرد", "تسویه حساب")):
            reply = self._settle_command(user_id, session_id, settle_match.group(1).strip())
            self.client.send_message(chat_id, reply)
            self.emit_panel_shadow_trace(chat_id, full_name, text, reply, status="approved", rule_applied="CMD_SETTLE")
            return

        # 4d. Undo (soft delete) of confirmed transactions
        if any(c in {"حذف آخری", "حذف آخرین", "حذف آخرین تراکنش", "حذف تراکنش آخری", "برگردان", "برگردان آخری", "/undo", "undo"} for c in cmd_candidates):
            reply, undo_keyboard = self._undo_prompt(user_id, session_id, pick=None)
            self.client.send_message(chat_id, reply, reply_markup=undo_keyboard)
            self.emit_panel_shadow_trace(chat_id, full_name, text, reply, status="approved", rule_applied="CMD_UNDO_LAST")
            return

        if any(c in {"حذف", "حذف تراکنش", "حذف یک تراکنش"} for c in cmd_candidates):
            reply, undo_keyboard = self._undo_list(user_id, session_id)
            self.client.send_message(chat_id, reply, reply_markup=undo_keyboard)
            self.emit_panel_shadow_trace(chat_id, full_name, text, reply, status="approved", rule_applied="CMD_UNDO_LIST")
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
        if pending and not pending.get("draft_id"):
            # Drafts persisted before inline buttons existed get an id the
            # first time they are touched again, so their buttons can bind.
            pending["draft_id"] = _new_draft_id()
            state["pending"] = pending
            self.store.save_session(session_id, user_id, state)
        self.store.add_message(session_id, user_id, "user", text)

        # 6a. A button-first settlement may be waiting for its amount.
        if state.get("settle_ctx"):
            if self._settle_ctx_message(chat_id, state, session_id, user_id, text, norm_text):
                return
            state = self.store.load_session(session_id, user_id)
            pending = state.get("pending")

        # 6b. The guide spine consumes its own answers (never a live draft).
        if state.get("guide") and not state.get("pending"):
            if self._guide_message(
                chat_id, state, session_id, user_id, text, norm_text, first_name, account
            ):
                return
            state = self.store.load_session(session_id, user_id)
            pending = state.get("pending")

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
                self.client.send_message(chat_id, reply, reply_markup=draft_confirm_keyboard(pending["draft_id"]))
                return

            # Stage B: Awaiting direction clarification
            if pending.get("status") == "awaiting_direction":
                negated_direction = has_transaction_negation(norm_text)
                if not negated_direction and any(w in norm_text for w in ["دریافت", "آمد", "اومد", "واریز", "فروش", "دخل", "+", "➕"]):
                    pending["direction"] = "incoming"
                    pending["status"] = "awaiting_confirmation"
                    state["pending"] = pending
                    self.store.save_session(session_id, user_id, state)
                    reply = (
                        f"جهت «دریافتی (آمد به حساب)» ثبت شد.\n"
                        f"💰 مبلغ: {pending['amount']:,} {pending['unit']}\n\n"
                        "برای ثبت نهایی، لطفاً «تأیید» را انتخاب کنید."
                    )
                    self.client.send_message(chat_id, reply, reply_markup=draft_confirm_keyboard(pending["draft_id"]))
                    return
                elif not negated_direction and any(w in norm_text for w in ["پرداخت", "خرج", "خرید", "دادم", "رفت", "-", "➖"]):
                    pending["direction"] = "outgoing"
                    pending["status"] = "awaiting_confirmation"
                    state["pending"] = pending
                    self.store.save_session(session_id, user_id, state)
                    reply = (
                        f"جهت «پرداختی (خرج شد)» ثبت شد.\n"
                        f"💰 مبلغ: {pending['amount']:,} {pending['unit']}\n\n"
                        "برای ثبت نهایی، لطفاً «تأیید» را انتخاب کنید."
                    )
                    self.client.send_message(chat_id, reply, reply_markup=draft_confirm_keyboard(pending["draft_id"]))
                    return
                else:
                    reply = "لطفاً با دکمه‌های زیر مشخص کنید این مبلغ دریافتی بوده یا پرداختی:"
                    self.client.send_message(chat_id, reply, reply_markup=draft_direction_keyboard(pending["draft_id"]))
                    return

            # Stage C: Awaiting unit clarification
            if pending.get("status") == "awaiting_unit" or pending.get("unit") is None:
                if norm_text in {"تومان", "تومن"}:
                    pending["unit"] = "تومان"
                    pending["status"] = "awaiting_confirmation"
                    state["pending"] = pending
                    self.store.save_session(session_id, user_id, state)
                    reply = "برای ثبت این تراکنش بنویسید: تأیید"
                    self.client.send_message(chat_id, reply, reply_markup=draft_confirm_keyboard(pending["draft_id"]))
                    return
                elif norm_text in {"ریال", "ريال"}:
                    pending["unit"] = "ریال"
                    pending["status"] = "awaiting_confirmation"
                    state["pending"] = pending
                    self.store.save_session(session_id, user_id, state)
                    reply = "برای ثبت این تراکنش بنویسید: تأیید"
                    self.client.send_message(chat_id, reply, reply_markup=draft_confirm_keyboard(pending["draft_id"]))
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
            if any(c in CONFIRMATIONS for c in cmd_candidates):
                transaction = Transaction(
                    str(uuid4()),
                    session_id,
                    user_id,
                    pending["amount"],
                    pending["unit"],
                    pending["direction"],
                    "confirmed",
                    _now(),
                    pending.get("description", ""),
                    kind=pending.get("kind", "cash"),
                    counterparty=pending.get("counterparty", ""),
                )
                self.store.add_transaction(transaction)
                state["pending"] = None
                self.store.save_session(session_id, user_id, state)

                desc_line = f"\n📝 بابت: {pending.get('description')}" if pending.get("description") else ""
                if transaction.kind == "credit":
                    who = transaction.counterparty or "نامشخص"
                    side_text = (
                        f"🧾 نسیه — طلب از {who}"
                        if transaction.direction == "incoming"
                        else f"🧾 نسیه — بدهی به {who}"
                    )
                    reply = (
                        "تراکنش با موفقیت ثبت شد. (نسیه — پول نقدی جابه‌جا نشد)\n\n"
                        f"{side_text}\n"
                        f"💰 مبلغ: {transaction.amount:,} {transaction.unit}"
                        f"{desc_line}\n"
                        "با «طلب‌ها» می‌بینی و تسویه‌اش می‌کنی."
                    )
                else:
                    dir_text = "دریافت (آمد به حساب)" if transaction.direction == "incoming" else "پرداخت (خرج/خرید)"
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
                # Section 13: the guide completes on the first real entry.
                guide = state.get("guide") or {}
                if not guide.get("done") and guide.get("step") == GUIDE_STEP_FIRST_ENTRY:
                    self._finish_guide(chat_id, state, session_id, user_id, skipped=False)
                return
            else:
                reply = "برای نهایی شدن تراکنش لطفاً بنویسید «تأیید» یا در صورت انصراف، گزینه «لغو پیش‌نویس» را انتخاب کنید."
                self.client.send_message(chat_id, reply, reply_markup=draft_confirm_keyboard(pending["draft_id"]))
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
                "draft_id": _new_draft_id(),
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
            credit_note = ""
            if bazaar_res.kind == "credit":
                who = bazaar_res.counterparty or "نامشخص"
                credit_note = (
                    f"\n🧾 نسیه: {'طلب از' if bazaar_res.direction == 'incoming' else 'بدهی به'} {who}"
                    " — پول نقدی جابه‌جا نمی‌شود"
                )
            if bazaar_res.direction:
                if bazaar_res.is_sub_thousand_ambiguous:
                    pending = {
                        "draft_id": _new_draft_id(),
                        "amount": bazaar_res.amount,
                        "unit": bazaar_res.unit,
                        "direction": bazaar_res.direction,
                        "description": bazaar_res.description,
                        "status": "awaiting_sub_thousand",
                        "kind": bazaar_res.kind,
                        "counterparty": bazaar_res.counterparty,
                    }
                    state["pending"] = pending
                    self.store.save_session(session_id, user_id, state)
                    reply = (
                        f"📝 پیش‌نویس تراکنش:\n"
                        f"{'➕ دریافت' if bazaar_res.direction == 'incoming' else '➖ پرداخت'}: {bazaar_res.description or 'تراکنش'}\n"
                        f"💰 مبلغ ثبت‌شده: {bazaar_res.amount:,} {bazaar_res.unit}{credit_note}\n\n"
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
                        "draft_id": _new_draft_id(),
                        "amount": bazaar_res.amount,
                        "unit": bazaar_res.unit,
                        "direction": bazaar_res.direction,
                        "description": bazaar_res.description,
                        "status": "awaiting_confirmation",
                        "kind": bazaar_res.kind,
                        "counterparty": bazaar_res.counterparty,
                    }
                    state["pending"] = pending
                    self.store.save_session(session_id, user_id, state)
                    dir_text = "دریافت (آمد به حساب)" if bazaar_res.direction == "incoming" else "پرداخت (خرج/خرید)"
                    desc_line = f"\n📝 بابت: {bazaar_res.description}" if bazaar_res.description else ""
                    reply = (
                        f"📋 پیش‌نویس تراکنش آماده ثبت:\n\n"
                        f"{'➕' if bazaar_res.direction == 'incoming' else '➖'} نوع: {dir_text}"
                        f"{desc_line}\n"
                        f"💰 مبلغ: {bazaar_res.amount:,} {bazaar_res.unit}{credit_note}\n\n"
                        f"آیا تأیید و ثبت شود؟"
                    )
                    self.client.send_message(chat_id, reply, reply_markup=draft_confirm_keyboard(pending["draft_id"]))
                    self.emit_panel_shadow_trace(chat_id, full_name, text, reply, status="approved", rule_applied="FLOW_AWAITING_CONFIRMATION")
                    return
            else:
                pending = {
                    "draft_id": _new_draft_id(),
                    "amount": bazaar_res.amount,
                    "unit": bazaar_res.unit,
                    "direction": None,
                    "description": bazaar_res.description,
                    "status": "awaiting_direction",
                    "kind": bazaar_res.kind,
                    "counterparty": bazaar_res.counterparty,
                }
                state["pending"] = pending
                self.store.save_session(session_id, user_id, state)
                desc_text = f" (بابت {bazaar_res.description})" if bazaar_res.description else ""
                reply = (
                    f"مبلغ {bazaar_res.amount:,} {bazaar_res.unit}{desc_text} مشخص شد.\n\n"
                    f"این مبلغ «دریافتی» (آمد به حساب) بوده یا «پرداختی» (خرج کردید/دادید)؟"
                )
                self.client.send_message(chat_id, reply, reply_markup=draft_direction_keyboard(pending["draft_id"]))
                self.emit_panel_shadow_trace(chat_id, full_name, text, reply, status="approved", rule_applied="FLOW_AWAITING_DIRECTION")
                return

        # Agent laws — the scope gate. Whatever reaches here is free
        # text the deterministic core did not claim (no command, no
        # draft, no parseable amount). Exactly three outcomes:
        #   scoped question -> a core-composed answer (the model may
        #     only rephrase it, through the gated door, caps applied);
        #   scoped but unanswerable -> fixed template + the question is
        #     routed to the supporter panel;
        #   anything else -> the one fixed off-scope template.
        # The model never improvises any of these replies.
        if is_scoped_question(norm_text):
            core_answer = self._scoped_answer(user_id, norm_text)
            if core_answer is not None:
                reply = self._polish_gated(user_id, core_answer)
                self.client.send_message(chat_id, reply)
                self.emit_panel_shadow_trace(chat_id, full_name, text, reply, status="approved", rule_applied="AGENT_SCOPED_ANSWER")
                return
            self._route_question_to_support(user_id, full_name, text)
            self.client.send_message(chat_id, UNKNOWN_REPLY)
            self.emit_panel_shadow_trace(chat_id, full_name, text, UNKNOWN_REPLY, stage_status="intercepted", status="rejected", rule_applied="AGENT_UNKNOWN_ROUTED")
            return
        reply = OFF_SCOPE_REPLY
        keyboard = {
            "keyboard": [
                [{"text": "گزارش مالی"}, {"text": "راهنما"}],
            ],
            "resize_keyboard": True,
        }
        self.client.send_message(chat_id, reply, reply_markup=keyboard)
        self.emit_panel_shadow_trace(chat_id, full_name, text, reply, stage_status="intercepted", status="rejected", rule_applied="AGENT_OFF_SCOPE")

    # A tap is translated into the exact typed text that drives the same
    # state-machine path, so buttons can never diverge from the typed flow.
    _CALLBACK_TEXT = {
        CB_CONFIRM: "تأیید",
        CB_CANCEL: "لغو پیش‌نویس",
        CB_DIR_INCOMING: "دریافت",
        CB_DIR_OUTGOING: "پرداخت",
    }

    def handle_callback_query(self, callback_query: dict[str, Any]) -> None:
        """Route an inline-button tap into the typed message flow.

        Safety contract (stale buttons, double taps, cross-user taps): the
        callback carries the draft_id that was rendered with the button; a
        tap only acts when that id matches the chat's *current* pending
        draft and the draft sits in the stage the button belongs to. Any
        other tap is a no-op with an explanatory reply — never a commit of
        an old, replaced, or someone else's draft.
        """
        query_id = str(callback_query.get("id", "") or "")
        data = str(callback_query.get("data", "") or "")
        message = callback_query.get("message") or {}
        chat = message.get("chat") or {}
        chat_id = str(chat.get("id", "") or "")
        sender = callback_query.get("from") or callback_query.get("from_user") or {}

        def _answer(text: str | None = None) -> None:
            if not query_id:
                return
            try:
                self.client.answer_callback_query(query_id, text=text)
            except Exception:
                logger.exception("answerCallbackQuery failed")

        action, _, draft_token = data.partition(":")
        if (
            not chat_id
            or (action not in self._CALLBACK_TEXT and action not in _ACTION_CALLBACKS)
            or not draft_token
        ):
            _answer("این دکمه دیگر فعال نیست.")
            return

        # Cross-user guard: in a private chat the tapper must be the chat
        # owner. A callback replayed with someone else's identity must not
        # touch this chat's draft (and gets no message into that chat).
        sender_id = sender.get("id")
        chat_type = str(chat.get("type", "private") or "private")
        if (
            sender_id is not None
            and str(sender_id) != chat_id
            and chat_type not in {"group", "supergroup"}
        ):
            logger.warning(
                "Blocked cross-user callback for chat %s from sender %s",
                chat_id,
                sender_id,
            )
            _answer("این دکمه مربوط به گفت‌وگوی شما نیست.")
            return

        if action in _ACTION_CALLBACKS:
            self._handle_action_callback(action, draft_token, chat_id, _answer)
            return

        session_id = f"bale-session-{chat_id}"
        user_id = str(chat_id)
        state = self.store.load_session(session_id, user_id)
        pending = state.get("pending") or {}
        stage_ok = (
            action == CB_CANCEL
            or (action == CB_CONFIRM and pending.get("status") == "awaiting_confirmation")
            or (
                action in (CB_DIR_INCOMING, CB_DIR_OUTGOING)
                and pending.get("status") == "awaiting_direction"
            )
        )
        if not pending or pending.get("draft_id") != draft_token or not stage_ok:
            _answer("این پیش‌نویس دیگر فعال نیست.")
            self.client.send_message(
                chat_id,
                "⚠️ این دکمه مربوط به پیش‌نویسی است که دیگر فعال نیست "
                "(ثبت، لغو یا با پیش‌نویس تازه‌ای جایگزین شده است).",
            )
            return

        _answer()
        synthetic = {
            "message_id": message.get("message_id"),
            "chat": {"id": chat_id, "type": chat_type},
            "from": sender if sender else {"id": chat_id},
            "text": self._CALLBACK_TEXT[action],
            "_from_callback": True,
        }
        self.handle_message(synthetic)

    def _handle_action_callback(self, action: str, token: str, chat_id: str, answer) -> None:
        """Settle / undo buttons: token-bound payloads in the session state.

        Same safety contract as draft buttons: a token that is unknown,
        already consumed, or bound to a different action is a no-op with
        an explanation — stale taps never move money.
        """
        session_id = f"bale-session-{chat_id}"
        user_id = str(chat_id)
        state = self.store.load_session(session_id, user_id)
        binding = self._binding(state, token)
        if not binding or binding.get("act") != action:
            answer("این دکمه دیگر فعال نیست.")
            self.client.send_message(
                chat_id, "⚠️ این دکمه دیگر فعال نیست (استفاده شده یا منقضی شده است)."
            )
            return
        answer()
        bindings = state.setdefault("cb_bindings", {})

        if action in (CB_UNDO_DISMISS, CB_SETTLE_DISMISS):
            bindings.pop(token, None)
            if action == CB_SETTLE_DISMISS:
                state["settle_ctx"] = None
            self.store.save_session(session_id, user_id, state)
            self.client.send_message(chat_id, "باشد، انجام نشد.")
            return

        if action == CB_SETTLE_PICK:
            bindings.pop(token, None)
            cp, unit, side = binding["cp"], binding["unit"], binding["side"]
            open_amount = self._open_balance(user_id, cp, unit, side)
            if open_amount <= 0:
                self.store.save_session(session_id, user_id, state)
                self.client.send_message(chat_id, "این حساب دیگر مانده‌ی بازی ندارد.")
                return
            state["settle_ctx"] = {"cp": cp, "unit": unit, "side": side}
            full_token = self._bind(
                state, {"act": CB_SETTLE_FULL, "cp": cp, "unit": unit, "side": side}
            )
            dismiss_token = self._bind(state, {"act": CB_SETTLE_DISMISS})
            self.store.save_session(session_id, user_id, state)
            label = "طلب" if side == "receivable" else "بدهی"
            keyboard = {
                "inline_keyboard": [
                    [
                        {"text": "✅ همه‌اش", "callback_data": f"{CB_SETTLE_FULL}:{full_token}"},
                        {"text": "❌ بی‌خیال", "callback_data": f"{CB_SETTLE_DISMISS}:{dismiss_token}"},
                    ]
                ]
            }
            self.client.send_message(
                chat_id,
                f"تسویه‌ی {label} {cp}: {open_amount:,} {unit}\n"
                "مبلغ تسویه را بنویس، یا برای تسویه‌ی کامل دکمه را بزن:",
                reply_markup=keyboard,
            )
            return

        if action == CB_SETTLE_FULL:
            bindings.pop(token, None)
            state["settle_ctx"] = None
            self.store.save_session(session_id, user_id, state)
            cp, unit, side = binding["cp"], binding["unit"], binding["side"]
            open_amount = self._open_balance(user_id, cp, unit, side)
            if open_amount <= 0:
                self.client.send_message(chat_id, "این حساب دیگر مانده‌ی بازی ندارد.")
                return
            balance = {"counterparty": cp, "unit": unit, "side": side, "open": open_amount}
            reply = self._execute_settlement(user_id, session_id, balance, open_amount)
            self.client.send_message(chat_id, reply)
            return

        if action == CB_UNDO_PICK:
            bindings.pop(token, None)
            self.store.save_session(session_id, user_id, state)
            tx = self.store.get_transaction(user_id, binding["tx"], include_voided=False)
            if tx is None:
                self.client.send_message(chat_id, "این تراکنش دیگر فعال نیست.")
                return
            reply, keyboard = self._undo_prompt(user_id, session_id, pick=tx)
            self.client.send_message(chat_id, reply, reply_markup=keyboard)
            return

        if action == CB_UNDO_CONFIRM:
            bindings.pop(token, None)
            self.store.save_session(session_id, user_id, state)
            tx = self.store.get_transaction(user_id, binding["tx"])
            if tx is None or tx.voided:
                self.client.send_message(chat_id, "این تراکنش دیگر فعال نیست.")
                return
            self.store.void_transaction(user_id, tx.transaction_id, reason="حذف توسط کاربر")
            if tx.settlement_id:
                # Voiding a settlement's cash row reopens the settled debt.
                self.store.void_settlement(user_id, tx.settlement_id)
            self.client.send_message(
                chat_id,
                f"🗑 حذف شد و از همه‌ی جمع‌ها کنار رفت:\n{self._tx_brief(tx)}",
            )
            return

    def poll_once(self) -> int:
        resp = self.client.get_updates(offset=self._last_offset, limit=20, timeout=5)
        if not resp.get("ok"):
            logger.warning(f"Failed get_updates: {resp}")
            return 0

        updates = resp.get("result", [])
        processed = 0
        for up in updates:
            try:
                up_id = int(up["update_id"])
                if up_id < self._last_offset:
                    continue
                cq = up.get("callback_query")
                msg = up.get("message")
                if cq:
                    self.handle_callback_query(cq)
                elif msg:
                    self.handle_message(msg)
                next_offset = up_id + 1
                self.store.save_poll_offset(next_offset)
            except Exception:
                logger.exception(
                    "Failed to handle Bale update %s; leaving it queued for retry",
                    up.get("update_id", "unknown"),
                )
                break

            self._last_offset = next_offset
            processed += 1

        return processed

    def run_polling_loop(self) -> None:
        self.running = True
        logger.info("Starting Bale Bot polling loop...")
        while self.running:
            try:
                self.poll_once()
                self.send_nightly_reports()
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
