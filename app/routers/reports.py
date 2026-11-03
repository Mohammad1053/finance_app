import datetime as dt

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import currency_of, require_profile
from app.jalali import (
    MONTH_NAMES,
    current_jalali_year_month,
    jalali_month_key,
    jalali_month_range,
)
from app.models import Category, Transaction, TransactionType
from app.templating import templates
from app.units import factor

router = APIRouter(include_in_schema=False, dependencies=[
                   Depends(require_profile)])


def _parse_month(year: int | None, month: int | None) -> tuple[int, int]:
    """Validate a Jalali year and month; fall back to the current Jalali month."""
    cur_year, cur_month = current_jalali_year_month()
    if year is None or month is None:
        return cur_year, cur_month
    if 1 <= month <= 12 and 1200 <= year <= 1700:
        return year, month
    return cur_year, cur_month


def _totals_by_type(db: Session, start: dt.date, end: dt.date) -> dict:
    """Return income, expense and balance for the half-open range [start, end)."""
    rows = (
        db.query(Category.type, func.sum(Transaction.amount))
        .join(Transaction.category)
        .filter(Transaction.date >= start, Transaction.date < end)
        .group_by(Category.type)
        .all()
    )
    totals = {t: s for t, s in rows}
    income = int(totals.get(TransactionType.INCOME, 0) or 0)
    expense = int(totals.get(TransactionType.EXPENSE, 0) or 0)
    return {"income": income, "expense": expense, "balance": income - expense}


def _expense_by_category(db: Session, start: dt.date, end: dt.date) -> list[dict]:
    """Return expense totals per category, largest first."""
    rows = (
        db.query(Category.name, func.sum(Transaction.amount))
        .join(Transaction.category)
        .filter(
            Category.type == TransactionType.EXPENSE,
            Transaction.date >= start,
            Transaction.date < end,
        )
        .group_by(Category.name)
        .order_by(func.sum(Transaction.amount).desc())
        .all()
    )
    return [{"name": name, "total": int(total)} for name, total in rows]


def _monthly_trend(db: Session, year: int, month: int, months: int = 12) -> list[dict]:
    """Return income and expense per Jalali month for the last N months ending at the given one."""
    # Build the list of Jalali (year, month) pairs, oldest first
    pairs = []
    y, m = year, month
    for _ in range(months):
        pairs.append((y, m))
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    pairs.reverse()

    first_start, _ = jalali_month_range(*pairs[0])
    _, last_end = jalali_month_range(*pairs[-1])

    # Fetch (date, type, amount) rows once, then bucket them by Jalali month in Python
    rows = (
        db.query(Transaction.date, Category.type, Transaction.amount)
        .join(Transaction.category)
        .filter(Transaction.date >= first_start, Transaction.date < last_end)
        .all()
    )
    buckets = {pair: {"income": 0, "expense": 0} for pair in pairs}
    for date_value, type_value, amount in rows:
        key = jalali_month_key(date_value)
        if key in buckets:
            buckets[key][type_value.value] += amount

    return [
        {
            "month": f"{MONTH_NAMES[m - 1]} {y}",
            "income": buckets[(y, m)]["income"],
            "expense": buckets[(y, m)]["expense"],
        }
        for y, m in pairs
    ]


@router.get("/reports", response_class=HTMLResponse)
def reports_page(request: Request):
    """Report page; charts are drawn in the browser from the JSON endpoint."""
    year, month = current_jalali_year_month()
    return templates.TemplateResponse(
        request,
        "reports.html",
        {
            "current_year": year,
            "current_month": month,
            "month_names": MONTH_NAMES,
            "years": list(range(year - 5, year + 1)),
        },
    )


@router.get("/api/report-data")
def report_data(
    request: Request,
    year: int | None = None,
    month: int | None = None,
    db: Session = Depends(get_db),
):
    """Return all report numbers for the given Jalali month, in the selected currency."""
    y, m = _parse_month(year, month)
    start, end = jalali_month_range(y, m)
    k = factor(currency_of(request))
    totals = _totals_by_type(db, start, end)
    return {
        "year": y,
        "month": m,
        "totals": {key: value * k for key, value in totals.items()},
        "by_category": [
            {"name": item["name"], "total": item["total"] * k}
            for item in _expense_by_category(db, start, end)
        ],
        "trend": [
            {"month": t["month"], "income": t["income"]
                * k, "expense": t["expense"] * k}
            for t in _monthly_trend(db, y, m)
        ],
    }
