"""Agent layer for bale-auto (v2 plan sections 11 and 13).

Two pieces, both subordinate to the deterministic core:

1. SoftLayer (section 11) — a chat model may *rephrase* texts the core has
   already produced (confirmations, reports, guide lines) in a friendlier
   tone. It never computes anything: every number in the model's output is
   checked verbatim against the core's text, and any mismatch, error,
   timeout or missing configuration falls back to the core's template,
   unchanged and unblocked. Customer text reaches the model only as the
   bot's own already-safe output — never as instructions.

2. The guide spine (section 13) — a scripted, resumable onboarding walk:
   shop type -> what they sell -> first real entry together -> done. The
   steps, their order and their state live in the engine's session store;
   this module only owns the step vocabulary and the (short) texts. The
   owner's simplicity law: one ask per message, buttons over typing,
   no feature dumps.

3. The owner's agent laws (docs/product/AGENT-LAWS.md) — the gate in
   this module's second half. A deterministic scope gate decides BEFORE
   any model call whether a text may be polished at all (guide turns
   and scoped questions only; transactions and reports never). An
   extraction attempt is refused by a fixed template and never reaches
   the model. Every fixed text is a constant here — the model writes
   none of them. This module holds no database handle, no file paths
   and no other user's data: it only ever receives one core-composed
   text for the current user plus flow constants.
"""
from __future__ import annotations

import json
import logging
import os
import re
import urllib.request
from typing import Callable, Optional

logger = logging.getLogger("agent_layer")

FA_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")


def numbers_in(text: str) -> list[str]:
    """All number tokens of a text, normalised for comparison.

    Persian digits become Latin; thousands separators (٬ and ,) are
    dropped so "۵۰۰" and "500,000" compare by value-bearing digits.
    """
    t = text.translate(FA_DIGITS).replace("٬", "").replace(",", "")
    return sorted(re.findall(r"\d+(?:\.\d+)?", t))


class ChatModel:
    """Minimal OpenAI-compatible chat client with an injectable transport.

    The transport signature is (url, api_key, payload, timeout) -> dict,
    so tests stub the model without any network.
    """

    def __init__(
        self,
        url: str,
        api_key: str,
        model: str,
        transport: Optional[Callable] = None,
        timeout: int = 12,
    ) -> None:
        self.url = url
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self._transport = transport or self._http_transport

    @staticmethod
    def _http_transport(url: str, api_key: str, payload: dict, timeout: int) -> dict:
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        req = urllib.request.Request(
            url, data=json.dumps(payload).encode("utf-8"), headers=headers
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def complete(self, system: str, user: str) -> Optional[str]:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.3,
        }
        try:
            data = self._transport(self.url, self.api_key, payload, self.timeout)
        except Exception as e:
            logger.warning(f"agent model call failed: {e}")
            return None
        try:
            text = str(data["choices"][0]["message"]["content"]).strip()
        except Exception:
            logger.warning("agent model returned an unusable response")
            return None
        return text or None


POLISH_SYSTEM = (
    "تو ویراستار لحن یک بات حسابداری فارسی هستی. متن داده‌شده را فقط کمی "
    "دوستانه‌تر و روان‌تر کن، با همان معنا و همان خط‌ها. قانون‌های سخت: "
    "هیچ عدد، مبلغ، اسم، کد یا نشانی را تغییر نده؛ چیزی به متن اضافه یا از "
    "آن کم نکن؛ نشانه‌ها و ایموجی‌ها را نگه دار. فقط متن نهایی را برگردان."
)


