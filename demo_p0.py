"""Run the required P0 mocked flow locally."""

from src.ledger import SyntheticLedger


def main() -> None:
    ledger = SyntheticLedger()
    user_id = "synthetic-user-01"
    acknowledgement, draft, question = ledger.receive(
        user_id, "دریافت 500000 از مشتری آزمایشی"
    )
    print(acknowledgement)
    print(question)
    print(ledger.answer_unit(user_id, draft.draft_id, "تومان"))
    record = ledger.confirm(user_id, draft.draft_id, "تأیید")
    print(f"ثبت شد: {record.record_id}")
    retrieved = ledger.retrieve(user_id, record.record_id)
    print(f"بازیابی: {retrieved.amount_raw} {retrieved.unit_raw}; {retrieved.classification}")


if __name__ == "__main__":
    main()
