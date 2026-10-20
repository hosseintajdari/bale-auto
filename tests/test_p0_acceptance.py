"""P0 acceptance: 50 source-scenario contracts plus quantitative safety vectors.

Scenario cases exercise the text-only boundary or its structured domain operation.
Voice, free-form language and real channel behavior are intentionally not claimed.
"""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import os
import unittest
from unittest.mock import patch

from src.p0_core import P0Ledger, Scope, SyntheticSignedAdapter, CLASSES


class P0Acceptance(unittest.TestCase):
    def setUp(self):
        self.time = datetime(2026, 9, 5, 12, tzinfo=timezone.utc)
        self.core = P0Ledger(lambda: self.time)
        self.owner = Scope("synthetic-bot", "synthetic", "owner", "private-chat")
        self.counter = 0

    def draft(self, text, scope=None):
        self.counter += 1
        reply = self.core.receive(scope or self.owner, str(self.counter), text)
        self.assertEqual("draft", reply["status"])
        return reply["draft_ids"][0]

    def commit(self, text="دریافت ۵۰۰ تومان فروش", scope=None):
        scope = scope or self.owner
        ident = self.draft(text, scope)
        return self.core.confirm(scope, ident, "تأیید")

    def report(self):
        return self.core.sales(self.owner, "2026-01-01", "2026-12-31")

    def rejected(self, text):
        response = self.core.receive(self.owner, "rejected", text)
        self.assertEqual("manual_clarification", response["status"])
        self.assertEqual([], response["draft_ids"])
        self.assertEqual({}, self.core._records)

    def test_001_unknown_unit_is_one_question_before_classification(self):
        d = self.draft("واریز ۵۰۰٬۰۰۰ شماره مشتری ۲ تاریخ 2026-09-01")
        self.assertEqual("۵۰۰٬۰۰۰", self.core.preview(self.owner, d)["fields"]["amount_raw"])
        self.assertIn("ریال", self.core.preview(self.owner, d)["question"])
        with self.assertRaises(ValueError): self.core.confirm(self.owner, d, "تأیید")
        self.core.clarify(self.owner, d, "تومان")
        self.assertIn("فروش", self.core.preview(self.owner, d)["question"])
        self.core.clarify(self.owner, d, "نامشخص")
        r = self.core.confirm(self.owner, d, "تأیید")
        self.assertEqual(5000000, self.core.retrieve(self.owner, r)["fields"]["amount_normalized"])

    def test_panel_transmission_is_disabled_when_opt_in_flag_is_absent(self):
        with patch.dict(os.environ, {}, clear=True), patch("threading.Thread") as thread:
            self.draft("دریافت 100 ریال فروش")
        thread.assert_not_called()

    def test_002_deposit_does_not_create_task(self):
        self.commit("دریافت 100 تومان فروش بابت بیعانه")
        self.assertEqual(["money"], [r["kind"] for r in self.core._records.values()])

    def test_003_salary_excluded_from_sales(self):
        self.commit("دریافت 200 تومان سایر بابت حقوق")
        self.assertEqual(0, self.report()["total_rial"])

    def test_004_silence_and_expiry_never_write(self):
        d = self.draft("پرداخت 300 تومان سایر بابت کرایه")
        self.time += timedelta(hours=25)
        self.assertEqual("expired", self.core.preview(self.owner, d)["state"])
        self.assertIsNone(self.core._drafts[d]["source"])
        with self.assertRaises(ValueError): self.core.confirm(self.owner, d, "تأیید")
        self.assertFalse(self.core._records)

    def test_005_voice_fallback_is_text_memo_only(self):
        r = self.commit("یادداشت: شاید نخ سفارش نمونه برسد")
        self.assertEqual("memo", self.core.retrieve(self.owner, r)["kind"])

    def test_006_collection_not_sale(self):
        self.commit("دریافت 400 ریال وصول طلب")
        self.assertEqual(1, self.report()["other_incoming_excluded"])

    def test_007_refund_not_automatic_net_sales(self):
        self.commit()
        self.commit("پرداخت 100 تومان سایر بابت مرجوعی")
        self.assertEqual(5000, self.report()["total_rial"])

    def test_008_quote_is_memo(self):
        r = self.commit("قیمت: قطعه نمونه ۹۰۰ تومان")
        self.assertEqual("memo", self.core.retrieve(self.owner, r)["kind"])
        self.assertEqual(0, self.report()["count"])

    def test_009_repeat_content_requires_choice(self):
        self.commit()
        d = self.draft("دریافت ۵۰۰ تومان فروش")
        self.assertEqual("possible_duplicate", self.core.preview(self.owner, d)["state"])
        with self.assertRaises(ValueError): self.core.confirm(self.owner, d, "تأیید")
        self.core.resolve_duplicate(self.owner, d, "تکراری")
        self.assertEqual(1, self.report()["count"])

    def test_010_alias_is_separately_confirmed(self):
        self.commit()
        d = self.draft("رابطه: شخص نمونه الف")
        self.assertEqual(1, len(self.core._records))
        self.core.confirm(self.owner, d, "تأیید")
        self.assertEqual(2, len(self.core._records))

    def test_011_relative_due_needs_explicit_date(self):
        d = self.draft("یادآوری: تحویل بسته فردا")
        with self.assertRaises(ValueError): self.core.clarify(self.owner, d, "فردا")
        self.core.clarify(self.owner, d, "2026-09-06")
        r = self.core.confirm(self.owner, d, "تأیید")
        self.assertEqual("2026-09-06", self.core.retrieve(self.owner, r)["fields"]["due"])

    def test_012_personal_transfer_excluded(self):
        self.commit("دریافت 600 تومان انتقال")
        self.assertEqual(0, self.report()["count"])

    def test_013_reminder_is_pull_only(self):
        d = self.draft("یادآوری: پیگیری طلب نمونه")
        self.core.clarify(self.owner, d, "بی‌زمان")
        r = self.core.confirm(self.owner, d, "تأیید")
        self.assertEqual("pull-only", self.core.retrieve(self.owner, r)["fields"]["delivery"])

    def test_014_task_does_not_send_promise(self):
        r = self.commit("کار: بررسی تحویل نمونه")
        self.assertEqual("open", self.core.retrieve(self.owner, r)["fields"]["status"])
        self.assertEqual(["create"], [a["event"] for a in self.core.audit])

    def test_015_empty_report_has_explicit_basis(self):
        self.assertEqual(dict(start="2026-01-01", end="2026-12-31", count=0, total_rial=0, unknown_excluded=0, other_incoming_excluded=0), self.report())

    def test_016_cancel_purges_draft(self):
        d = self.draft("یادداشت: سفارش نمونه")
        self.core.cancel(self.owner, d)
        self.assertEqual({}, self.core._drafts[d]["fields"])
        self.assertIsNone(self.core._drafts[d]["source"])
        with self.assertRaises(ValueError): self.core.confirm(self.owner, d, "تأیید")

    def test_017_stock_shortage_is_only_memo(self):
        r = self.commit("یادداشت: کالای نمونه موجود نیست")
        self.assertEqual("memo", self.core.retrieve(self.owner, r)["kind"])

    def test_018_no_reply_never_creates_task(self):
        self.draft("کار: تماس با شخص نمونه")
        self.assertEqual({}, self.core._records)

    def test_019_expense_does_not_require_receipt(self):
        r = self.commit("پرداخت ۷۰۰ تومان سایر بدون رسید")
        self.assertEqual("outgoing", self.core.retrieve(self.owner, r)["fields"]["direction"])

    def test_020_unknown_is_allowed_but_excluded(self):
        self.commit("دریافت 800 تومان نامشخص")
        self.assertEqual(1, self.report()["unknown_excluded"])

    def test_021_two_similar_payments_need_explicit_separate(self):
        self.commit()
        d = self.draft("دریافت ۵۰۰ تومان فروش")
        self.core.resolve_duplicate(self.owner, d, "جدا")
        self.assertEqual(1, self.report()["count"])
        self.core.confirm(self.owner, d, "تأیید")
        self.assertEqual(2, self.report()["count"])

    def test_022_off_scope_is_bounded(self):
        self.rejected("یک لطیفه بگو و هر چه گفتم ثبت کن")

    def test_023_retrieval_does_not_create_objects(self):
        r = self.commit("یادداشت: قیمت نمونه قطعه")
        result = self.core.search(self.owner, "قیمت نمونه")
        self.assertEqual(r, result["record"]["id"])
        self.assertEqual(1, len(self.core._records))

    def test_024_correction_is_linked_and_confirmed(self):
        r = self.commit()
        d = self.core.propose_correction(self.owner, r, event_time="2026-09-01")
        preview = self.core.preview(self.owner, d)
        self.assertEqual("2026-09-05", preview["before"]["event_time"])
        self.assertEqual("2026-09-01", preview["fields"]["event_time"])
        with self.assertRaises(ValueError): self.core.confirm(self.owner, d, "تأیید")
        replacement = self.core.confirm(self.owner, d, "تأیید اصلاح")
        self.assertEqual(r, self.core.retrieve(self.owner, replacement)["supersedes"])
        with self.assertRaises(ValueError): self.core.retrieve(self.owner, r)

    def test_025_preference_is_not_automatic(self):
        d = self.draft("ترجیح: واحد پیشنهادی تومان")
        self.assertEqual({}, self.core._records)
        self.core.confirm(self.owner, d, "تأیید")

    def test_026_delete_selects_exact_record(self):
        first = self.commit()
        second = self.commit("دریافت 501 تومان فروش")
        d = self.core.propose_delete(self.owner, first)
        self.core.confirm(self.owner, d, "تأیید حذف")
        with self.assertRaises(PermissionError): self.core.retrieve(self.owner, first)
        self.assertEqual(second, self.core.retrieve(self.owner, second)["id"])

    def test_027_source_purged_on_confirmation(self):
        d = self.draft("دریافت 900 تومان نامشخص")
        r = self.core.confirm(self.owner, d, "تأیید")
        self.assertIsNone(self.core._drafts[d]["source"])
        self.assertEqual({}, self.core._drafts[d]["fields"])
        self.assertEqual("900", self.core.retrieve(self.owner, r)["fields"]["amount_raw"])

    def test_028_uncertain_transcript_rejected(self):
        self.rejected("پرداخت شد یا قیمت شد 900 تومان")

    def test_029_conflicting_source_rejected(self):
        self.rejected("واریز 100 تومان ولی دریافت نشد")

    def test_030_private_alias_not_disclosed_to_other_user(self):
        r = self.commit("رابطه: نام مستعار خصوصی نمونه")
        other = Scope("synthetic-bot", "synthetic", "other", "private-chat")
        with self.assertRaises(PermissionError): self.core.retrieve(other, r)
        self.assertEqual("empty", self.core.search(other, "خصوصی")["status"])

    def test_031_two_drafts_make_yes_ambiguous(self):
        a = self.draft("دریافت 100 ریال فروش")
        self.draft("یادداشت: نمونه دوم")
        with self.assertRaises(ValueError): self.core.confirm(self.owner, a, "آره")
        self.assertEqual({}, self.core._records)

    def test_032_confirmation_retry_same_record(self):
        d = self.draft("دریافت 100 ریال فروش")
        first = self.core.confirm(self.owner, d, "تأیید")
        self.assertEqual(first, self.core.confirm(self.owner, d, "تأیید"))
        self.assertEqual(1, self.report()["count"])

    def test_033_outbound_privacy_change_not_supported(self):
        d = self.draft("یادآوری: نمونه خصوصی")
        self.core.clarify(self.owner, d, "بی‌زمان")
        r = self.core.confirm(self.owner, d, "تأیید")
        with self.assertRaises(ValueError): self.core.propose_correction(self.owner, r, delivery="detailed")
        self.assertEqual("pull-only", self.core.retrieve(self.owner, r)["fields"]["delivery"])

    def test_034_ambiguous_calendar_does_not_resolve(self):
        d = self.draft("یادآوری: آخر ماه")
        with self.assertRaises(ValueError): self.core.clarify(self.owner, d, "آخر ماه")
        with self.assertRaises(ValueError): self.core.confirm(self.owner, d, "تأیید")

    def test_035_time_does_not_complete_task(self):
        r = self.commit("کار: تحویل نمونه")
        self.time += timedelta(days=10)
        self.assertEqual("open", self.core.retrieve(self.owner, r)["fields"]["status"])

    def test_036_multiple_results_do_not_disclose_bodies(self):
        self.commit("یادداشت: پروژه نمونه الف راز")
        self.commit("یادداشت: پروژه نمونه ب راز")
        result = self.core.search(self.owner, "پروژه نمونه")
        self.assertEqual("choose", result["status"])
        self.assertEqual(2, len(result["ids"]))
        self.assertNotIn("راز", json.dumps(result, ensure_ascii=False))

    def test_037_sales_has_unknown_exclusion_and_refund_boundary(self):
        self.commit()
        self.commit("دریافت 600 تومان نامشخص")
        self.commit("پرداخت 300 تومان سایر بابت مرجوعی")
        self.assertEqual((5000, 1, 1), (self.report()["total_rial"], self.report()["count"], self.report()["unknown_excluded"]))

    def test_038_ambiguous_correction_target_unavailable(self):
        self.commit()
        with self.assertRaises(PermissionError): self.core.propose_correction(self.owner, "اون یکی", amount_raw="200")

    def test_039_linked_reminder_requires_own_delete(self):
        r = self.commit()
        d = self.draft("یادآوری: پیگیری نمونه")
        self.core.clarify(self.owner, d, "بی‌زمان")
        self.core.link_reminder(self.owner, d, r)
        reminder = self.core.confirm(self.owner, d, "تأیید")
        deletion = self.core.propose_delete(self.owner, r)
        self.assertEqual([reminder], self.core.preview(self.owner, deletion)["linked_reminder_ids"])
        self.core.confirm(self.owner, deletion, "تأیید حذف")
        self.assertEqual(reminder, self.core.retrieve(self.owner, reminder)["id"])

    def test_040_cancel_cannot_delete_confirmed_payment(self):
        d = self.draft("دریافت 100 ریال فروش")
        r = self.core.confirm(self.owner, d, "تأیید")
        with self.assertRaises(ValueError): self.core.cancel(self.owner, d)
        self.assertEqual(r, self.core.retrieve(self.owner, r)["id"])

    def test_041_payment_does_not_close_task(self):
        r = self.commit("کار: تحویل نمونه")
        self.commit()
        self.assertEqual("open", self.core.retrieve(self.owner, r)["fields"]["status"])

    def test_042_explicit_unit_wins_over_preference(self):
        self.commit("ترجیح: واحد پیشنهادی تومان")
        r = self.commit("دریافت 100 ریال فروش")
        self.assertEqual(100, self.core.retrieve(self.owner, r)["fields"]["amount_normalized"])

    def test_043_two_payments_not_concatenated(self):
        reply = self.core.receive(self.owner, "compound", "دریافت 100 ریال فروش؛ دریافت 200 ریال فروش")
        self.assertEqual(2, len(reply["draft_ids"]))
        for d in reply["draft_ids"]: self.core.confirm(self.owner, d, "تأیید")
        self.assertEqual(300, self.report()["total_rial"])

    def test_044_compound_objects_independent_confirmation(self):
        reply = self.core.receive(self.owner, "compound", "دریافت 100 ریال فروش؛ یادداشت: نمونه؛ یادآوری: پیگیری")
        a, b, c = reply["draft_ids"]
        self.core.confirm(self.owner, a, "تأیید")
        self.assertEqual(1, len(self.core._records))
        self.core.confirm(self.owner, b, "تأیید")
        self.assertEqual(2, len(self.core._records))
        with self.assertRaises(ValueError): self.core.confirm(self.owner, c, "تأیید")

    def test_045_private_reminder_list_hides_title(self):
        d = self.draft("یادآوری: راز ساختگی 987654")
        self.core.clarify(self.owner, d, "بی‌زمان")
        self.core.confirm(self.owner, d, "تأیید")
        self.assertNotIn("987654", json.dumps(self.core.reminders(self.owner)))

    def test_046_event_time_distinct_from_receipt_order(self):
        self.commit("دریافت 100 ریال فروش تاریخ 2026-09-04")
        self.commit("دریافت 200 ریال فروش تاریخ 2026-09-01")
        self.assertEqual(200, self.core.sales(self.owner, "2026-09-01", "2026-09-01")["total_rial"])

    def test_047_invoice_and_customer_send_are_off_scope(self):
        self.rejected("فاکتور بساز و به مشتری پیام بفرست")

    def test_048_unresolved_reference_not_interpreted_as_amount(self):
        self.rejected("همان سه را ثبت کن")

    def test_049_retention_question_does_not_change_state(self):
        self.rejected("پیام من را چقدر نگه می‌داری؟")

    def test_050_bulk_delete_not_supported(self):
        self.commit()
        response = self.core.receive(self.owner, "bulk", "همه را پاک کن")
        self.assertEqual([], response["draft_ids"])
        self.assertEqual(1, self.report()["count"])

    def test_fifty_incoming_classification_vectors(self):
        for i in range(50):
            label = list(CLASSES)[i % len(CLASSES)]
            self.commit(f"دریافت {i + 1} ریال {label}")
        expected = sum(i + 1 for i in range(50) if list(CLASSES)[i % len(CLASSES)] == "فروش")
        self.assertEqual(expected, self.report()["total_rial"])
        self.assertEqual(sum(list(CLASSES)[i % len(CLASSES)] == "نامشخص" for i in range(50)), self.report()["unknown_excluded"])

    def test_fifty_unconfirmed_objects_never_write(self):
        texts = ["دریافت 100 ریال فروش", "یادداشت: نمونه", "کار: نمونه", "یادآوری: نمونه", "ترجیح: نمونه", "رابطه: نمونه"]
        for i in range(50):
            scope = Scope("b", "synthetic", str(i), "c")
            d = self.draft(texts[i % len(texts)], scope)
            with self.assertRaises(ValueError): self.core.confirm(scope, d, "")
        self.assertEqual({}, self.core._records)

    def test_twenty_duplicate_and_retry_vectors(self):
        for i in range(20):
            scope = Scope("b", "synthetic", str(i), "c")
            message = f"دریافت {i + 1} ریال فروش"
            first = self.core.receive(scope, "m", message)
            self.assertEqual(first["draft_ids"], self.core.receive(scope, "m", message)["draft_ids"])
            d = first["draft_ids"][0]
            r = self.core.confirm(scope, d, "تأیید")
            self.assertEqual(r, self.core.confirm(scope, d, "تأیید"))
            other = self.core.receive(scope, "m2", message)["draft_ids"][0]
            with self.assertRaises(ValueError): self.core.confirm(scope, other, "تأیید")
            self.core.resolve_duplicate(scope, other, "تکراری")
        self.assertEqual(20, len(self.core._records))

    def test_twenty_correction_and_deletion_vectors(self):
        for i in range(20):
            scope = Scope("b", "synthetic", str(i), "c")
            r = self.commit(f"دریافت {i + 1} ریال فروش", scope)
            c = self.core.propose_correction(scope, r, amount_raw="999")
            replacement = self.core.confirm(scope, c, "تأیید اصلاح")
            deletion = self.core.propose_delete(scope, replacement)
            with self.assertRaises(ValueError): self.core.confirm(scope, deletion, "تأیید")
            self.core.confirm(scope, deletion, "تأیید حذف")
            self.assertEqual(replacement, self.core.confirm(scope, deletion, "تأیید حذف"))
            for ident in (r, replacement):
                with self.assertRaises(PermissionError): self.core.retrieve(scope, ident)
        self.assertEqual({}, self.core._records)
        self.assertTrue(all(not d["fields"] and d["source"] is None for d in self.core._drafts.values()))

    def test_tombstone_content_suppression_expires_at_thirty_days(self):
        text = "دریافت 123 ریال فروش"
        r = self.commit(text)
        d = self.core.propose_delete(self.owner, r)
        self.core.confirm(self.owner, d, "تأیید حذف")
        self.assertEqual("suppressed", self.core.receive(self.owner, "new-id", text)["status"])
        self.assertEqual(1, len(self.core._tombstones))
        self.time += timedelta(days=31)
        self.assertEqual("draft", self.core.receive(self.owner, "fresh-id", text)["status"])
        self.assertEqual({}, self.core._tombstones)

    def test_bot_user_platform_conversation_isolation(self):
        r = self.commit()
        d = self.draft("یادداشت: خصوصی")
        values = list(self.owner.values())
        for i in range(4):
            other = values.copy()
            other[i] = "other"
            scope = Scope(*other)
            with self.assertRaises(PermissionError): self.core.retrieve(scope, r)
            with self.assertRaises(PermissionError): self.core.confirm(scope, d, "تأیید")
            with self.assertRaises(PermissionError): self.core.propose_delete(scope, r)
            self.assertEqual(0, self.core.sales(scope, "2026-01-01", "2026-12-31")["count"])

    def test_atomic_concurrent_confirmation(self):
        d = self.draft("دریافت 100 ریال فروش")
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _: self.core.confirm(self.owner, d, "تأیید"), range(20)))
        self.assertEqual(1, len(set(results)))
        self.assertEqual(1, self.report()["count"])

    def test_signed_adapter_tamper_expiry_and_identity_reuse(self):
        adapter = SyntheticSignedAdapter(self.core)
        payload = dict(version=1, bot_id="b", platform="synthetic", user_id="u", conversation_id="c", message_id="m", text="دریافت 100 ریال فروش", timestamp=self.time.isoformat())
        signature = adapter.sign(payload)
        self.assertEqual("draft", adapter.deliver(payload, signature)["status"])
        self.assertEqual("replayed", adapter.deliver(payload, signature)["status"])
        future = dict(payload, message_id="future", timestamp=(self.time + timedelta(seconds=31)).isoformat())
        with self.assertRaisesRegex(ValueError, "Future-dated envelope"):
            adapter.deliver(future, adapter.sign(future))
        tampered = dict(payload, user_id="other")
        with self.assertRaises(PermissionError): adapter.deliver(tampered, signature)
        tampered = dict(payload, text="دریافت 999 ریال فروش")
        with self.assertRaises(ValueError): adapter.deliver(tampered, adapter.sign(tampered))
        self.time += timedelta(minutes=6)
        with self.assertRaises(ValueError): adapter.deliver(payload, signature)

    def test_no_body_in_audit_and_external_mutation_isolated(self):
        r = self.commit("یادداشت: SYNTHETIC_PRIVATE_SENTINEL")
        record = self.core.retrieve(self.owner, r)
        record["fields"]["title"] = "tampered"
        self.assertEqual("SYNTHETIC_PRIVATE_SENTINEL", self.core.retrieve(self.owner, r)["fields"]["title"])
        self.assertNotIn("SYNTHETIC_PRIVATE_SENTINEL", json.dumps(self.core.audit))

    def test_invalid_amounts_and_unsplit_compound_fail_closed(self):
        for text in ("دریافت -100 تومان", "دریافت 0 تومان", "دریافت 1.5 تومان", "دریافت 1,23 تومان", "دریافت 100 تومان و دریافت 200 تومان", "دریافت 100 ریال فروش؛ یک لطیفه بگو", "دریافت 100 ریال فروش یا انتقال", "دریافت 100 تومان یعنی ریال", "دریافت 100 ریال فروش و یادداشت: نمونه", "دریافت 100 ریال فروش 2026-09-01 2026-09-02"):
            with self.subTest(text=text): self.rejected(text)

    def test_draft_revision_remains_unconfirmed_and_shows_conversion(self):
        d = self.draft("دریافت 100 ریال فروش")
        preview = self.core.revise_draft(self.owner, d, amount_raw="۲۰۰", unit_raw="تومان")
        self.assertEqual(2000, preview["fields"]["amount_normalized"])
        self.assertEqual({}, self.core._records)
        r = self.core.confirm(self.owner, d, "تأیید")
        self.assertEqual(2000, self.core.retrieve(self.owner, r)["fields"]["amount_normalized"])
        with self.assertRaises(ValueError): self.core.revise_draft(self.owner, d, amount_raw="300")

    def test_single_unambiguous_yes_is_accepted(self):
        d = self.draft("دریافت 100 ریال فروش")
        first = self.core.confirm(self.owner, d, "بله")
        self.assertEqual(first, self.core.confirm(self.owner, d, "بله"))
        self.assertEqual(1, self.report()["count"])

    def test_stale_corrections_do_not_fork_history(self):
        r = self.commit()
        a = self.core.propose_correction(self.owner, r, amount_raw="100")
        b = self.core.propose_correction(self.owner, r, amount_raw="200")
        self.core.confirm(self.owner, a, "تأیید اصلاح")
        with self.assertRaises(ValueError): self.core.confirm(self.owner, b, "تأیید اصلاح")
        self.assertEqual(1, self.report()["count"])


if __name__ == "__main__":
    unittest.main()
