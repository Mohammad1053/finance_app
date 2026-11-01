import datetime as dt

import jdatetime

PERSIAN_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
ASCII_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")

MONTH_NAMES = [
    "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
]


def to_jalali_str(value: dt.date | None, persian_digits: bool = True) -> str:
    """Format a Gregorian date as a Jalali string like 1405/08/10."""
    if value is None:
        return ""
    j = jdatetime.date.fromgregorian(date=value)
    text = f"{j.year:04d}/{j.month:02d}/{j.day:02d}"
    return text.translate(PERSIAN_DIGITS) if persian_digits else text


def parse_jalali(text: str | None) -> dt.date | None:
    """Parse a Jalali string (Persian or ASCII digits, / or - separator) into a Gregorian date."""
    if not text:
        return None
    cleaned = text.strip().translate(ASCII_DIGITS).replace("-", "/")
    parts = cleaned.split("/")
    if len(parts) != 3:
        return None
    try:
        year, month, day = (int(p) for p in parts)
        return jdatetime.date(year, month, day).togregorian()
    except (ValueError, TypeError):
        return None


def today_jalali_str() -> str:
    """Return today's date as an ASCII-digit Jalali string, used as a form default."""
    return to_jalali_str(dt.date.today(), persian_digits=False)


def current_jalali_year_month() -> tuple[int, int]:
    """Return today's Jalali (year, month)."""
    j = jdatetime.date.today()
    return j.year, j.month


def jalali_month_range(year: int, month: int) -> tuple[dt.date, dt.date]:
    """Return the Gregorian half-open range [start, end) covering a Jalali month."""
    start = jdatetime.date(year, month, 1).togregorian()
    if month == 12:
        end = jdatetime.date(year + 1, 1, 1).togregorian()
    else:
        end = jdatetime.date(year, month + 1, 1).togregorian()
    return start, end


def jalali_month_key(value: dt.date) -> tuple[int, int]:
    """Return the Jalali (year, month) that contains a Gregorian date."""
    j = jdatetime.date.fromgregorian(date=value)
    return j.year, j.month
