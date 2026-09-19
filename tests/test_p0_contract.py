import unittest

from src.ledger import ACKNOWLEDGEMENT, SyntheticLedger


class P0ContractTests(unittest.TestCase):
    def test_fifty_synthetic_message_to_record_to_retrieval_flows(self):
        ledger = SyntheticLedger()
        for number in range(1, 51):
            user_id = f"synthetic-user-{number:02d}"
            message = f"دریافت {number}000 از مشتری ساختگی {number}"
            acknowledgement, draft, question = ledger.receive(user_id, message)
            self.assertEqual(ACKNOWLEDGEMENT, acknowledgement)
            self.assertIn("ریال یا تومان", question)
            preview = ledger.answer_unit(user_id, draft.draft_id, "تومان")
            self.assertIn("برای ثبت بنویسید: تأیید", preview)
            record = ledger.confirm(user_id, draft.draft_id, "تأیید")
            self.assertIsNone(draft.source_body)
            self.assertEqual("unknown", record.classification)
            self.assertEqual(record, ledger.retrieve(user_id, record.record_id))

    def test_confirmation_is_required_and_repeat_is_idempotent(self):
        ledger = SyntheticLedger()
        _, draft, _ = ledger.receive("synthetic-user", "دریافت 700000 از شخص ساختگی")
        with self.assertRaises(ValueError):
            ledger.confirm("synthetic-user", draft.draft_id, "بله")
        ledger.answer_unit("synthetic-user", draft.draft_id, "ریال")
        first = ledger.confirm("synthetic-user", draft.draft_id, "تأیید")
        second = ledger.confirm("synthetic-user", draft.draft_id, "تأیید")
        self.assertEqual(first.record_id, second.record_id)

    def test_other_user_cannot_retrieve_or_confirm(self):
        ledger = SyntheticLedger()
        _, draft, _ = ledger.receive("owner", "دریافت 800000 از شخص ساختگی")
        with self.assertRaises(PermissionError):
            ledger.answer_unit("other-user", draft.draft_id, "تومان")
        ledger.answer_unit("owner", draft.draft_id, "تومان")
        record = ledger.confirm("owner", draft.draft_id, "تأیید")
        with self.assertRaises(PermissionError):
            ledger.retrieve("other-user", record.record_id)

    def test_cancel_draft_flow(self):
        ledger = SyntheticLedger()
        _, draft, _ = ledger.receive("cancel-user", "دریافت 250000 از شخص الف")
        # Other user cannot cancel
        with self.assertRaises(PermissionError):
            ledger.cancel("other-user", draft.draft_id)
        msg = ledger.cancel("cancel-user", draft.draft_id)
        self.assertIn("لغو شد", msg)
        self.assertEqual(draft.state, "cancelled")
        self.assertIsNone(draft.source_body)
        # Idempotent cancellation check
        repeat_msg = ledger.cancel("cancel-user", draft.draft_id)
        self.assertIn("قبلاً لغو شده", repeat_msg)
        # Cannot confirm a cancelled draft
        with self.assertRaises(ValueError):
            ledger.confirm("cancel-user", draft.draft_id, "تأیید")
        # Missing draft or record raises KeyError
        with self.assertRaises(KeyError):
            ledger.cancel("cancel-user", "non-existent-draft-id")
        with self.assertRaises(KeyError):
            ledger.retrieve("cancel-user", "non-existent-record-id")

    def test_list_records_and_isolation(self):
        ledger = SyntheticLedger()
        self.assertEqual([], ledger.list_records("user-a"))
        _, d1, _ = ledger.receive("user-a", "دریافت 100000 تومان")
        ledger.answer_unit("user-a", d1.draft_id, "تومان")
        ledger.confirm("user-a", d1.draft_id, "تأیید")

        _, d2, _ = ledger.receive("user-b", "دریافت 200000 ریال")
        ledger.answer_unit("user-b", d2.draft_id, "ریال")
        ledger.confirm("user-b", d2.draft_id, "تأیید")

        user_a_records = ledger.list_records("user-a")
        user_b_records = ledger.list_records("user-b")
        self.assertEqual(1, len(user_a_records))
        self.assertEqual(1, len(user_b_records))
        self.assertEqual("user-a", user_a_records[0].user_id)
        self.assertEqual("user-b", user_b_records[0].user_id)

    def test_direction_detection_and_summary_totals(self):
        ledger = SyntheticLedger()
        # Test variz is incoming
        _, d1, _ = ledger.receive("summary-user", "واریز 300000 تومان")
        self.assertEqual("incoming", d1.direction)
        ledger.answer_unit("summary-user", d1.draft_id, "تومان")
        ledger.confirm("summary-user", d1.draft_id, "تأیید")

        # Test pardakht is outgoing
        _, d2, _ = ledger.receive("summary-user", "پرداخت 50000 تومان برای خرید تجهیزات")
        self.assertEqual("outgoing", d2.direction)
        ledger.answer_unit("summary-user", d2.draft_id, "تومان")
        ledger.confirm("summary-user", d2.draft_id, "تأیید")

        # Test rial incoming
        _, d3, _ = ledger.receive("summary-user", "دریافت 1000000 ریال")
        ledger.answer_unit("summary-user", d3.draft_id, "ریال")
        ledger.confirm("summary-user", d3.draft_id, "تأیید")

        summary = ledger.summary("summary-user")
        self.assertEqual("summary-user", summary["user_id"])
        self.assertEqual(3, summary["record_count"])
        self.assertEqual(300000, summary["totals"]["تومان"]["incoming"])
        self.assertEqual(50000, summary["totals"]["تومان"]["outgoing"])
        self.assertEqual(250000, summary["totals"]["تومان"]["net"])
        self.assertEqual("۲۵۰٬۰۰۰ تومان", summary["totals"]["تومان"]["formatted_net"])
        self.assertEqual(1000000, summary["totals"]["ریال"]["incoming"])
        self.assertEqual(0, summary["totals"]["ریال"]["outgoing"])
        self.assertEqual(1000000, summary["totals"]["ریال"]["net"])
        self.assertEqual("۱٬۰۰۰٬۰۰۰ ریال", summary["totals"]["ریال"]["formatted_net"])

        # Isolation: another user has empty summary
        other_summary = ledger.summary("other-user")
        self.assertEqual(0, other_summary["record_count"])
        self.assertEqual(0, other_summary["totals"]["تومان"]["incoming"])
        self.assertEqual(0, other_summary["totals"]["تومان"]["net"])
        self.assertEqual("۰ تومان", other_summary["totals"]["تومان"]["formatted_net"])

    def test_persian_digits_extraction_and_unaccented_confirm(self):
        ledger = SyntheticLedger()
        # Message with Persian digits: دریافت ۵۰۰۰۰ تومان
        ack, draft, question = ledger.receive("user-fa", "دریافت ۵۰۰۰۰ تومان")
        self.assertEqual("50000", draft.amount_raw)
        self.assertIn("50000", question)

        # Answer unit with surrounding spaces
        reply = ledger.answer_unit("user-fa", draft.draft_id, "  تومان  ")
        self.assertIn("50000 تومان", reply)

        # Confirm using standard Persian keyboard spelling 'تایید' (no hamza)
        record = ledger.confirm("user-fa", draft.draft_id, "تایید")
        self.assertEqual("50000", record.amount_raw)
        self.assertEqual("تومان", record.unit_raw)
        self.assertEqual("incoming", record.direction)


if __name__ == "__main__":
    unittest.main()
