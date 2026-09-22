"""Bazaar and Worker Persian NLP Parser for Conversational Work Ledger.

Tailored specifically for Iranian bazaar shopkeepers, merchants, and workers:
- Understands colloquial market terms (کارت کشید, پوز, فروش, دخل, خرید بار, خرج ناهار, مساعده, دستمزد).
- Parses Persian number words (میلیون, میلیارد, هزار, نیم, پونصد, دویست, ...).
- Auto-extracts description / memo without annoying ping-pong.
- Supports single-tap confirmation workflows.
- Safe guardrails: asks clarification when direction or scale (<1000) is ambiguous.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Optional, Tuple

DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")

NUMBER_WORDS = {
    "صفر": 0, "یک": 1, "یه": 1, "دو": 2, "سه": 3, "چهار": 4, "پنج": 5,
    "شش": 6, "شیش": 6, "هفت": 7, "هشت": 8, "نه": 9, "ده": 10,
    "یازده": 11, "دوازده": 12, "سیزده": 13, "چهارده": 14, "پانزده": 15, "پونزده": 15,
    "شانزده": 16, "شونزده": 16, "هفده": 17, "هجده": 18, "نوزده": 19,
    "بیست": 20, "سی": 30, "چهل": 40, "پنجاه": 50, "شصت": 60, "هفتاد": 70, "هشتاد": 80, "نود": 90,
    "صد": 100, "دویست": 200, "سیصد": 300, "چهارصد": 400, "پانصد": 500, "پونصد": 500,
    "ششصد": 600, "شیشصد": 600, "هفتصد": 700, "هشتصد": 800, "نهصد": 900,
}

NUM_WORD_PATTERN = (
    r"(?:یک|یه|دو|سه|چهار|پنج|شش|شیش|هفت|هشت|نه|ده|یازده|دوازده|سیزده|چهارده|پانزده|پونزده|"
    r"شانزده|شونزده|هفده|هجده|نوزده|بیست|سی|چهل|پنجاه|شصت|هفتاد|هشتاد|نود|صد|دویست|سیصد|چهارصد|"
    r"پانصد|پونصد|ششصد|شیشصد|هفتصد|هشتصد|نهصد)"
)
NUM_EXPR = rf"(?:\d+(?:\.\d+)?|{NUM_WORD_PATTERN}(?:\s+و\s+{NUM_WORD_PATTERN})*)"

INCOMING_KEYWORDS = [
    "دریافت شد", "دریافت", "دریافتی", "واریز شد", "واریز", "واریزی",
    "کارت کشیدند", "کارت کشیدن", "کارت کشید", "کارتخوان", "پوز", "دستگاه پوز",
    "فروختم", "فروش نقدی", "فروش", "فروخته شد", "دخل امروز", "دخل مغازه", "دخل",
    "طلبم رو داد", "طلبم رو گرفتم", "وصول چک", "پاس شد چک", "پاس شد", "وصول", "تسویه کرد",
    "انعام گرفتم", "مساعده گرفتم", "حقوق گرفتم", "دستمزد گرفتم", "پول گرفتم",
    "ریخت به حسابم", "به حسابم اومد", "به حسابم ریخت", "به کارتم اومد", "به کارتم ریخت",
    "ریخت به حساب", "ریختن به حساب", "گرفتم از", "گرفتم", "گرفتیم"
]

OUTGOING_KEYWORDS = [
    "پرداخت شد", "پرداخت", "پرداختی", "برداشت", "برداشتم",
    "خرج ناهار", "خرج مغازه", "خرج خونه", "خرج شد", "خرج", "هزینه",
    "خرید بار", "خرید جنس", "خرید عمده", "خریدم", "خریداری شد", "خرید",
    "کارت به کارت کردم", "کارت به کارت", "ریختم به حساب", "ریختم به", "ریختم",
    "دادم به", "دادم", "دادیم", "فرستادم برای", "فرستادم",
    "تسویه کردم با", "تسویه کردم", "تسویه حساب",
    "مساعده دادم به", "مساعده دادم", "حقوق دادم", "دستمزد دادم",
    "کرایه وانت", "کرایه اسنپ", "کرایه تاکسی", "کرایه مغازه", "کرایه",
    "پول بنزین", "بنزین", "قبض برق", "قبض آب", "قبض گاز", "قبض", "قسط وام", "قسط",
    "پول ناهار", "ناهار کارگرا", "ناهار", "شام"
]

CONFIRMATIONS = {
    "تأیید", "تایید", "تأیید و ثبت", "تایید و ثبت", "confirm", "ok",
    "بله", "آره", "اره", "ثبت", "ثبت کن", "ثبتش کن", "حله", "درسته",
    "اوکی", "خوبه", "دمت گرم", "نوکرتم", "باشه", "yes", "موافقم", "بزن ثبت"
}

CANCELLATIONS = {
    "لغو", "کنسل", "بیخیال", "ولش کن", "نمیخوام", "نه", "اشتباه شد", "لغوش کن",
    "منصرف شدم", "cancel", "/cancel", "لغو پیش نویس", "لغو پیش‌نویس", "انصراف"
}

SUMMARY_KEYWORDS = {
    "/summary", "گزارش", "گزارش مالی", "موجودی", "summary",
    "حساب کتاب", "دخل و خرج", "جمع حساب", "وضعیت حساب", "چقدر کار کردیم"
}


@dataclass
class BazaarParseResult:
    amount: Optional[int]
    unit: str
    direction: Optional[str]
    description: str
    raw_amount_str: str
    is_sub_thousand_ambiguous: bool = False


def normalize_text(text: str) -> str:
    t = text.translate(DIGITS).replace("ي", "ی").replace("ك", "ک")
    t = re.sub(r"[،,٬]", "", t)
    return " ".join(t.split())


def parse_num_token(tok: str) -> Optional[float]:
    if not tok:
        return None
    tok = tok.strip()
    if re.match(r"^\d+(?:\.\d+)?$", tok):
        return float(tok)
    parts = [p.strip() for p in re.split(r"\s+و\s+|\s+", tok) if p.strip()]
    if not parts:
        return None
    total = 0
    matched = False
    for p in parts:
        if p in NUMBER_WORDS:
            total += NUMBER_WORDS[p]
            matched = True
        elif p.isdigit():
            total += int(p)
            matched = True
        else:
            return None
    return float(total) if matched else None


def extract_amount_and_unit(norm: str) -> Tuple[Optional[int], str, str, bool]:
    """Extract numeric amount, currency unit, matched raw substring, and whether sub-1000 is ambiguous."""
    unit = "ریال" if "ریال" in norm else "تومان"

    # Pattern 1: X میلیون و Y هزار (or X میلیون و Y where Y is e.g. 200, 500)
    m = re.search(rf"({NUM_EXPR})\s+میلیون(?:\s+و\s+({NUM_EXPR})(?:\s+هزار)?)?", norm)
    if m:
        m_part, k_part = m.group(1), m.group(2)
        m_val = parse_num_token(m_part)
        if m_val is not None:
            k_val = 0.0
            if k_part:
                parsed_k = parse_num_token(k_part)
                if parsed_k is not None:
                    # If parsed_k is like 200, 500, it means 200 thousand
                    k_val = parsed_k * 1_000 if parsed_k < 1000 else parsed_k
            total = int(m_val * 1_000_000 + k_val)
            return total, unit, m.group(0), False

    # Pattern 2: X و نیم میلیون
    m = re.search(rf"({NUM_EXPR})\s+و\s+نیم\s+میلیون", norm)
    if m:
        val = parse_num_token(m.group(1))
        if val is not None:
            return int(val * 1_000_000 + 500_000), unit, m.group(0), False

    # Pattern 3: X میلیون
    m = re.search(rf"({NUM_EXPR})\s+میلیون", norm)
    if m:
        val = parse_num_token(m.group(1))
        if val is not None:
            return int(val * 1_000_000), unit, m.group(0), False

    # Pattern 4: X هزار
    m = re.search(rf"({NUM_EXPR})\s+هزار", norm)
    if m:
        val = parse_num_token(m.group(1))
        if val is not None:
            return int(val * 1_000), unit, m.group(0), False

    # Pattern 5: Plain digits with or without unit
    m = re.search(r"\b(\d+)\b", norm)
    if m:
        val = int(m.group(1))
        is_sub_thousand = (val < 1000 and val > 0)
        return val, unit, m.group(0), is_sub_thousand

    # Pattern 6: Pure Persian word (e.g. پونصد, دویست)
    for word, val in NUMBER_WORDS.items():
        if word in ["صفر", "یک", "یه"]:
            continue
        if re.search(r"\b" + word + r"\b(?:\s+(?:تومان|تومن|ریال))?", norm):
            is_sub_thousand = (val < 1000 and val > 0)
            return val, unit, word, is_sub_thousand

    return None, unit, "", False


def extract_direction(norm: str) -> Tuple[Optional[str], Optional[str]]:
    for kw in INCOMING_KEYWORDS:
        if kw in norm:
            return "incoming", kw
    for kw in OUTGOING_KEYWORDS:
        if kw in norm:
            return "outgoing", kw
    return None, None


def extract_description(norm: str, amount_str: str, dir_keyword: Optional[str]) -> str:
    cleaned = norm
    if amount_str:
        cleaned = cleaned.replace(amount_str, " ")
    if dir_keyword:
        cleaned = cleaned.replace(dir_keyword, " ")
    for noise in [
        "تومان", "تومن", "ریال", "میلیون", "هزار", "بابت", "برای", "به", "از",
        "شد", "کردم", "دادم", "گرفتم", "نقد", "نقدی"
    ]:
        cleaned = re.sub(r"\b" + noise + r"\b", " ", cleaned)
    desc = " ".join(cleaned.split()).strip()
    return desc


def parse_bazaar_message(text: str) -> BazaarParseResult:
    norm = normalize_text(text)
    amount, unit, amt_str, is_sub_thousand = extract_amount_and_unit(norm)
    direction, dir_kw = extract_direction(norm)
    desc = extract_description(norm, amt_str, dir_kw)
    return BazaarParseResult(
        amount=amount,
        unit=unit,
        direction=direction,
        description=desc,
        raw_amount_str=amt_str,
        is_sub_thousand_ambiguous=is_sub_thousand,
    )