class SoftLayer:
    """Model-polish with a hard verbatim guard and a template fallback."""

    def __init__(self, model: Optional[ChatModel] = None) -> None:
        self.model = model

    @classmethod
    def from_env(cls) -> "SoftLayer":
        if os.environ.get("AGENT_MODEL_ENABLED", "1") == "0":
            return cls(None)
        url = os.environ.get("AGENT_MODEL_URL", "").strip()
        key = os.environ.get("AGENT_MODEL_KEY", "").strip()
        name = os.environ.get("AGENT_MODEL_NAME", "").strip()
        if not (url and key and name):
            return cls(None)
        if not url.rstrip("/").endswith("/chat/completions"):
            url = url.rstrip("/") + "/chat/completions"
        return cls(ChatModel(url, key, name))

    @property
    def enabled(self) -> bool:
        return self.model is not None

    def polish(self, text: str) -> str:
        """Return a friendlier rendering of `text`, or `text` itself.

        The fallback is the contract: model down, quota out, slow, or a
        single digit out of place -> the deterministic template is used.
        """
        if self.model is None or not text or not text.strip():
            return text
        out = self.model.complete(POLISH_SYSTEM, text)
        if not out:
            return text
        if numbers_in(out) != numbers_in(text):
            logger.warning("agent polish rejected: numbers changed")
            return text
        if len(out) > 3 * len(text) + 50:
            logger.warning("agent polish rejected: implausible length")
            return text
        return out


# ----- section 13: the guide spine -------------------------------------

GUIDE_STEP_SHOP_TYPE = "shop_type"
GUIDE_STEP_GOODS = "goods"
GUIDE_STEP_FIRST_ENTRY = "first_entry"

SHOP_TYPES = ["مغازه و فروشگاه", "داروخانه", "کارگاه و خدمات", "سایر"]

GUIDE_SKIP_ALL = {"رد کردن راهنما", "رد کردن", "رد کن"}
GUIDE_SKIP_STEP = {"رد کردن این قدم", "رد کردن", "فعلاً نه", "فعلا نه", "بعداً", "بعدا"}
GUIDE_LATER_ENTRY = {"بعداً ثبت می‌کنم", "بعدا ثبت می‌کنم", "بعداً", "بعدا"}


def new_guide_state() -> dict:
    return {
        "step": GUIDE_STEP_SHOP_TYPE,
        "done": False,
        "skipped": False,
        "shop_type": "",
        "goods": "",
    }


def guide_greeting(first_name: str, referral_code: str) -> str:
    name = first_name or "عزیز"
    return (
        f"سلام {name}! 👋\n"
        "من دستیار هوشمند حساب‌کتاب مغازه‌ات هستم؛ دفتر فروش و طلبت.\n"
        "چند قدم کوتاه با هم می‌ریم.\n"
        "اول: کارت چیه؟ یکی را انتخاب کن:\n"
        f"🎁 کد معرفی تو: {referral_code}"
    )


def guide_goods_prompt() -> str:
    return (
        "خوب! حالا کوتاه بگو چی می‌فروشی یا چه خدمتی می‌دی؟\n"
        "(مثلاً: مواد غذایی)"
    )


def guide_first_entry_prompt() -> str:
    return (
        "حالا اولین فروشت را با هم ثبت کنیم ✍️\n"
        "فقط بنویس: «فروش ۲۰۰ هزار تومن»\n"
        "(با مبلغ و کالای واقعی خودت)"
    )


def guide_done_text() -> str:
    return (
        "🎉 تمام شد! اولین ثبتت انجام شد.\n"
        "از این به بعد فقط بنویس یا ویس بفرست؛ ثبتش با من.\n"
        "هر شب ساعت ۲۱ گزارش روزت می‌آید."
    )


def guide_skipped_text() -> str:
    return (
        "باشد، راهنما را رد کردیم.\n"
        "هر وقت خواستی، فقط بنویس: «فروش ۲۰۰ هزار تومن».\n"
        "با «راهنما» هم توضیح کامل هست."
    )


# ----- the owner's agent laws: scope gate, denylist, fixed texts -------
# docs/product/AGENT-LAWS.md states the laws in full. Everything here is
# deterministic and runs BEFORE any model call. The agent is not a free
# chatbot: it accompanies the first setup steps, then answers scoped
# questions about the product and the user's own ledger — nothing else.

