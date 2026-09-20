"""Persistent synthetic conversation sessions and transaction storage.

This module is deliberately dependency-free and local-only. It stores only the
structured conversation state required to resume a synthetic money workflow.
It does not connect to channels, models, or production credentials.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import re
import sqlite3
from threading import RLock
from typing import Any
from uuid import uuid4

CONFIRMATIONS = {"تأیید", "تایید", "تأیید و ثبت", "تایید و ثبت", "confirm"}
UNITS = {"ریال", "ريال", "تومان"}
DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
MONEY_RE = re.compile(r"^(دریافت|واریز|پرداخت|برداشت)\s*:?[ ]*([0-9۰-۹٠-٩][0-9۰-۹٠-٩,٬]*)")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize(text: str) -> str:
    return " ".join(text.translate(DIGITS).replace("ي", "ی").replace("ك", "ک").split())


@dataclass(frozen=True)
class Transaction:
    transaction_id: str
    session_id: str
    user_id: str
    amount: int
    unit: str
    direction: str
    status: str
    created_at: str


class ConversationStore:
    """SQLite persistence for sessions, messages, and confirmed transactions."""

    def __init__(self, path: str = ":memory:") -> None:
        self.path = path
        self._lock = RLock()
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA foreign_keys = ON")
        self._db.executescript(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY, user_id TEXT NOT NULL,
                state_json TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS messages (
                message_id TEXT PRIMARY KEY, session_id TEXT NOT NULL,
                user_id TEXT NOT NULL, role TEXT NOT NULL, body TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(session_id) REFERENCES sessions(session_id)
            );
            CREATE TABLE IF NOT EXISTS transactions (
                transaction_id TEXT PRIMARY KEY, session_id TEXT NOT NULL,
                user_id TEXT NOT NULL, amount INTEGER NOT NULL, unit TEXT NOT NULL,
                direction TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL,
                FOREIGN KEY(session_id) REFERENCES sessions(session_id)
            );
            CREATE INDEX IF NOT EXISTS idx_transactions_user ON transactions(user_id, created_at);
            """
        )
        self._db.commit()

    def close(self) -> None:
        with self._lock:
            self._db.close()

    def load_session(self, session_id: str, user_id: str) -> dict[str, Any]:
        with self._lock:
            row = self._db.execute("SELECT * FROM sessions WHERE session_id=?", (session_id,)).fetchone()
            if row and row["user_id"] != user_id:
                raise PermissionError("Session belongs to another user")
            if row:
                return json.loads(row["state_json"])
            state = {"pending": None, "created_at": _now()}
            self._db.execute("INSERT INTO sessions VALUES (?, ?, ?, ?)", (session_id, user_id, json.dumps(state), _now()))
            self._db.commit()
            return state

    def save_session(self, session_id: str, user_id: str, state: dict[str, Any]) -> None:
        with self._lock:
            self._db.execute("UPDATE sessions SET state_json=?, updated_at=? WHERE session_id=? AND user_id=?", (json.dumps(state, ensure_ascii=False), _now(), session_id, user_id))
            self._db.commit()

    def add_message(self, session_id: str, user_id: str, role: str, body: str) -> str:
        if role not in {"user", "assistant"}:
            raise ValueError("role must be user or assistant")
        message_id = str(uuid4())
        with self._lock:
            self._db.execute("INSERT INTO messages VALUES (?, ?, ?, ?, ?, ?)", (message_id, session_id, user_id, role, body, _now()))
            self._db.commit()
        return message_id

    def add_transaction(self, transaction: Transaction) -> None:
        with self._lock:
            self._db.execute("INSERT INTO transactions VALUES (?, ?, ?, ?, ?, ?, ?, ?)", tuple(transaction.__dict__.values()))
            self._db.commit()

    def list_transactions(self, user_id: str, session_id: str | None = None) -> list[Transaction]:
        query = "SELECT * FROM transactions WHERE user_id=?"
        args: list[str] = [user_id]
        if session_id is not None:
            query += " AND session_id=?"
            args.append(session_id)
        query += " ORDER BY created_at"
        with self._lock:
            return [Transaction(**dict(row)) for row in self._db.execute(query, args).fetchall()]

    def list_messages(self, session_id: str, user_id: str) -> list[dict[str, Any]]:
        with self._lock:
            row = self._db.execute("SELECT user_id FROM sessions WHERE session_id=?", (session_id,)).fetchone()
            if row is None or row["user_id"] != user_id:
                raise PermissionError("Session belongs to another user")
            return [dict(r) for r in self._db.execute("SELECT message_id, role, body, created_at FROM messages WHERE session_id=? ORDER BY created_at, rowid", (session_id,)).fetchall()]


class ConversationService:
    """Resume a bounded Persian money conversation across service instances."""

    def __init__(self, store: ConversationStore) -> None:
        self.store = store

    def handle(self, session_id: str, user_id: str, text: str) -> dict[str, Any]:
        if not session_id.strip() or not user_id.strip():
            raise ValueError("session_id and user_id are required")
        if not isinstance(text, str) or not text.strip():
            raise ValueError("message text is required")
        state = self.store.load_session(session_id, user_id)
        self.store.add_message(session_id, user_id, "user", text)
        pending = state.get("pending")
        normalized = _normalize(text)
        if pending is None:
            match = MONEY_RE.match(normalized)
            if not match:
                reply = "مبلغ را با دریافت، واریز، پرداخت یا برداشت و عدد روشن بنویسید."
                return self._finish(session_id, user_id, state, reply, "manual_clarification")
            amount = int(match.group(2).replace(",", "").replace("٬", ""))
            if amount <= 0:
                raise ValueError("amount must be positive")
            pending = {"amount": amount, "direction": "incoming" if match.group(1) in {"دریافت", "واریز"} else "outgoing", "unit": None}
            state["pending"] = pending
            reply = "واحد مبلغ ریال است یا تومان؟"
            return self._finish(session_id, user_id, state, reply, "awaiting_unit")
        if pending["unit"] is None:
            if normalized not in UNITS:
                raise ValueError("Explicit unit required: ریال or تومان")
            pending["unit"] = "ریال" if normalized == "ريال" else normalized
            reply = "برای ثبت این تراکنش بنویسید: تأیید"
            return self._finish(session_id, user_id, state, reply, "awaiting_confirmation")
        if normalized.casefold() not in CONFIRMATIONS:
            raise ValueError("Explicit confirmation is required")
        transaction = Transaction(str(uuid4()), session_id, user_id, pending["amount"], pending["unit"], pending["direction"], "confirmed", _now())
        self.store.add_transaction(transaction)
        state["pending"] = None
        result = self._finish(session_id, user_id, state, "تراکنش با موفقیت ثبت شد.", "confirmed")
        result["transaction"] = transaction
        return result

    def _finish(self, session_id: str, user_id: str, state: dict[str, Any], reply: str, status: str) -> dict[str, Any]:
        self.store.save_session(session_id, user_id, state)
        self.store.add_message(session_id, user_id, "assistant", reply)
        return {"status": status, "reply": reply}
