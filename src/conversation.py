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

CONFIRMATIONS = {"تأیید", "تایید", "تأیید و ثبت", "تایید و ثبت", "confirm", "ok"}
UNITS = {"ریال", "ريال", "تومان", "تومن"}
DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
MONEY_RE = re.compile(
    r"^(دریافت|واریز|پرداخت|برداشت)\s*:?[ ]*([0-9][0-9,٬]*(?:\.[0-9]+)?)"
)


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
    description: str = ""
    # Credit model (نسیه): kind "cash" moves money now; kind "credit" is a
    # receivable (direction "incoming") or payable (direction "outgoing")
    # against counterparty and moves no cash until settled.
    kind: str = "cash"
    counterparty: str = ""
    # Link to the settlements row when this cash row IS a settlement.
    settlement_id: str = ""
    # Soft delete (undo): the row stays for audit, flagged and excluded
    # from every total; money history is never hard-deleted.
    voided: int = 0
    voided_at: str = ""
    void_reason: str = ""


@dataclass(frozen=True)
class Settlement:
    """A recorded settlement event against one person's open credit."""

    settlement_id: str
    user_id: str
    counterparty: str
    unit: str
    side: str  # "receivable" (they owed the user) | "payable" (user owed them)
    amount: int
    created_at: str
    voided: int = 0
    voided_at: str = ""