OFF_SCOPE_REPLY = (
    "من فقط برای دفتر و حساب‌وکتابت اینجام؛ "
    "بنویس «فروش ۵۰۰ هزار تومان» یا سؤالت را درباره‌ی دفترت بپرس."
)

UNKNOWN_REPLY = (
    "این را نمی‌دانم؛ از پشتیبان بپرس.\n"
    "سؤالت را برای پشتیبان فرستادم تا جوابش را بگیری."
)

REFUSAL_REPLY = (
    "به دیتابیس، فایل‌های سرور یا داده‌های بقیه دسترسی ندارم و چنین چیزی نمی‌دهم.\n"
    "من فقط برای دفتر و حساب‌وکتاب خودت اینجام."
)

# Extraction attempts. Strong targets are attempts on their own; weak
# targets count only together with a request intent — or, for database
# targets, as a bare short demand with no amount in it — so a purchase
# line like «خرید توکن اینترنت ۵۰ هزار» that the parser claims is
# never mistaken for an attack on the bot.
_EXTRACTION_STRONG = (
    ("prompt", ("پرامپت", "پرومپت", "prompt", "دستورات سیستمی", "دستورالعمل سیستمی")),
    ("secrets", ("توکن بات", "رمز سرور", "پسورد سرور", "رمز عبور سرور",
                 "کلید api", "api key", "apikey")),
    ("server_files", ("سورس کد", "کد منبع", "فایل‌های سرور", "فایل های سرور",
                      "فایلهای سرور", "محتوای سرور")),
    ("others_data", ("اطلاعات بقیه", "اطلاعات دیگران", "داده‌های بقیه",
                     "داده های بقیه", "اطلاعات مردم", "داده‌های مردم",
                     "لیست کاربران", "لیست کاربرها", "همه کاربران",
                     "همه‌ی کاربران", "مشتری‌های بقیه", "مشتری های بقیه")),
)
_EXTRACTION_WEAK = (
    ("database", ("دیتابیس", "دیتا بیس", "پایگاه داده", "database",
                  "دامپ", "dump", "بکاپ دیتابیس", "بک آپ دیتابیس",
                  "فایل بکاپ", "sqlite")),
    ("secrets", ("توکن", "token")),
)
_INTENT_MARKERS = (
    "بده", "بفرست", "نشون", "نشان", "می‌خوام", "میخوام", "می خواهم",
    "دانلود", "استخراج", "چیه", "چیست", "بگو", "بگین", "لو بده",
)


def extraction_kind(text: str) -> str | None:
    """Classify an extraction attempt, or None.

    Deterministic substring rules over the normalised text. Returns a
    short kind label ('database', 'prompt', 'secrets', 'server_files',
    'others_data') used for the owner's guard log — never the content.
    """
    t = (text or "").lower()
    for kind, terms in _EXTRACTION_STRONG:
        if any(term in t for term in terms):
            return kind
    has_intent = any(m in t for m in _INTENT_MARKERS)
    has_digit = any(c.isdigit() for c in t)
    for kind, terms in _EXTRACTION_WEAK:
        if not any(term in t for term in terms):
            continue
        if has_intent:
            return kind
        if kind == "database" and not has_digit and len(t.split()) <= 5:
            return kind
    return None


# Scoped questions: a question marker AND product vocabulary. When in
# doubt the message is NOT scoped and never reaches the model.
_QUESTION_MARKERS = (
    "؟", "?", "چطور", "چجور", "چگونه", "چرا", "چیه", "چیست", "یعنی چه",
    "چقدر", "چند", "آیا", "مگه", "می‌شه", "میشه", "ممکنه", "چه جوری",
)
_PRODUCT_VOCAB = (
    "ثبت", "گزارش", "طلب", "تسویه", "حذف", "برگردان", "پلن",
    "ماه رایگان", "کد معرفی", "معرفی", "نسیه", "بدهی", "بدهکار",
    "خروجی", "دفتر", "موجودی", "فروش", "خرید", "دخل", "خرج", "ویس",
    "تراکنش", "حساب‌وکتاب", "حساب و کتاب", "بازو", "بات", "فاکتور",
)


