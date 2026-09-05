"""Synthetic P0 conversation contract for the Conversational Work Ledger.

This module is deliberately an in-memory test double.  It has no network,
database, channel-adapter, or production credential integration.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Optional
from uuid import uuid4


ACKNOWLEDGEMENT = "پیام دریافت شد. چند لحظه صبر کنید…"
CONFIRMATIONS = {"تأیید", "تاييد", "confirm"}
UNITS = {"ریال", "ريال", "تومان"}


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
        direction = "incoming" if "دریافت" in message else "outgoing"
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
        if unit not in UNITS:
            raise ValueError("Unit must be ریال or تومان.")
        draft.unit_raw = "ریال" if unit in {"ریال", "ريال"} else "تومان"
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

    def retrieve(self, user_id: str, record_id: str) -> MoneyRecord:
        record = self._records[record_id]
        if record.user_id != user_id:
            raise PermissionError("Records are private to their owner.")
        return record

    @staticmethod
    def _extract_amount(message: str) -> str:
        digits = "".join(character for character in message if character.isdigit())
        if not digits:
            raise ValueError("A synthetic P0 money message must contain an amount.")
        return digits

    def _owned_draft(self, user_id: str, draft_id: str) -> Draft:
        draft = self._drafts[draft_id]
        if draft.user_id != user_id:
            raise PermissionError("Drafts are private to their owner.")
        return draft
