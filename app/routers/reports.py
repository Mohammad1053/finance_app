import datetime as dt

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Category, Transaction, TransactionType

router = APIRouter(include_in_schema=False)
templates = Jinja2Templates(directory="app/templates")


def _month_range(year: int, month: int) -> tuple[dt.date, dt.date]:
    """Return the first day of the month and the first day of the next month."""
    start = dt.date(year, month, 1)
    end = dt.date(
        year + 1, 1, 1) if month == 12 else dt.date(year, month + 1, 1)
    return start, end


def _parse_month(value: str | None) -> tuple[int, int]:
    """Parse 'YYYY-MM' into (year, month); fall back to the current month."""
    today = dt.date.today()
    try:
        year_str, month_str = (value or "").split("-")
        year, month = int(year_str), int(month_str)
        if 1 <= month <= 12 and 1900 <= year <= 2200:
            return year, month
    except ValueError:
        pass
    return today.year, today.month


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


def _monthly_trend(db: Session, months: int = 12, end_year: int = 0, end_month: int = 0) -> list[dict]:
    """Return income and expense totals for the last N months ending at the given month."""
    # Build the list of (year, month) pairs, oldest first
    pairs = []
    year, month = end_year, end_month
    for _ in range(months):
        pairs.append((year, month))
        month -= 1
        if month == 0:
            year, month = year - 1, 12
    pairs.reverse()

    first_start, _ = _month_range(*pairs[0])
    _, last_end = _month_range(*pairs[-1])

    # SQLite strftime groups rows by year-month in a single query
    ym = func.strftime("%Y-%m", Transaction.date)
    rows = (
        db.query(ym, Category.type, func.sum(Transaction.amount))
        .join(Transaction.category)
        .filter(Transaction.date >= first_start, Transaction.date < last_end)
        .group_by(ym, Category.type)
        .all()
    )
    data = {(key, t): int(total) for key, t, total in rows}

    result = []
    for y, m in pairs:
        key = f"{y:04d}-{m:02d}"
        result.append(
            {
                "month": key,
                "income": data.get((key, TransactionType.INCOME), 0),
                "expense": data.get((key, TransactionType.EXPENSE), 0),
            }
        )
    return result


@router.get("/reports", response_class=HTMLResponse)
def reports_page(request: Request):
    """Report page; charts are drawn in the browser from the JSON endpoint."""
    today = dt.date.today()
    return templates.TemplateResponse(
        request, "reports.html", {
            "current_month": f"{today.year:04d}-{today.month:02d}"}
    )


@router.get("/api/report-data")
def report_data(month: str | None = None, db: Session = Depends(get_db)):
    """Return all report numbers for the given month as JSON."""
    year, mon = _parse_month(month)
    start, end = _month_range(year, mon)
    return {
        "month": f"{year:04d}-{mon:02d}",
        "totals": _totals_by_type(db, start, end),
        "by_category": _expense_by_category(db, start, end),
        "trend": _monthly_trend(db, 12, year, mon),
    }