def is_scoped_question(text: str) -> bool:
    """Conservative scope test for the question-support role."""
    t = text or ""
    if not any(m in t for m in _QUESTION_MARKERS):
        if "کی" not in t.split():
            return False
    return any(v in t for v in _PRODUCT_VOCAB)


# Product facts: deterministic answers for how-to questions. The model
# may rephrase these (numbers guard applies); it never invents one.
# First match wins — keep entries ordered specific to general.
PRODUCT_FACTS = (
    (("تسویه",),
     "تسویه یعنی طلب یا بدهی یک نفر را ببندی. بنویس «طلب‌ها»، نفر را "
     "انتخاب کن و مبلغ را بفرست یا «همه‌اش» را بزن. تسویه‌ی ناقص هم "
     "می‌شود؛ بقیه‌اش باز می‌ماند."),
    (("حذف", "برگردان", "اشتباه ثبت"),
     "برای برگرداندن یک ثبت اشتباه بنویس «حذف آخری» یا «حذف تراکنش» و "
     "از فهرست انتخاب کن. حذف نرم است؛ ردّش در دفتر می‌ماند و از "
     "جمع‌ها کم می‌شود."),
    (("خروجی", "اکسل", "csv"),
     "بنویس «خروجی ماه» تا فایل CSV این ماه را همین‌جا بفرستم."),
    (("کد معرفی", "معرفی"),
     "کد معرفی‌ات را در «وضعیت من» می‌بینی. هر کس با کد تو بیاید و "
     "اولین تراکنشش را ثبت کند، یک ماه رایگان می‌گیری (تا ۶ ماه)؛ با "
     "نفر دومِ فعال، پلن ۲ برایت باز می‌شود."),
    (("ماه رایگان",),
     "ماه اول کامل و رایگان است و از اولین تراکنش تأییدشده‌ات شروع "
     "می‌شود، نه از اولین پیام. روزهای مانده را در «وضعیت من» و "
     "گزارش شبانه می‌بینی."),
    (("پلن",),
     "پلن‌ها: ماه اول رایگان و کامل؛ بعد «دفتر» ۴۹۹ هزار تومان، "
     "«حسابدار صنف» ۹۹۹ هزار تومان و «ارتباطی» ۱٬۰۹۹ هزار تومان در "
     "ماه. پلن فعلی‌ات را در «وضعیت من» ببین."),
    (("گزارش شبانه", "گزارش هر شب"),
     "گزارش روزت هر شب ساعت ۲۱ خودکار می‌آید. هر وقت هم خواستی بنویس "
     "«گزارش امروز» یا «گزارش مالی»."),
    (("ویس", "صوتی"),
     "به‌جای تایپ می‌توانی ویس بفرستی؛ به متن تبدیلش می‌کنم و مثل "
     "پیام نوشته‌شده بررسی و ثبت می‌شود."),
    (("ثبت",),
     "ثبت ساده است: بنویس «فروش ۵۰۰ هزار تومان» یا «خرج ناهار ۵۰ "
     "تومن»؛ پیش‌نویس را می‌بینی و با دکمه‌ی تأیید ثبتش می‌کنی. نسیه "
     "هم می‌شود: «فروش نسیه ۵۰۰ هزار به احمدی»."),
)


def match_product_fact(text: str) -> str | None:
    """The deterministic fact for a how-to question, or None."""
    t = text or ""
    for keywords, fact in PRODUCT_FACTS:
        if any(k in t for k in keywords):
            return fact
    return None
