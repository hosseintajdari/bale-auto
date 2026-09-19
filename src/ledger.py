"""Synthetic P0 conversation contract for the Conversational Work Ledger.

This module is deliberately an in-memory test double.  It has no network,
database, channel-adapter, or production credential integration.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Optional
from uuid import uuid4


ACKNOWLEDGEMENT = "پیام دریافت شد. چند لحظه صبر کنید…"
CONFIRMATIONS = {"تأیید", "تایید", "تاييد", "تأیید و ثبت", "confirm"}
UNITS = {"ریال", "ريال", "تومان"}
DIGITS_TABLE = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


@dataclass
class Draft:
    draft_id: str
    user_id: str
    source_body: Optional[str]
    amount_raw: str
    direction: str
    unit_raw: Optional[str] = None
    state: str = "needs_clarification"


@dataclass(frozen=True)
class MoneyRecord:
    record_id: str
    user_id: str
    amount_raw: str
    unit_raw: str
    direction: str
    classification: str
    source_fingerprint: str


class SyntheticLedger:
    """A bounded P0 state machine for synthetic text only."""

    def __init__(self) -> None:
        self._drafts: dict[str, Draft] = {}
        self._records: dict[str, MoneyRecord] = {}
        self._confirmed_by_draft: dict[str, str] = {}

    def receive(self, user_id: str, message: str) -> tuple[str, Draft, str]:
        """Create a money draft and ask exactly one material unit question."""
        amount = self._extract_amount(message)
        direction = "incoming" if any(w in message for w in ("دریافت", "واریز")) else "outgoing"
        draft = Draft(
            draft_id=str(uuid4()),
            user_id=user_id,
            source_body=message,
            amount_raw=amount,
            direction=direction,
        )
        self._drafts[draft.draft_id] = draft
        question = f"مبلغ پیام {amount} است. واحد را انتخاب کنید: ریال یا تومان؟"
        return ACKNOWLEDGEMENT, draft, question

    def answer_unit(self, user_id: str, draft_id: str, unit: str) -> str:
        draft = self._owned_draft(user_id, draft_id)
        if draft.state != "needs_clarification":
            raise ValueError("Draft is not awaiting a clarification.")
        cleaned_unit = unit.strip()
        if cleaned_unit not in UNITS:
            raise ValueError("Unit must be ریال or تومان.")
        draft.unit_raw = "ریال" if cleaned_unit in {"ریال", "ريال"} else "تومان"
        draft.state = "awaiting_confirmation"
        return (
            "پیش‌نویس دریافت وجه آماده است.\n"
            f"مبلغ: {draft.amount_raw} {draft.unit_raw}\n"
            "دسته‌بندی: نامشخص (در فروش محاسبه نمی‌شود)\n"
            "برای ثبت بنویسید: تأیید"
        )

    def confirm(self, user_id: str, draft_id: str, reply: str) -> MoneyRecord:
        draft = self._owned_draft(user_id, draft_id)
        if draft.state == "confirmed":
            return self._records[self._confirmed_by_draft[draft_id]]
        if draft.state != "awaiting_confirmation" or reply.strip().casefold() not in CONFIRMATIONS:
            raise ValueError("An explicit confirmation is required before recording.")
        assert draft.unit_raw is not None
        fingerprint = sha256((draft.user_id + "\x00" + (draft.source_body or "")).encode()).hexdigest()
        record = MoneyRecord(
            record_id=str(uuid4()),
            user_id=draft.user_id,
            amount_raw=draft.amount_raw,
            unit_raw=draft.unit_raw,
            direction=draft.direction,
            classification="unknown",
            source_fingerprint=fingerprint,
        )
        self._records[record.record_id] = record
        self._confirmed_by_draft[draft_id] = record.record_id
        draft.state = "confirmed"
        draft.source_body = None  # P0 retention rule: purge raw source on resolution.
        return record

    def cancel(self, user_id: str, draft_id: str) -> str:
        draft = self._owned_draft(user_id, draft_id)
        if draft.state == "confirmed":
            raise ValueError("A confirmed record cannot be cancelled.")
        if draft.state == "cancelled":
            return "پیش‌نویس قبلاً لغو شده است."
        draft.state = "cancelled"
        draft.source_body = None
        return "پیش‌نویس با موفقیت لغو شد."

    def list_records(self, user_id: str) -> list[MoneyRecord]:
        return [r for r in self._records.values() if r.user_id == user_id]

    def summary(self, user_id: str) -> dict[str, Any]:
        records = [r for r in self._records.values() if r.user_id == user_id]
        totals: dict[str, dict[str, int]] = {
            "ریال": {"incoming": 0, "outgoing": 0},
            "تومان": {"incoming": 0, "outgoing": 0},
        }
        for rec in records:
            unit = rec.unit_raw if rec.unit_raw in totals else "تومان"
            amount = int(rec.amount_raw) if rec.amount_raw.isdigit() else 0
            if rec.direction == "incoming":
                totals[unit]["incoming"] += amount
            else:
                totals[unit]["outgoing"] += amount
        return {
            "user_id": user_id,
            "record_count": len(records),
            "totals": totals,
        }

    def retrieve(self, user_id: str, record_id: str) -> MoneyRecord:
        record = self._records.get(record_id)
        if record is None:
            raise KeyError(f"Record '{record_id}' not found.")
        if record.user_id != user_id:
            raise PermissionError("Records are private to their owner.")
        return record

    @staticmethod
    def _extract_amount(message: str) -> str:
        translated = message.translate(DIGITS_TABLE)
        digits = "".join(character for character in translated if character.isdigit())
        if not digits:
            raise ValueError("A synthetic P0 money message must contain an amount.")
        return digits

    def _owned_draft(self, user_id: str, draft_id: str) -> Draft:
        draft = self._drafts.get(draft_id)
        if draft is None:
            raise KeyError(f"Draft '{draft_id}' not found.")
        if draft.user_id != user_id:
            raise PermissionError("Drafts are private to their owner.")
        return draft
