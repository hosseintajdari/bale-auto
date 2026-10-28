# مسیر پروداکشن bale-auto — سند ثبت (Production Path)

- **برنچ:** `gorgg/production-path`
- **بیس:** `origin/main` در کامیت `8cc741ac87dd7e27eb094de514624363042032ba` (ادغام PR #56، مورخ 2026-10-26)
- **تاریخ ثبت:** 2026-10-28
- **مبنای تصمیم:** اعلام مالک (2026-10-28): محصول آماده‌ی بازار است و بازاریاب دارد؛ گلوگاه، وضعیت گیت بود. این سند همان وضعیت گیت را صورت‌برداری، جمع‌بندی و قابل دیپلوی می‌کند.
- **دامنه‌ی این برنچ:** فقط همین برنچ ساخته و پوش شده است. `main` و همه‌ی برنچ‌های موجود دست‌نخورده‌اند؛ هیچ مرج، فورس‌پوش، حذف برنچ یا بازنویسی تاریخچه‌ای انجام نشده است.

---

## ۱) origin/main الان چه دارد (صورت‌برداری در سطح فایل)

محصول زنده همین حالا روی `main` است:

| قطعه | نقش |
|---|---|
| `src/bale_bot.py` | بات زنده‌ی بله — Long Polling روی `tapi.bale.ai`، کیبورد اینلاین، ارسال اختیاری Shadow Trace به Bale-Panel (پیش‌فرض خاموش) |
| `src/bazaar_parser.py` | موتور NLP بازار فارسی — اصطلاحات بازاری، اعداد گفتاری/نوشتاری، تشخیص جهت و واحد |
| `src/conversation.py` | ذخیره‌سازی SQLite و مدیریت نشست (`ConversationStore` + `ConversationService`) |
| `src/p0_core.py` | هسته‌ی state machine و قواعد راستی‌آزمایی تراکنش |
| `src/ledger.py` | پروتوتایپ حافظه‌ای P0 (`SyntheticLedger`) — فقط `demo_p0.py` و `tests/test_p0_contract.py` از آن استفاده می‌کنند؛ بات زنده به آن وابسته نیست |
| `tests/` (۵ فایل) | پذیرش، قرارداد، مکالمه، شبیه‌سازی پرسونا، کارگر بازار |
| `run_p0_review.py` | رانر رسمی بررسی (همان که CI اجرا می‌کند) |

شواهد وضعیت زنده روی سرور مالک (2026-10-28): در کلون اصلی `~/bale-auto` فایل‌های `.env`/`.env.local` و `data/ledger.db` (ساخته‌شده 2026-09-22) وجود دارد، اما در لحظه‌ی بررسی هیچ پروسه‌ی `bale_bot` و هیچ یونیت systemd برای bale-auto فعال نبود (برخلاف `bale-panel.service` و `bale-salon.service`). یعنی بات قبلاً دستی اجرا شده و مسیر دیپلوی ثبت‌شده نداشته است — یکی از خلأهایی که این برنچ می‌بندد.

## ۲) از هر برنچ دقیقاً چه لازم بود — حکم برنچ‌به‌برنچ

روش بررسی: `fetch --prune`، سپس برای هر برنچ `merge-base`، شمارش `rev-list --left-right --count origin/main...branch`، آزمون `merge-base --is-ancestor` و در مورد تنها کامیت یکتا، `git cherry` و چری‌پیک آزمایشی واقعی.

### الف) برنچ‌های مرتبط که کامل در main هستند (۰ کامیت یکتا — چیزی برای آوردن نبود)

همه‌ی این‌ها جدّ `origin/main` هستند و از مسیر PR ادغام شده‌اند:

| برنچ | تیپ | مسیر ورود به main |
|---|---|---|
| `codex/fix-issue-22` | `fad1158` | PR #43 |
| `codex/fix-issue-39` | `24c557a` | PR #44 |
| `codex/fix-issue-37` | `69ab66a` | PR #45 |
| `codex/fix-issue-36` | `8e7de6d` | PR #46 |
| `codex/fix-issue-34` | `036e03c` | PR #47 |
| `codex/fix-issue-33` | `b671d87` | PR #48 |
| `codex/fix-parser-boundaries` | `36cce58` | PR #49 |
| `codex/fix-issue-30` | `7b4f55d` | PR #50 |
| `codex/fix-issue-40` | `3f7b5d1` | PR #51 |
| `codex/fix-issue-28` | `881fce6` | PR #52 |
| `codex/fix-issue-23` | `08ce179` | PR #53 |
| `codex/fix-parser-amount-phrases` | `87ef8c7` | PR #54 |
| `codex/fix-negated-transfer-24` | `603e667` | PR #55 |
| `codex/publication-status-41` | `11a5df1` | PR #56 |
| `docs/bilingual-readme` | `3514c3d` | PR #42 |
| `feat/perf-trace-and-persian-normalization` | `77b8bdb` | PR #18 |
| `docs/embednet-recovery-alignment` | `f3c497b` | PR #14 |

### ب) تنها برنچ مرتبط با کامیت یکتا: `chore/canonical-p0-cleanup` — آورده نشد، با دلیل

- تیپ `22258ad`، یک کامیت یکتا: «canonicalize P0 implementation» — حذف `src/ledger.py`، `demo_p0.py`، `tests/test_p0_contract.py` و `p0_synthetic_flow.js` و اعلام `src/p0_core.py` به‌عنوان تنها پیاده‌سازی.
- **PR متناظرش (#15) در 2026-09-08 بسته و ادغام‌نشده است** — یعنی در فرایند خود پروژه کنار گذاشته شده، نه این‌که جا مانده باشد.
- چری‌پیک آزمایشی روی این برنچ (2026-10-28) انجام و **abort** شد؛ شواهد: کانفلیکت محتوایی در `README.md` و کانفلیکت modify/delete روی `src/ledger.py` و `tests/test_p0_contract.py` (در آن کامیت حذف شده‌اند، روی main تغییر کرده‌اند).
- چرا اعمالش امروز غلط است: `src/ledger.py` بعد از آن کامیت روی main رشد کرده (۱۲۰ → ۱۷۵ خط، از جمله `format_persian_currency`) و تست‌های قراردادش جزئی از سوئیت فعلی ۱۰۳ تستیِ سبز است؛ متن HANDOFF داخل آن کامیت وضعیت سپتامبر (چک‌اوت `9886f1e`) را توصیف می‌کند و اسناد امروز را پس‌رفت می‌دهد.
- نیت آن کامیت (حذف ماشین موازی) امروز مصداق زنده‌اش جای دیگری است: ایشوی باز **#35** — `ConversationService` در `bale_bot.py:166` ساخته می‌شود ولی `handle()` آن هرگز صدا زده نمی‌شود و بات ماشین وضعیت خودش را دارد. حل آن تصمیم کدیِ جداست و در این برنچ دست نخورده تا رفتار ران‌تایم بدون دستور مشخص مالک تغییر نکند.

### ج) برنچ‌های legacy با تاریخچه‌ی نامرتبط (OpenClaw PoC) — هیچ‌چیز آورده نشد، با دلیل

زنجیره‌ی واحد: `feat/poc-foundation` (`61a73b6`) ← `codex/openclaw-poc-verification` (`18e9f7a`) ← `codex/finalize-openclaw-handoff` (`7426cb4`) ← `codex/record-capacity-cleanup` (`c2a1e0d`) ← `archive/pre-ledger-main` (`8bc8ff3`، تیپ زنجیره). هیچ جد مشترکی با main ندارند.

محتوای یکتایشان (۲۲ فایل، در سطح `ls-tree`): `deploy/openclaw/compose.yaml` و `.env.example` مخصوص OpenClaw، `scripts/health_check.py`، `scripts/scan_secrets.py`، `scripts/validate_policy.py`، `policies/intents.json` (مدل default-deny مخصوص PoC)، ران‌بوک‌های `BOOTSTRAP`/`OPENCLAW_POC`/`SERVER_PREPARATION_CHECKLIST` و اسناد طراحی PoC.

دلیل نیاوردن، حدس نیست — قانون خود ریپوست: `START_HERE.md` روی main صریح می‌گوید این بسته «عمداً مستقل از OpenClaw PoC تاریخی bale-auto» است و «از PoC تاریخی OpenClaw به‌عنوان بخشی از این محصول استفاده، کپی، تغییر یا دیپلوی نکن». این پنج برنچ به‌عنوان legacy حفظ می‌مانند (مطابق تریاژ ممیزی 2026-10-28: unrelated-legacy-retain) و حذفشان دستور جدا می‌خواهد.

## ۳) برای پروداکشن چه کم بود و این برنچ چه اضافه می‌کند

| خلأ روی main | رفع در این برنچ |
|---|---|
| `.env.example` وجود نداشت، با این‌که `.gitignore` صریحاً برایش استثنا گذاشته (`!.env.example`) و README راه‌اندازی را به `.env` ارجاع می‌دهد | `.env.example` جدید — هر ۹ متغیر واقعاً خوانده‌شده در کد (`BALE_BOT_TOKEN`، `BALE_API_BASE`، `LEDGER_DB_PATH`، `ENABLE_PANEL_EMIT`، `DISABLE_PANEL_EMIT`، `PANEL_BASE_URL`، `PANEL_API_SECRET`، `PANEL_OPERATOR_TOKEN`، `PANEL_SHADOW_TRACE_URL`) + `BALE_BOT_USERNAME` با توضیح این‌که در `.env` زنده‌ی سرور هست ولی کد فعلی آن را نمی‌خواند. همه‌ی مقادیر خالی‌اند؛ هیچ سکرتی وارد گیت نشده است |
| هیچ یونیت سرویس یا مسیر دیپلوی ثبت‌شده‌ای برای بات نبود (اجرای دستی سپتامبر) | `deploy/bale-auto.service.example` — قالب systemd؛ نصبش قدم اپراتوریِ جدا در بخش ۵ است و خودبه‌خود نصب نشده |
| Status در README محصول را «پروتوتایپ، نه آماده‌ی پروداکشن» معرفی می‌کرد و با اعلام مالک نمی‌خواند | بخش Status در `README.md` به «Production-path baseline» روی همین برنچ به‌روز شد، با ارجاع به این سند و ذکر شفاف ایشوهای باز |
| سند واحدی برای مسیر پروداکشن نبود | همین `PRODUCTION-PATH.md` |

تغییر کدی در رفتار بات در این برنچ **انجام نشده است** — عمداً: گلوگاه اعلام‌شده گیت بود، نه کد.

## ۴) شواهد تست (اجرا روی همین سرور، Python 3.12.3)

بیس‌لاین روی `origin/main` و سپس روی همین برنچ، هر دو در کلون تازه‌ی `~/bale-auto-prodpath`:

```text
python3 -m unittest discover -s tests   → Ran 103 tests — OK (exit 0)
python3 run_p0_review.py                → tests_run=103, failures=0, errors=0, skipped=0, success=true
                                          PASS: synthetic demonstration and 50-row source-scenario mapping generated.
python3 -m py_compile src/*.py tests/*.py run_p0_review.py demo_p0.py → OK
```

- بیس‌لاین main: اجرا در `2026-10-28T02:36:37Z` — ۱۰۳/۱۰۳ سبز.
- روی برنچ (بعد از اضافه‌شدن فایل‌های بخش ۳): اجرا در `2026-10-28T02:37:56Z` — ۱۰۳/۱۰۳ سبز، بدون تغییر نسبت به بیس‌لاین.
- صداقت دامنه: `live_channel_tested=false` — تست‌ها سینتتیک‌اند و اتصال زنده به API بله در این ثبت آزموده نشده است؛ اجرای زنده قبلاً روی سرور مالک اتفاق افتاده (لاگ و `ledger.db` مورخ 2026-09-22).

## ۵) قدم‌های دیپلوی (اپراتوری — اجرای واقعی روی سرور دستور جدا می‌خواهد)

1. روی هاست دیپلوی: `git fetch origin && git checkout gorgg/production-path` (یا کلون تازه از همین برنچ).
2. `cp .env.example .env` و پر کردن فقط مقادیر واقعی روی همان هاست؛ `ENABLE_PANEL_EMIT` را `0` نگه دار مگر اپراتور آگاهانه انتشار متن خام پیام به پنل را بپذیرد.
3. مسیر دیتابیس را مشخص کن: `LEDGER_DB_PATH` (پیش‌فرض کد: `/home/admin/bale-auto/data/ledger.db`). از دیتابیس قبلی بک‌آپ بگیر قبل از هر جابه‌جایی.
4. دروازه‌ی تست: `python3 -m unittest discover -s tests` و `python3 run_p0_review.py` — هر دو باید سبز باشند (۱۰۳ تست).
5. نصب سرویس: مقادیر `User`/`WorkingDirectory`/`EnvironmentFile` در `deploy/bale-auto.service.example` را با هاست تطبیق بده، بعد `sudo cp deploy/bale-auto.service.example /etc/systemd/system/bale-auto.service && sudo systemctl daemon-reload && sudo systemctl enable --now bale-auto.service`.
6. راستی‌آزمایی: `systemctl status bale-auto` و `journalctl -u bale-auto -f` — بات باید Polling را شروع کند؛ هیچ پورت ورودی‌ای باز نمی‌شود. یک پیام آزمایشی با داده‌ی سینتتیک بفرست و ثبت با تأیید صریح را چک کن.
7. بازگشت (Rollback): `systemctl stop bale-auto` و برگرداندن چک‌اوت به `origin/main` (`8cc741a`)؛ دیتابیس دست‌نخورده می‌ماند چون این برنچ هیچ مهاجرت اسکیمایی ندارد.

## ۶) چه ماند و چرا — تصمیم‌های باز مالک

- **#35** — یکپارچه‌سازی ماشین مکالمه (`ConversationService` مرده در بات): تصمیم و تغییر کدی جدا.
- **#38** — تکمیل ردّ حسابرسی پیام‌ها در `handle_message`: قبل از داده‌ی واقعی کاربران باید بسته شود.
- **#41** — چک‌لیست عمومی‌شدن ریپو: این ریپو private است و این برنچ هم private می‌ماند؛ عمومی‌کردن تصمیم جداست.
- **حذف یا آرشیو برنچ‌های legacy و `chore/canonical-p0-cleanup`:** هیچ‌کدام حذف نشده‌اند؛ حذف برنچ دستور جدا می‌خواهد.
- **مرج این برنچ به `main`:** انجام نشده و دستور جدا می‌خواهد؛ مسیر طبیعی آن PR از `gorgg/production-path` به `main` است.
