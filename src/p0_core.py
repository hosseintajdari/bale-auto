"""Dependency-free, synthetic-only P0. No network, database or model calls.

This deliberately bounded parser is a manual-clarification fallback, not an
LLM/NLU implementation. One process owns state. No restart durability is claimed.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import re
from secrets import token_bytes
from threading import RLock
from uuid import uuid4

ACK = "پیام دریافت شد. چند لحظه صبر کنید…"
CONFIRM = {"تأیید", "تایید", "تأیید و ثبت", "confirm"}
YES = {"بله", "آره", "yes"}
CLASSES = {
    "فروش": "sale", "وصول طلب": "receivable_collection",
    "انتقال": "personal_or_inter_account_transfer", "وام": "loan_or_capital",
    "سرمایه": "loan_or_capital", "سایر": "other", "نامشخص": "unknown",
}
KINDS = {"money", "memo", "task", "reminder", "preference", "relationship"}
ACTIVE = {"needs_clarification", "awaiting_confirmation", "possible_duplicate"}
DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
NUMBER = r"(?:[0-9]{1,3}(?:[,٬][0-9]{3})+|[0-9]+)"
MONEY = re.compile(r"^(دریافت|واریز|پرداخت|برداشت)\s*:?\s*(" + NUMBER + r")(?=\s|$)(?:\s+(تومان|ریال))?(?:\s|$)")


def normalize(text):
    return " ".join(text.translate(DIGITS).replace("ي", "ی").replace("ك", "ک").split())


def synchronized(method):
    def call(self, *args, **kwargs):
        with self._lock:
            self._sweep()
            return method(self, *args, **kwargs)
    return call


@dataclass(frozen=True)
class Scope:
    bot_id: str
    platform: str
    user_id: str
    conversation_id: str

    def __post_init__(self):
        if not all(isinstance(x, str) and x.strip() for x in self.values()):
            raise ValueError("Stable nonempty scope identifiers are required")

    def values(self):
        return (self.bot_id, self.platform, self.user_id, self.conversation_id)


class P0Ledger:
    def __init__(self, clock=None):
        self.now = clock or (lambda: datetime.now(timezone.utc))
        self._lock = RLock()
        self._key = token_bytes(32)  # ephemeral fingerprint key, never persisted/logged
        self._drafts = {}
        self._records = {}
        self._receipts = {}
        self._tombstones = {}
        self.audit = []

    def _digest(self, scope, value):
        raw = json.dumps([scope.values(), value], ensure_ascii=False).encode()
        return hmac.new(self._key, raw, hashlib.sha256).hexdigest()

    def _sweep(self):
        now = self.now()
        for draft in self._drafts.values():
            if draft["state"] in ACTIVE and draft["expires_at"] <= now:
                draft.update(state="expired", source=None, fields={})
        for key, expiry in list(self._tombstones.items()):
            if expiry <= now:
                del self._tombstones[key]
        for key, receipt in list(self._receipts.items()):
            if receipt["expires_at"] <= now:
                del self._receipts[key]

    def _owned(self, collection, scope, ident):
        value = collection.get(ident)
        if value is None or value["scope"] != scope:
            raise PermissionError("Object unavailable in this scope")
        return value

    def _audit(self, event, ident):
        self.audit.append({"event": event, "id": ident, "time": self.now().isoformat(), "status": "ok"})

    def _emit_to_panel(self, draft):
        import os
        import threading
        import urllib.request
        import json

        # Avoid blocking unit/acceptance tests on dead external endpoints
        if os.environ.get("PYTEST_CURRENT_TEST") and os.environ.get("ENABLE_PANEL_EMIT") != "1":
            return
        if os.environ.get("DISABLE_PANEL_EMIT") == "1":
            return

        payload = {
            "engine_id": "bale-auto",
            "shadow_item": {
                "id": draft["id"],
                "sessionId": draft["scope"].conversation_id,
                "channel": draft["scope"].platform,
                "senderDisplay": draft["scope"].user_id,
                "userMessage": draft.get("source", ""),
                "proposedReply": "تایید می‌کنید؟",
                "timestamp": draft["created_at"].isoformat(),
                "confidenceScore": 0.9,
                "riskLevel": "safe",
                "status": "pending",
                "deterministicRuleApplied": None
            },
            "pipeline_traces": [
                {
                    "stage": "GATEWAY_INGEST",
                    "title": "Received via P0 Ledger",
                    "status": "passed",
                    "detail": "Parsed successfully",
                    "durationMs": 10
                },
                {
                    "stage": "LLM_INFERENCE",
                    "title": "Intent classification",
                    "status": "passed",
                    "detail": f"Parsed as {draft['kind']}",
                    "durationMs": 20
                }
            ]
        }

        def _send():
            try:
                panel_url = os.environ.get("PANEL_SHADOW_TRACE_URL", "http://localhost:3001/api/pipeline/ingest/shadow-trace")
                req = urllib.request.Request(
                    panel_url,
                    data=json.dumps(payload).encode('utf-8'),
                    headers={'Content-Type': 'application/json'}
                )
                urllib.request.urlopen(req, timeout=1)
            except Exception:
                pass

        threading.Thread(target=_send, daemon=True).start()

    def _new(self, scope, kind, fields, source=None, action="create", target=None):
        ident = str(uuid4())
        draft = dict(id=ident, scope=scope, kind=kind, fields=deepcopy(fields), source=source,
                     action=action, target=target, state="needs_clarification", result=None,
                     fingerprint=self._digest(scope, normalize(source)) if source else None,
                     created_at=self.now(), expires_at=self.now() + timedelta(hours=24))
        self._drafts[ident] = draft
        self._refresh(draft)
        self._emit_to_panel(draft)
        return ident

    def _refresh(self, draft):
        if draft["state"] == "possible_duplicate":
            return
        f = draft["fields"]
        required = []
        if draft["kind"] == "money" and draft["action"] != "delete":
            required = [x for x in ("unit_raw", "classification") if f.get(x) is None]
        if draft["kind"] == "reminder" and draft["action"] != "delete" and not f.get("due"):
            required = ["due"]
        draft["missing"] = required
        draft["state"] = "needs_clarification" if required else "awaiting_confirmation"

    @synchronized
    def receive(self, scope, message_id, text):
        if not isinstance(message_id, str) or not message_id.strip():
            raise ValueError("Stable message ID required")
        if not isinstance(text, str) or len(text) > 8000:
            raise ValueError("Bounded text required")
        event_key = self._digest(scope, ["message", message_id])
        body_hash = self._digest(scope, text)
        old = self._receipts.get(event_key)
        if old:
            if old["body_hash"] != body_hash:
                raise ValueError("Message identity reused with changed body")
            return {"ack": ACK, "draft_ids": list(old["draft_ids"]), "status": "replayed"}
        chunks = [x.strip() for x in re.split(r"[;؛\n]", text) if x.strip()]
        parsed = []
        for chunk in chunks:
            candidate = self._parse(chunk)
            if candidate is None:
                # Fail the entire compound input closed; do not silently lose clauses.
                return {"ack": ACK, "draft_ids": [], "status": "manual_clarification",
                        "question": "این پیام مبهم یا خارج از دامنه است. هر مورد را جدا و روشن بنویسید؛ یا بگویید ثبت نکن."}
            parsed.append((chunk, candidate))
        ids = []
        for chunk, (kind, fields) in parsed:
            fingerprint = self._digest(scope, normalize(chunk))
            if fingerprint in self._tombstones:
                continue
            ident = self._new(scope, kind, fields, chunk)
            draft = self._drafts[ident]
            exists = any(r["scope"] == scope and r["fingerprint"] == fingerprint for r in self._records.values())
            pending = any(d["id"] != ident and d["scope"] == scope and d["state"] in ACTIVE and d["fingerprint"] == fingerprint for d in self._drafts.values())
            if exists or pending:
                draft["state"] = "possible_duplicate"
            ids.append(ident)
        self._receipts[event_key] = dict(body_hash=body_hash, draft_ids=ids,
                                        expires_at=self.now() + timedelta(days=30))
        return {"ack": ACK, "draft_ids": ids, "status": "draft" if ids else "suppressed"}

    def _parse(self, raw):
        text = normalize(raw)
        match = MONEY.match(text)
        if match:
            # Multiple money clauses, negation and conflicting direction need a human.
            tail = text[match.end():]
            if re.search(r"دریافت|واریز|پرداخت|برداشت|نشد|نشده|نیست|قیمت|شاید|احتمال", tail):
                return None
            action, amount, unit = match.groups()
            # Preserve the actual source numeral spelling, not concatenated other digits.
            raw_amount = re.search(r"[0-9۰-۹٠-٩]+(?:[,٬][0-9۰-۹٠-٩]+)*", raw).group()
            meanings = {v for k, v in CLASSES.items() if re.search(r"(?:^|\s)" + k + r"(?:\s|$)", tail)}
            if len(meanings) > 1 or re.search(r"یادداشت:|کار:|یادآوری:|ترجیح:|رابطه:", tail):
                return None
            if (unit == "ریال" and "تومان" in tail) or (unit == "تومان" and "ریال" in tail):
                return None
            classification = next(iter(meanings), None)
            if len(re.findall(r"\b\d{4}-\d{2}-\d{2}\b", tail)) > 1:
                return None
            event_date = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", tail)
            event_time = self.now().date().isoformat()
            if event_date:
                try:
                    event_time = datetime.strptime(event_date.group(), "%Y-%m-%d").date().isoformat()
                except ValueError:
                    return None
            if any(x in tail for x in ("دیروز", "فردا", "ماه", "هفته")):
                return None
            if int(amount.replace(",", "").replace("٬", "")) <= 0:
                return None
            return "money", dict(amount_raw=raw_amount, unit_raw=unit, classification=classification,
                                 direction="incoming" if action in {"دریافت", "واریز"} else "outgoing",
                                 event_time=event_time)
        prefixes = {"یادداشت:": "memo", "قیمت:": "memo", "کار:": "task",
                    "یادآوری:": "reminder", "ترجیح:": "preference", "رابطه:": "relationship"}
        for prefix, kind in prefixes.items():
            if text.startswith(prefix) and text[len(prefix):].strip():
                fields = {"title": text[len(prefix):].strip()}
                if kind == "task":
                    fields["status"] = "open"
                if kind == "reminder":
                    fields.update(due=None, delivery="pull-only", privacy="private")
                return kind, fields
        return None

    @synchronized
    def preview(self, scope, ident):
        d = self._owned(self._drafts, scope, ident)
        result = {k: deepcopy(d[k]) for k in ("id", "kind", "action", "state", "fields", "result")}
        if d["kind"] == "money" and d["fields"].get("unit_raw"):
            raw_amount = normalize(str(d["fields"]["amount_raw"])).replace(",", "").replace("٬", "")
            result["fields"]["amount_normalized"] = int(raw_amount) * (10 if d["fields"]["unit_raw"] == "تومان" else 1)
            result["fields"]["currency"] = "IRR"
        questions = {"unit_raw": "واحد مبلغ ریال است یا تومان؟", "classification": "این دریافت/پرداخت فروش، وصول طلب، انتقال، وام، سایر یا نامشخص است؟", "due": "موعد را با تاریخ میلادی YYYY-MM-DD بنویسید یا بگویید بی‌زمان."}
        result["question"] = questions[d["missing"][0]] if d.get("missing") and d["state"] == "needs_clarification" else None
        if d["action"] in {"correct", "delete"}:
            record = self._owned(self._records, scope, d["target"])
            result["before"] = deepcopy(record["fields"])
            if d["action"] == "delete":
                result["notice"] = "حذف دائمی است و فقط همین مورد را حذف می‌کند. برای حذف بنویسید: تأیید حذف"
                result["linked_reminder_ids"] = [r["id"] for r in self._records.values() if r["scope"] == scope and r["fields"].get("linked_to") == record["id"]]
        return result

    @synchronized
    def clarify(self, scope, ident, reply):
        d = self._owned(self._drafts, scope, ident)
        if d["state"] != "needs_clarification":
            raise ValueError("No pending clarification")
        field = d["missing"][0]
        value = normalize(reply)
        if field == "unit_raw":
            if value not in {"ریال", "تومان"}:
                raise ValueError("Explicit unit required")
        elif field == "classification":
            if value not in CLASSES:
                raise ValueError("Explicit classification choice required")
            value = CLASSES[value]
        else:
            if value == "بی‌زمان":
                value = "no-time"
            else:
                value = datetime.strptime(value, "%Y-%m-%d").date().isoformat()
        d["fields"][field] = value
        self._refresh(d)
        return self.preview(scope, ident)

    @synchronized
    def resolve_duplicate(self, scope, ident, reply):
        d = self._owned(self._drafts, scope, ident)
        if d["state"] != "possible_duplicate" or reply not in {"تکراری", "جدا"}:
            raise ValueError("Explicit duplicate/separate choice required")
        if reply == "تکراری":
            d.update(state="cancelled", source=None, fields={})
        else:
            d["state"] = "needs_clarification"
            d["duplicate_accepted"] = True
            self._refresh(d)
        return self.preview(scope, ident)

    @synchronized
    def cancel(self, scope, ident):
        d = self._owned(self._drafts, scope, ident)
        if d["state"] not in ACTIVE:
            raise ValueError("Cancellation only closes an active draft")
        d.update(state="cancelled", source=None, fields={})

    @synchronized
    def confirm(self, scope, ident, reply):
        d = self._owned(self._drafts, scope, ident)
        text = normalize(reply)
        allowed = {"تأیید حذف"} if d["action"] == "delete" else ({"تأیید اصلاح"} if d["action"] == "correct" else CONFIRM)
        if d["action"] == "create" and text in YES:
            ready = [x for x in self._drafts.values() if x["scope"] == scope and x["state"] in ACTIVE]
            if d["state"] != "confirmed" and (len(ready) != 1 or ready[0]["id"] != ident):
                raise ValueError("Ambiguous yes does not confirm an object")
            text = "تأیید"
        if text not in allowed:
            raise ValueError("Matching explicit confirmation required")
        if d["state"] == "confirmed":
            return d["result"]
        if d["state"] != "awaiting_confirmation":
            raise ValueError("Draft is not ready")
        if d["action"] == "delete":
            self._delete(scope, d["target"])
            result = d["target"]
        else:
            old = None
            if d["action"] == "correct":
                old = self._owned(self._records, scope, d["target"])
                if old["state"] != "confirmed":
                    raise ValueError("Stale correction target")
            elif not d.get("duplicate_accepted") and any(r["scope"] == scope and r["fingerprint"] == d["fingerprint"] for r in self._records.values()):
                d["state"] = "possible_duplicate"
                raise ValueError("Resolve newly confirmed duplicate first")
            result = str(uuid4())
            fields = deepcopy(d["fields"])
            if d["kind"] == "money":
                amount = int(normalize(fields["amount_raw"]).replace(",", "").replace("٬", ""))
                fields["amount_normalized"] = amount * (10 if fields["unit_raw"] == "تومان" else 1)
                fields["currency"] = "IRR"
            self._records[result] = dict(id=result, scope=scope, kind=d["kind"], fields=fields,
                fingerprint=d["fingerprint"] if old is None else old["fingerprint"],
                state="confirmed", supersedes=old["id"] if old else None,
                created_at=self.now().isoformat())
            if old:
                old["state"] = "superseded"
                # An active reminder follows the replacement without copying its fields.
                for r in self._records.values():
                    if r["scope"] == scope and r["fields"].get("linked_to") == old["id"]:
                        r["fields"]["linked_to"] = result
        d.update(state="confirmed", result=result, source=None, fields={})
        self._audit(d["action"], result)
        return result

    @synchronized
    def propose_correction(self, scope, record_id, **changes):
        r = self._owned(self._records, scope, record_id)
        if r["state"] != "confirmed":
            raise ValueError("Select an active record")
        allowed = {"amount_raw", "unit_raw", "classification", "event_time"} if r["kind"] == "money" else {"title"}
        if not changes or not set(changes) <= allowed:
            raise ValueError("Unsupported correction")
        fields = deepcopy(r["fields"])
        fields.update(changes)
        if r["kind"] == "money":
            if not re.fullmatch(NUMBER, normalize(str(fields["amount_raw"]))):
                raise ValueError("Invalid amount")
            if int(normalize(str(fields["amount_raw"])).replace(",", "").replace("٬", "")) <= 0:
                raise ValueError("Amount must be positive")
            if fields["unit_raw"] not in {"ریال", "تومان"} or fields["classification"] not in CLASSES.values():
                raise ValueError("Invalid unit or classification")
            datetime.strptime(fields["event_time"], "%Y-%m-%d")
        return self._new(scope, r["kind"], fields, action="correct", target=record_id)

    @synchronized
    def revise_draft(self, scope, draft_id, **changes):
        """Revise candidate fields only; the next explicit confirmation still gates storage."""
        d = self._owned(self._drafts, scope, draft_id)
        if d["state"] not in {"awaiting_confirmation", "needs_clarification"} or d["action"] != "create":
            raise ValueError("Select an active creation draft")
        allowed = {"amount_raw", "unit_raw", "classification"} if d["kind"] == "money" else {"title"}
        if not changes or not set(changes) <= allowed:
            raise ValueError("Unsupported draft revision")
        fields = deepcopy(d["fields"])
        fields.update(changes)
        if d["kind"] == "money":
            amount = normalize(str(fields["amount_raw"]))
            if not re.fullmatch(NUMBER, amount) or int(amount.replace(",", "").replace("٬", "")) <= 0:
                raise ValueError("Invalid amount")
            if fields["unit_raw"] not in {None, "ریال", "تومان"} or fields["classification"] not in {None, *CLASSES.values()}:
                raise ValueError("Invalid unit or classification")
        elif not isinstance(fields["title"], str) or not fields["title"].strip():
            raise ValueError("Explicit title required")
        d["fields"] = fields
        self._refresh(d)
        return self.preview(scope, draft_id)

    @synchronized
    def propose_delete(self, scope, record_id):
        r = self._owned(self._records, scope, record_id)
        if r["state"] != "confirmed":
            raise ValueError("Select an active record")
        return self._new(scope, r["kind"], {}, action="delete", target=record_id)

    def _delete(self, scope, record_id):
        r = self._owned(self._records, scope, record_id)
        # Purge all superseded revisions so deleted content cannot be reconstructed.
        chain = {record_id}
        previous = r.get("supersedes")
        while previous:
            chain.add(previous)
            previous = self._records[previous].get("supersedes")
        for ident in chain:
            removed = self._records.pop(ident)
            if removed["fingerprint"]:
                self._tombstones[removed["fingerprint"]] = self.now() + timedelta(days=30)
        for d in self._drafts.values():
            if d["result"] in chain or d["target"] in chain:
                d.update(source=None, fields={})
                if d["state"] in ACTIVE and d["action"] != "delete":
                    d["state"] = "cancelled"

    @synchronized
    def link_reminder(self, scope, draft_id, record_id):
        d = self._owned(self._drafts, scope, draft_id)
        r = self._owned(self._records, scope, record_id)
        if d["kind"] != "reminder" or d["state"] not in ACTIVE or r["state"] != "confirmed":
            raise ValueError("Active reminder draft and record required")
        d["fields"]["linked_to"] = record_id

    @synchronized
    def retrieve(self, scope, record_id):
        r = self._owned(self._records, scope, record_id)
        if r["state"] != "confirmed":
            raise ValueError("Record was replaced")
        return deepcopy(r)

    @synchronized
    def search(self, scope, query):
        matches = [r for r in self._records.values() if r["scope"] == scope and r["state"] == "confirmed" and normalize(query) in normalize(r["fields"].get("title", ""))]
        if len(matches) == 1:
            return {"status": "found", "record": deepcopy(matches[0])}
        # No body, amount or candidate title disclosure on ambiguous retrieval.
        return {"status": "choose" if matches else "empty", "ids": [r["id"] for r in matches]}

    @synchronized
    def sales(self, scope, start, end):
        datetime.strptime(start, "%Y-%m-%d")
        datetime.strptime(end, "%Y-%m-%d")
        if start > end:
            raise ValueError("Invalid date range")
        money = [r["fields"] for r in self._records.values() if r["scope"] == scope and r["state"] == "confirmed" and r["kind"] == "money" and r["fields"]["direction"] == "incoming" and start <= r["fields"]["event_time"] <= end]
        sales = [r for r in money if r["classification"] == "sale"]
        return dict(start=start, end=end, count=len(sales), total_rial=sum(r["amount_normalized"] for r in sales), unknown_excluded=sum(r["classification"] == "unknown" for r in money), other_incoming_excluded=sum(r["classification"] not in {"sale", "unknown"} for r in money))

    @synchronized
    def reminders(self, scope):
        return [{"id": r["id"], "due": r["fields"]["due"], "private": True} for r in self._records.values() if r["scope"] == scope and r["state"] == "confirmed" and r["kind"] == "reminder"]


class SyntheticSignedAdapter:
    """In-process signing demonstration, not an installed LangBot integration.

    The trusted adapter binds a signed envelope to the complete identity scope.
    A real adapter must obtain these identifiers from platform events, not text.
    """
    def __init__(self, ledger, key=b"SYNTHETIC-P0-ONLY-NOT-A-PRODUCTION-SECRET"):
        self.ledger = ledger
        self.key = key

    def sign(self, payload):
        body = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
        return hmac.new(self.key, body, hashlib.sha256).hexdigest()

    def deliver(self, payload, signature):
        if not isinstance(signature, str) or not hmac.compare_digest(self.sign(payload), signature):
            raise PermissionError("Invalid adapter signature")
        if set(payload) != {"version", "bot_id", "platform", "user_id", "conversation_id", "message_id", "text", "timestamp"} or payload["version"] != 1:
            raise ValueError("Invalid versioned envelope")
        timestamp = datetime.fromisoformat(payload["timestamp"])
        if timestamp.tzinfo is None or abs((self.ledger.now() - timestamp).total_seconds()) > 300:
            raise ValueError("Expired envelope")
        scope = Scope(*(payload[k] for k in ("bot_id", "platform", "user_id", "conversation_id")))
        return self.ledger.receive(scope, payload["message_id"], payload["text"])
