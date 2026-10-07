"""Small shared helpers (parsing, normalisation, column mapping)."""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable, Optional

BLANK_TOKENS = {"", "n/a", "na", "n.a.", "null", "none", "nil", "-", "--", "?", "nan", "tbd", "#n/a"}


def is_blank(value: Any) -> bool:
    return value is None or str(value).strip().lower() in BLANK_TOKENS


def snake(text: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(text or "").strip().lower()).strip("_")


def norm_sku(value: Any) -> str:
    """Case/spacing/punctuation-insensitive SKU key: ' sku-1002 ' -> 'SKU1002'."""
    return re.sub(r"[^A-Z0-9]", "", str(value or "").upper())


def to_decimal(value: Any) -> Optional[Decimal]:
    """Parse '$1,234.50', '12 %', '(5)', 7, 7.5 ... -> Decimal; None if blank/invalid."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float, Decimal)):
        try:
            d = Decimal(str(value))
        except InvalidOperation:
            return None
        return d if d.is_finite() else None
    text = str(value).strip()
    if is_blank(text):
        return None
    negative = text.startswith("(") and text.endswith(")")
    cleaned = re.sub(r"[^\d.\-]", "", text.replace(",", ""))
    if cleaned in ("", "-", ".", "-."):
        return None
    try:
        d = Decimal(cleaned)
    except InvalidOperation:
        return None
    if not d.is_finite():
        return None
    return -d if negative and d > 0 else d


def map_columns(headers: Iterable[str], aliases: dict[str, Iterable[str]]) -> dict[str, str]:
    """canonical name -> actual header, matching on snake-cased aliases (first match wins)."""
    by_key = {snake(h): h for h in headers if snake(h)}
    mapping: dict[str, str] = {}
    for canonical, names in aliases.items():
        for candidate in (canonical, *names):
            actual = by_key.get(snake(candidate))
            if actual is not None and actual not in mapping.values():
                mapping[canonical] = actual
                break
    return mapping


_MONTHS = {m.lower(): i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July", "August",
     "September", "October", "November", "December"], start=1)}
_MONTHS.update({k[:3]: v for k, v in list(_MONTHS.items())})
_MONTHS["sept"] = 9
_WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def parse_date(text: Any, today: Optional[date] = None) -> Optional[date]:
    """Parse ISO dates, '5 Nov 2026', 'Nov 5, 2026', 'tomorrow', 'in 3 days', 'friday'."""
    if text is None:
        return None
    if isinstance(text, datetime):
        return text.date()
    if isinstance(text, date):
        return text
    s = str(text).strip().lower()
    if not s:
        return None
    today = today or date.today()
    m = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", s)
    if m:
        try:
            return date(int(m[1]), int(m[2]), int(m[3]))
        except ValueError:
            return None
    m = re.fullmatch(r"(\d{1,2})(?:st|nd|rd|th)?\s+([a-z]{3,9})\.?,?\s+(\d{4})", s)
    if m and m[2] in _MONTHS:
        try:
            return date(int(m[3]), _MONTHS[m[2]], int(m[1]))
        except ValueError:
            return None
    m = re.fullmatch(r"([a-z]{3,9})\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})", s)
    if m and m[1] in _MONTHS:
        try:
            return date(int(m[3]), _MONTHS[m[1]], int(m[2]))
        except ValueError:
            return None
    m = re.fullmatch(r"([a-z]{3,9})\.?\s+(\d{1,2})(?:st|nd|rd|th)?", s) or None
    if m and m[1] in _MONTHS:
        return _next_occurrence(_MONTHS[m[1]], int(m[2]), today)
    m = re.fullmatch(r"(\d{1,2})(?:st|nd|rd|th)?\s+([a-z]{3,9})\.?", s)
    if m and m[2] in _MONTHS:
        return _next_occurrence(_MONTHS[m[2]], int(m[1]), today)
    if s in ("today", "eod", "end of day"):
        return today
    if s == "tomorrow":
        return today + timedelta(days=1)
    m = re.fullmatch(r"(?:in\s+)?(\d{1,3})\s+days?(?:\s+from\s+now)?", s)
    if m:
        return today + timedelta(days=int(m[1]))
    m = re.fullmatch(r"(?:by\s+|next\s+|this\s+)?(" + "|".join(_WEEKDAYS) + ")", s)
    if m:
        delta = (_WEEKDAYS.index(m[1]) - today.weekday()) % 7
        return today + timedelta(days=delta or 7)
    return None


def _next_occurrence(month: int, day: int, today: date) -> Optional[date]:
    """'Nov 1' with no year -> the next Nov 1 on or after today."""
    for year in (today.year, today.year + 1):
        try:
            d = date(year, month, day)
        except ValueError:
            return None
        if d >= today:
            return d
    return None


_MONTH_RX = (r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|"
             r"sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)")
_DATE_TOKEN = re.compile(
    r"\d{4}-\d{1,2}-\d{1,2}"
    rf"|\b\d{{1,2}}(?:st|nd|rd|th)?\s+{_MONTH_RX}\b\.?(?:,?\s+\d{{4}})?(?!\d)"
    rf"|\b{_MONTH_RX}\b\.?\s+\d{{1,2}}(?:st|nd|rd|th)?(?:,?\s+\d{{4}})?(?!\d)", re.I)


def find_dates(text: str, today: Optional[date] = None) -> list[date]:
    out = []
    for m in _DATE_TOKEN.finditer(text or ""):
        d = parse_date(m.group(0), today)
        if d:
            out.append(d)
    return out


def truncate_words(text: str, limit: int) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    cut = text[: limit].rsplit(" ", 1)[0].rstrip(" ,;:-–—")
    return cut or text[:limit]
