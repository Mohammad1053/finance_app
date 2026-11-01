import datetime as dt

import pytest

from app.jalali import (
    jalali_month_key,
    jalali_month_range,
    parse_jalali,
    to_jalali_str,
)


def test_gregorian_to_jalali_ascii():
    assert to_jalali_str(dt.date(2026, 11, 1),
                         persian_digits=False) == "1405/08/10"


def test_gregorian_to_jalali_persian_digits():
    assert to_jalali_str(dt.date(2026, 11, 1)) == "۱۴۰۵/۰۸/۱۰"


def test_none_date_gives_empty_string():
    assert to_jalali_str(None) == ""


@pytest.mark.parametrize(
    "text",
    ["1405/08/10", "۱۴۰۵/۰۸/۱۰", "1405-08-10", " 1405/08/10 "],
)
def test_parse_accepts_digit_and_separator_variants(text):
    assert parse_jalali(text) == dt.date(2026, 11, 1)


@pytest.mark.parametrize("text", ["1405/13/40", "1405/8", "abc", "", None])
def test_parse_rejects_invalid_input(text):
    assert parse_jalali(text) is None


def test_roundtrip_for_many_days():
    start = dt.date(2025, 1, 1)
    for offset in range(0, 1500, 7):
        day = start + dt.timedelta(days=offset)
        assert parse_jalali(to_jalali_str(day, persian_digits=False)) == day


def test_month_range_of_aban_1405():
    # Aban has 30 days: 1405/08/01 = 2026-10-23, and Azar starts on 2026-11-22
    assert jalali_month_range(1405, 8) == (
        dt.date(2026, 10, 23), dt.date(2026, 11, 22))


def test_month_ranges_are_contiguous_and_sane():
    for month in range(1, 13):
        start, end = jalali_month_range(1405, month)
        assert 29 <= (end - start).days <= 31
    # Last month of a year ends exactly where the next year begins
    assert jalali_month_range(1405, 12)[1] == jalali_month_range(1406, 1)[0]


def test_month_key_matches_range():
    assert jalali_month_key(dt.date(2026, 11, 1)) == (1405, 8)
    start, end = jalali_month_range(1405, 8)
    assert jalali_month_key(start) == (1405, 8)
    assert jalali_month_key(end) == (1405, 9)
