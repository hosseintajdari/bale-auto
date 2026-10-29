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

TRANSACTION_NEGATIONS = {
    "نشد", "نشده", "نکردم", "نکردیم", "نکرده", "نگرفتم", "نگرفتیم",
    "ندادم", "ندادیم", "نمی", "نمیکنم", "نمیشه",
}


# Credit (نسیه) model: a credit entry is NOT a cash movement. A credit sale
# or "نسیه دادم" creates a receivable (someone owes the shopkeeper); buying
# on credit or "نسیه گرفتم" creates a payable (the shopkeeper owes). Cash
# moves only on a real دریافت/پرداخت or on settlement. Collection phrases
# ("طلبم رو گرفتم", "وصول", "تسویه کرد") are cash receipts, never credit.
CREDIT_MARKERS = ("نسیه", "قرض", "دفتری", "حساب باز")
COLLECTION_MARKERS = ("طلبم رو داد", "طلبم رو گرفتم", "وصول", "تسویه کرد", "پاس شد")
CREDIT_DESC_WORDS = ("حساب باز", "نسیه", "دفتری", "قرض", "طلب", "بدهی", "بدهکار")


def detect_credit(norm: str, description: str) -> tuple[str, Optional[str], str]:
    """Return (kind, credit_direction, counterparty) for a normalized text.

    kind is "credit" only when a credit marker is present and the text is
    not a collection of an old debt. credit_direction is "incoming" for a
    receivable (owed TO the user) and "outgoing" for a payable (owed BY
    the user). counterparty is the person named in the description with
    the credit words stripped out.
    """
    if any(c in norm for c in COLLECTION_MARKERS):
        return "cash", None, ""
    has_marker = any(m in norm for m in CREDIT_MARKERS) or "طلب" in norm
    if not has_marker:
        return "cash", None, ""
    payable = "خرید" in norm or (
        "گرفتم" in norm and ("نسیه" in norm or "قرض" in norm)
    )
    counterparty = description
    for word in CREDIT_DESC_WORDS:
        counterparty = counterparty.replace(word, " ")
    counterparty = " ".join(counterparty.split()).strip(" :،,-")
    return "credit", ("outgoing" if payable else "incoming"), counterparty


@dataclass
class BazaarParseResult:
    amount: Optional[int]
    unit: str
    direction: Optional[str]
    description: str
    raw_amount_str: str
    is_sub_thousand_ambiguous: bool = False
    kind: str = "cash"
    counterparty: str = ""


def normalize_text(text: str) -> str:
    t = text.translate(DIGITS).replace("ي", "ی").replace("ك", "ک")
    # Arabic decimal separator (U+066B, standard on Persian keyboards)
    # becomes a dot so "۲٫۵ میلیون" parses as 2.5 million, not 5 million.
    t = t.replace("٫", ".")
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

    # Billions may optionally be followed by a lower million component.
    # The gap before a scale word is \s* (not \s+): glued forms like
    # «۵میلیون» and «۵۰۰هزار» are how fast typing and STT actually arrive.
    m = re.search(rf"({NUM_EXPR})\s*میلیارد(?:\s+و\s+({NUM_EXPR})\s*میلیون)?", norm)
    if m:
        billion_value = parse_num_token(m.group(1))
        million_value = parse_num_token(m.group(2)) if m.group(2) else 0
        if billion_value is not None and million_value is not None:
            total = int(billion_value * 1_000_000_000 + million_value * 1_000_000)
            return total, unit, m.group(0), False

    m = re.search(rf"({NUM_EXPR})\s*میلیارد", norm)
    if m:
        value = parse_num_token(m.group(1))
        if value is not None:
            return int(value * 1_000_000_000), unit, m.group(0), False

    # Pattern 1: X میلیون و Y هزار (or X میلیون و Y where Y is e.g. 200, 500)
    m = re.search(rf"({NUM_EXPR})\s*میلیون(?:\s+و\s+({NUM_EXPR})(?:\s*هزار)?)?", norm)
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

    # Standalone half-million is a common amount shorthand.
    m = re.search(r"(?<!\w)نیم\s+میلیون(?!\w)", norm)
    if m:
        return 500_000, unit, m.group(0), False

    # Pattern 3: X میلیون
    m = re.search(rf"({NUM_EXPR})\s*میلیون", norm)
    if m:
        val = parse_num_token(m.group(1))
        if val is not None:
            return int(val * 1_000_000), unit, m.group(0), False

    # Pattern 4: X هزار
    m = re.search(rf"({NUM_EXPR})\s*هزار", norm)
    if m:
        val = parse_num_token(m.group(1))
        if val is not None:
            return int(val * 1_000), unit, m.group(0), False

    # Parse compound Persian number words as a whole before single-word fallback.
    compound = re.search(
        rf"(?<!\w)({NUM_WORD_PATTERN}(?:\s+و\s+{NUM_WORD_PATTERN})+)(?!\w)",
        norm,
    )
    if compound:
        value = parse_num_token(compound.group(1))
        if value is not None:
            is_sub_thousand = 0 < value < 1000
            return int(value), unit, compound.group(1), is_sub_thousand

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


def has_transaction_negation(norm: str) -> bool:
    # Unicode word tokenization also separates ZWNJ forms such as نشده‌است.
    return bool(TRANSACTION_NEGATIONS.intersection(re.findall(r"\w+", norm)))


def extract_direction(norm: str) -> Tuple[Optional[str], Optional[str]]:
    if has_transaction_negation(norm):
        return None, None

    def matches(keywords: list[str]) -> list[str]:
        return [
            keyword
            for keyword in keywords
            if re.search(r"(?<!\w)" + re.escape(keyword) + r"(?!\w)", norm)
        ]

    incoming = matches(INCOMING_KEYWORDS)
    outgoing = matches(OUTGOING_KEYWORDS)
    if incoming and outgoing:
        return None, None
    if incoming:
        return "incoming", incoming[0]
    if outgoing:
        return "outgoing", outgoing[0]
    return None, None


def extract_description(norm: str, amount_str: str, dir_keyword: Optional[str]) -> str:
    cleaned = norm
    if amount_str:
        cleaned = re.sub(
            r"(?<!\w)" + re.escape(amount_str) + r"(?!\w)", " ", cleaned
        )
    if dir_keyword:
        cleaned = re.sub(
            r"(?<!\w)" + re.escape(dir_keyword) + r"(?!\w)", " ", cleaned
        )
    for noise in [
        "تومان", "تومن", "ریال", "میلیارد", "میلیون", "هزار", "بابت", "برای", "به", "از",
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
    kind, credit_direction, counterparty = detect_credit(norm, desc)
    if kind == "credit":
        # Credit semantics decide the direction on their own (receivable
        # vs payable); no direction-clarification round-trip for credit.
        direction = credit_direction
    return BazaarParseResult(
        amount=amount,
        unit=unit,
        direction=direction,
        description=desc,
        raw_amount_str=amt_str,
        is_sub_thousand_ambiguous=is_sub_thousand,
        kind=kind,
        counterparty=counterparty,
    )
