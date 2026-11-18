# طرح ارکستراسیون `bale-auto` با LangGraph

وضعیت: پیش‌نویس برای بازبینی انسانی

این سند فقط لایهٔ ارکستراسیون را مشخص می‌کند. در این مرحله هیچ وابستگی جدیدی
نصب نمی‌شود، هیچ کانال پیام‌رسانی متصل نمی‌شود و هیچ قابلیت تجاری یا پزشکی
اضافه نمی‌شود.

## تصمیم معماری

`LangGraph` فقط در لایهٔ application/orchestration قرار می‌گیرد. هستهٔ دامنه،
Policy، ثبت Intent، ابزارهای مجاز و Audit نباید به LangGraph وابسته باشند.
این جداسازی اجازه می‌دهد بعداً فریم‌ورک، مدل یا کانال پیام‌رسان عوض شود، بدون
آن‌که قواعد ایمنی و داده‌های محصول بازنویسی شوند.

```text
کانال ورودی (Bale/Telegram/HTTP)
        |
        v
Inbound Adapter -> Normalizer -> LangGraph Orchestrator
                                      |
                   +------------------+------------------+
                   |                                     |
             Domain Ports                         Registered Tools
          (Intent/Policy/Audit)                (فعلاً health_check)
                   |                                     |
                   +------------------+------------------+
                                      v
                         Outbound Adapter / Receipt
```

## گراف نسخهٔ اول

گراف اول عمداً کوچک و قابل‌ممیزی است و با PoC فعلی هماهنگ می‌ماند:

```text
START
  -> ingest
  -> normalize_input
  -> classify_intent
  -> evaluate_policy
  -> prepare_execution
  -> execute_registered_tool
  -> build_redacted_receipt
  -> persist_audit
  -> END
```

مسیرهای خطا و توقف:

```text
classify_intent --[unknown/ambiguous]--> reject_with_safe_message
evaluate_policy --[deny]---------------> reject_with_safe_message
prepare_execution --[approval needed]--> await_human_confirmation
execute_registered_tool --[timeout/error]--> record_failure
```

در وضعیت فعلی، `system.health.read` ریسک پایین دارد و نیاز به تأیید ندارد؛
بنابراین مسیر `await_human_confirmation` فعلاً استفاده نمی‌شود، اما از ابتدا
به‌عنوان یک نقطهٔ توقف صریح در قرارداد گراف تعریف می‌شود.

## وضعیت Typed پیشنهادی

وضعیت گراف باید دادهٔ قابل‌ثبت و حداقلی داشته باشد، نه تاریخچهٔ نامحدود پیام:

```python
class OrchestrationState(TypedDict, total=False):
    request_id: str
    actor_id: str
    channel: str
    raw_input: str
    normalized_input: str
    intent: str
    intent_arguments: dict[str, object]
    policy_decision: Literal["allow", "deny", "approval_required"]
    tool_name: str
    tool_result: dict[str, object]
    receipt: dict[str, object]
    audit_event: dict[str, object]
    error_code: str
```

قواعد مهم:

- متن خام فقط تا جایی نگه‌داری شود که قرارداد نگه‌داری داده اجازه می‌دهد.
- خروجی مدل مستقیماً ابزار را اجرا نمی‌کند؛ ابتدا باید به Intent ساختاریافته
  تبدیل و با Policy بررسی شود.
- `tool_name` فقط از Registry داخلی انتخاب می‌شود؛ هرگز از ورودی کاربر یا
  خروجی آزاد مدل به‌عنوان نام دستور استفاده نمی‌شود.
- `receipt` و `audit_event` باید پیش از ارسال از مسیر redaction عبور کنند.
- برای هر اجرای قابل‌تداوم، `request_id` همان شناسهٔ اتصال به checkpointer است.

## قرارداد گره‌ها

