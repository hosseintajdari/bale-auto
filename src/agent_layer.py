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