_TX_COLUMNS = (
    "transaction_id", "session_id", "user_id", "amount", "unit", "direction",
    "status", "created_at", "description", "kind", "counterparty",
    "settlement_id", "voided", "voided_at", "void_reason",
)
_SETTLEMENT_COLUMNS = (
    "settlement_id", "user_id", "counterparty", "unit", "side", "amount",
    "created_at", "voided", "voided_at",
)


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
            CREATE TABLE IF NOT EXISTS bot_state (
                state_key TEXT PRIMARY KEY, state_value INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS kv_state (
                state_key TEXT PRIMARY KEY, state_value TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_transactions_user ON transactions(user_id, created_at);
            CREATE TABLE IF NOT EXISTS settlements (
                settlement_id TEXT PRIMARY KEY, user_id TEXT NOT NULL,
                counterparty TEXT NOT NULL, unit TEXT NOT NULL,
                side TEXT NOT NULL, amount INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                voided INTEGER NOT NULL DEFAULT 0, voided_at TEXT NOT NULL DEFAULT ''
            );
            CREATE INDEX IF NOT EXISTS idx_settlements_user ON settlements(user_id, created_at);
            """
        )
        # Backward-safe migrations: older ledger files gain the new
        # columns in place; existing rows default to plain cash, unvoided.
        columns = {row[1] for row in self._db.execute("PRAGMA table_info(transactions)").fetchall()}
        for name, ddl in (
            ("description", "TEXT NOT NULL DEFAULT ''"),
            ("kind", "TEXT NOT NULL DEFAULT 'cash'"),
            ("counterparty", "TEXT NOT NULL DEFAULT ''"),
            ("settlement_id", "TEXT NOT NULL DEFAULT ''"),
            ("voided", "INTEGER NOT NULL DEFAULT 0"),
            ("voided_at", "TEXT NOT NULL DEFAULT ''"),
            ("void_reason", "TEXT NOT NULL DEFAULT ''"),
        ):
            if name not in columns:
                self._db.execute(f"ALTER TABLE transactions ADD COLUMN {name} {ddl}")
        self._db.commit()

    def close(self) -> None:
        with self._lock:
            self._db.close()

    def get_poll_offset(self) -> int:
        with self._lock:
            row = self._db.execute(
                "SELECT state_value FROM bot_state WHERE state_key='bale_update_offset'"
            ).fetchone()
            return int(row[0]) if row else 0

    def save_poll_offset(self, offset: int) -> None:
        if offset < 0:
            raise ValueError("poll offset must be non-negative")
        with self._lock:
            self._db.execute(
                """
                INSERT INTO bot_state (state_key, state_value)
                VALUES ('bale_update_offset', ?)
                ON CONFLICT(state_key) DO UPDATE SET state_value=excluded.state_value
                WHERE excluded.state_value >= bot_state.state_value
                """,
                (offset,),
            )
            self._db.commit()

    def get_kv(self, key: str) -> str | None:
        with self._lock:
            row = self._db.execute(
                "SELECT state_value FROM kv_state WHERE state_key=?", (key,)
            ).fetchone()
            return str(row[0]) if row else None

    def set_kv(self, key: str, value: str) -> None:
        with self._lock:
            self._db.execute(
                """
                INSERT INTO kv_state (state_key, state_value) VALUES (?, ?)
                ON CONFLICT(state_key) DO UPDATE SET state_value=excluded.state_value
                """,
                (key, value),
            )
            self._db.commit()

    def list_sessions(self) -> list[dict[str, str]]:
        with self._lock:
            return [
                dict(r)
                for r in self._db.execute(
                    "SELECT session_id, user_id FROM sessions ORDER BY updated_at"
                ).fetchall()
            ]

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
            cursor = self._db.execute(
                """
                INSERT INTO sessions (session_id, user_id, state_json, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    state_json=excluded.state_json,
                    updated_at=excluded.updated_at
                WHERE sessions.user_id=excluded.user_id
                """,
                (session_id, user_id, json.dumps(state, ensure_ascii=False), _now()),
            )
            if cursor.rowcount == 0:
                raise PermissionError("Session belongs to another user")
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
        cols = ", ".join(_TX_COLUMNS)
        marks = ", ".join("?" for _ in _TX_COLUMNS)
        values = [getattr(transaction, c) for c in _TX_COLUMNS]
        with self._lock:
            self._db.execute(f"INSERT INTO transactions ({cols}) VALUES ({marks})", values)
            self._db.commit()

    def list_transactions(
        self, user_id: str, session_id: str | None = None, include_voided: bool = False
    ) -> list[Transaction]:
        query = f"SELECT {', '.join(_TX_COLUMNS)} FROM transactions WHERE user_id=?"
        args: list[Any] = [user_id]
        if session_id is not None:
            query += " AND session_id=?"
            args.append(session_id)
        if not include_voided:
            query += " AND voided=0"
        query += " ORDER BY created_at, rowid"
        with self._lock:
            return [Transaction(**dict(row)) for row in self._db.execute(query, args).fetchall()]

    def get_transaction(
        self, user_id: str, transaction_id: str, include_voided: bool = True
    ) -> Transaction | None:
        query = f"SELECT {', '.join(_TX_COLUMNS)} FROM transactions WHERE user_id=? AND transaction_id=?"
        args: list[Any] = [user_id, transaction_id]
        if not include_voided:
            query += " AND voided=0"
        with self._lock:
            row = self._db.execute(query, args).fetchone()
            return Transaction(**dict(row)) if row else None

    def last_transactions(self, user_id: str, limit: int = 5) -> list[Transaction]:
        """Newest live (non-voided) transactions first — the undo menu."""
        query = (
            f"SELECT {', '.join(_TX_COLUMNS)} FROM transactions "
            "WHERE user_id=? AND voided=0 ORDER BY created_at DESC, rowid DESC LIMIT ?"
        )
        with self._lock:
            return [Transaction(**dict(row)) for row in self._db.execute(query, (user_id, limit)).fetchall()]

    def void_transaction(self, user_id: str, transaction_id: str, reason: str = "") -> Transaction | None:
        """Soft-delete: flag the row, keep it for audit, exclude it from totals."""
        with self._lock:
            cur = self._db.execute(
                "UPDATE transactions SET voided=1, voided_at=?, void_reason=? "
                "WHERE transaction_id=? AND user_id=? AND voided=0",
                (_now(), reason, transaction_id, user_id),
            )
            self._db.commit()
            if cur.rowcount == 0:
                return None
        return self.get_transaction(user_id, transaction_id)

    def add_settlement(self, settlement: Settlement) -> None:
        cols = ", ".join(_SETTLEMENT_COLUMNS)
        marks = ", ".join("?" for _ in _SETTLEMENT_COLUMNS)
        values = [getattr(settlement, c) for c in _SETTLEMENT_COLUMNS]
        with self._lock:
            self._db.execute(f"INSERT INTO settlements ({cols}) VALUES ({marks})", values)
            self._db.commit()

    def list_settlements(self, user_id: str, include_voided: bool = False) -> list[Settlement]:
        query = f"SELECT {', '.join(_SETTLEMENT_COLUMNS)} FROM settlements WHERE user_id=?"
        if not include_voided:
            query += " AND voided=0"
        query += " ORDER BY created_at, rowid"
        with self._lock:
            return [Settlement(**dict(row)) for row in self._db.execute(query, (user_id,)).fetchall()]

    def void_settlement(self, user_id: str, settlement_id: str) -> bool:
        with self._lock:
            cur = self._db.execute(
                "UPDATE settlements SET voided=1, voided_at=? "
                "WHERE settlement_id=? AND user_id=? AND voided=0",
                (_now(), settlement_id, user_id),
            )
            self._db.commit()
            return cur.rowcount > 0

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
            amount_text = match.group(2).replace(",", "").replace("٬", "")
            if "." in amount_text:
                reply = "مبلغ اعشاری پشتیبانی نمی‌شود؛ لطفاً مبلغ را به‌صورت عدد کامل وارد کنید."
                return self._finish(session_id, user_id, state, reply, "manual_clarification")
            amount = int(amount_text)
            if amount <= 0:
                raise ValueError("amount must be positive")
            pending = {"amount": amount, "direction": "incoming" if match.group(1) in {"دریافت", "واریز"} else "outgoing", "unit": None}
            state["pending"] = pending
            reply = "واحد مبلغ ریال است یا تومان؟"
            return self._finish(session_id, user_id, state, reply, "awaiting_unit")
        if pending["unit"] is None:
            if normalized not in UNITS:
                raise ValueError("Explicit unit required: ریال or تومان")
            if normalized in {"تومان", "تومن"}:
                pending["unit"] = "تومان"
            else:
                pending["unit"] = "ریال"
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
