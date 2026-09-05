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


if __name__ == "__main__":
    unittest.main()
