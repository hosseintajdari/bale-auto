"""Run synthetic tests and write review artifacts without printing message bodies."""
from datetime import datetime, timezone
from io import StringIO
import json
from pathlib import Path
import re
import unittest

from src.p0_core import P0Ledger, Scope, SyntheticSignedAdapter


def demonstration():
    now = datetime(2026, 9, 5, 12, tzinfo=timezone.utc)
    core = P0Ledger(lambda: now)
    scope = Scope("synthetic-bot", "synthetic", "synthetic-owner", "private-chat")
    adapter = SyntheticSignedAdapter(core)
    payload = dict(version=1, bot_id=scope.bot_id, platform=scope.platform,
                   user_id=scope.user_id, conversation_id=scope.conversation_id,
                   message_id="synthetic-message-001", text="دریافت ۵۰۰٬۰۰۰ از مشتری ساختگی ۲",
                   timestamp=now.isoformat())
    response = adapter.deliver(payload, adapter.sign(payload))
    d = response["draft_ids"][0]
    unit_question = core.preview(scope, d)["question"]
    next_preview = core.clarify(scope, d, "تومان")
    preview = core.clarify(scope, d, "نامشخص")
    assert not core._records
    r = core.confirm(scope, d, "تأیید")
    assert core.confirm(scope, d, "تأیید") == r
    assert core.retrieve(scope, r)["fields"]["amount_normalized"] == 5000000
    assert core._drafts[d]["source"] is None
    first_report = core.sales(scope, "2026-09-01", "2026-09-30")
    assert first_report["total_rial"] == 0 and first_report["unknown_excluded"] == 1
    correction = core.propose_correction(scope, r, classification="sale")
    assert core.sales(scope, "2026-09-01", "2026-09-30")["count"] == 0
    replacement = core.confirm(scope, correction, "تأیید اصلاح")
    corrected_report = core.sales(scope, "2026-09-01", "2026-09-30")
    assert corrected_report["total_rial"] == 5000000
    deletion = core.propose_delete(scope, replacement)
    core.confirm(scope, deletion, "تأیید حذف")
    assert not core._records
    assert core.receive(scope, "synthetic-retry", payload["text"])["status"] == "suppressed"
    return f"""# نمونهٔ اجرای P0 — فقط دادهٔ ساختگی

این متن از اجرای واقعی هستهٔ ساختگی و assertionهای آن تولید شده است.
نمایشگر چت زنده، اتصال LangBot یا آزمون مدل زبانی نیست.

1. کاربر: «{payload['text']}»
2. بات: «{response['ack']}»
3. بات: «{unit_question}»
4. کاربر: «تومان»
5. بات: «{next_preview['question']}»
6. کاربر: «نامشخص»
7. پیش‌نویس: دریافت {preview['fields']['amount_raw']} تومان؛ معادل ۵٬۰۰۰٬۰۰۰ ریال؛ دسته نامشخص. هنوز رکوردی ثبت نشده است.
8. کاربر: «تأیید»؛ یک رکورد ایجاد شد و متن خام از وضعیت داخلی پاک شد.
9. تکرار «تأیید»: همان شناسه بازگردانده شد؛ ثبت دوم ایجاد نشد.
10. گزارش سپتامبر: فروش صفر؛ یک دریافت نامشخص از فروش کنار گذاشته شد.
11. درخواست اصلاح دسته به فروش: فقط پیش‌نویس اصلاح ایجاد شد و گزارش تغییر نکرد.
12. کاربر: «تأیید اصلاح»؛ رکورد جایگزین با پیوند به قبلی ایجاد شد. فروش تأییدشده ۵٬۰۰۰٬۰۰۰ ریال شد.
13. درخواست حذف: حذف دائمی همین رکورد نمایش داده شد؛ «تأیید حذف» باعث حذف رکورد و نسخهٔ قبلی شد.
14. ارسال مجدد همان متن پس از حذف: نشانگر بدون محتوا جلوی ثبت دوباره را گرفت.

نتیجه: همهٔ assertionهای این نمایش پاس شدند. اجرای برنامه شبکه و ارسال واقعی ندارد.
"""


def main():
    root = Path(__file__).resolve().parent
    out = root / "work" / "p0_evidence"
    out.mkdir(parents=True, exist_ok=True)
    suite = unittest.defaultTestLoader.discover(str(root / "tests"))
    stream = StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    (out / "tests.log").write_text(stream.getvalue(), encoding="utf-8")
    summary = dict(timestamp_utc=datetime.now(timezone.utc).isoformat(),
                   tests_run=result.testsRun, failures=len(result.failures), errors=len(result.errors),
                   skipped=len(result.skipped), success=result.wasSuccessful(),
                   synthetic_only=True, live_channel_tested=False, persistent_storage_tested=True)
    (out / "test_results.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    if not result.wasSuccessful():
        print(stream.getvalue())
        raise SystemExit(1)
    (out / "P0_DEMO_FA.md").write_text(demonstration(), encoding="utf-8")
    test_source = (root / "tests" / "test_p0_acceptance.py").read_text(encoding="utf-8")
    methods = re.findall(r"def (test_(\d{3})_[a-z_]+)\(self\)", test_source)
    assert {int(number) for _, number in methods} == set(range(1, 51))
    rows = ["# P0 source-scenario coverage", "", "Each row verifies one bounded invariant distilled from the corresponding existing", "design scenario. These are NOT 50 full natural-language conversations or field", "validations. Voice is represented only by a manually supplied text fallback.", "Unsupported/ambiguous inputs are rejected or require structured clarification.", "", "Sources: `CONVERSATIONAL_WORK_LEDGER_100_SCENARIOS_FA.md` (001-025) and", "`CONVERSATIONAL_WORK_LEDGER_25_HARD_SCENARIOS_FA.md` (026-050).", "", "| Scenario | Executable assertion | Scope |", "| --- | --- | --- |"]
    fallback = {5, 22, 28, 29, 33, 34, 38, 47, 48, 49, 50}
    for method, number in methods:
        rows.append(f"| {number} | `{method}` | {'Fallback / refusal boundary' if int(number) in fallback else 'Synthetic domain contract'} |")
    (out / "P0_SCENARIO_COVERAGE.md").write_text("\n".join(rows) + "\n", encoding="utf-8")
    print(json.dumps(summary))
    print("PASS: synthetic demonstration and 50-row source-scenario mapping generated.")
    print("Artifacts: work/p0_evidence/{tests.log,test_results.json,P0_DEMO_FA.md,P0_SCENARIO_COVERAGE.md}")


if __name__ == "__main__":
    main()