| گره | مسئولیت | مجاز به انجام | ممنوع |
|---|---|---|---|
| `ingest` | ایجاد شناسه و دریافت ورودی | ثبت متادیتای حداقلی | اجرای ابزار |
| `normalize_input` | یکسان‌سازی متن/ورودی | پاک‌سازی قالب و طول | تصمیم‌گیری تجاری |
| `classify_intent` | تبدیل ورودی به Intent محدود | فراخوانی مدل با schema | فراخوانی مستقیم ابزار |
| `evaluate_policy` | اعمال default-deny | خواندن Policy و تصمیم | تغییر Policy در زمان اجرا |
| `prepare_execution` | ساخت درخواست اجرای ثبت‌شده | اعتبارسنجی آرگومان‌ها | حدس‌زدن آرگومان حساس |
| `await_human_confirmation` | توقف برای تأیید | `interrupt()` و resume | اجرای side effect پیش از تأیید |
| `execute_registered_tool` | اجرای Adapter ثبت‌شده | اجرای `health_check` فعلی | shell آزاد یا command کاربر |
| `build_redacted_receipt` | ساخت پاسخ قابل‌نمایش | خلاصه‌سازی نتیجهٔ مجاز | افشای Secret یا دادهٔ خام |
| `persist_audit` | ثبت رویداد ممیزی | نوشتن رویداد حداقلی | ذخیرهٔ توکن/اطلاعات غیرضروری |

## مرزهای دامنه و زیرساخت

لایهٔ LangGraph فقط Portها را صدا می‌زند:

```text
IntentClassifierPort
PolicyDecisionPort
ToolRegistryPort
AuditSinkPort
ReceiptRendererPort
```

پیاده‌سازی فعلی این Portها می‌تواند از ماژول‌های استانداردپایتون استفاده کند.
LangGraph در گام بعدی یک Adapter برای همین Portها خواهد بود؛ بنابراین منطق
`validate_policy.py` و `health_check.py` در ابتدا جابه‌جا یا بازنویسی نمی‌شوند.

## ماندگاری و تأیید انسانی

برای توسعهٔ محلی می‌توان از checkpointer حافظه‌ای استفاده کرد، اما در محیط
واقعی باید checkpointer پایدار و دارای سیاست نگه‌داری داده انتخاب شود. هر
`interrupt` باید با `request_id` و یک رویداد Audit همراه باشد و resume فقط با
یک پاسخ معتبر و متعلق به همان actor انجام شود.

هیچ گرافی نباید برای تشخیص، تجویز، تغییر دارو یا تصمیم بالینی استفاده شود.
هر قابلیت سلامت آینده باید مسیر ارجاع و بازبینی انسان واجد صلاحیت داشته باشد.

## معیار پذیرش فاز ارکستراسیون

قبل از رفتن به فاز بعدی، این موارد باید تأیید شوند:

1. ورودی ناشناخته بدون فراخوانی ابزار رد می‌شود.
2. Intent ردشده یا Policy-deny هیچ side effect ندارد.
3. فقط Executor ثبت‌شده قابل فراخوانی است.
4. خروجی سلامت با قرارداد فعلی و redaction سازگار می‌ماند.
5. timeout و خطای ابزار به پاسخ کنترل‌شده و Audit تبدیل می‌شود.
6. تست گراف بدون شبکه و بدون اجرای واقعی ابزار قابل‌انجام است.
7. مسیر approval پیش از هر side effect متوقف می‌شود.

## ترتیب اجرای پیشنهادی بعد از تأیید

1. افزودن مدل وضعیت و Portهای کوچک، بدون نصب LangGraph.
2. افزودن Adapter LangGraph و تست گراف با fake tool.
3. اتصال `health_check` واقعی به Registry موجود.
4. افزودن checkpointer پایدار فقط پس از تعیین سیاست نگه‌داری داده.
5. اجرای تست‌های شکست، redaction، deny و resume.

تا زمان تأیید این سند، هیچ Intent جدیدی به `policies/intents.json` اضافه نمی‌شود.
