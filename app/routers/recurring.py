import datetime as dt

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import Category, Frequency, PaymentMethod, RecurringTransaction
from app.services.recurring import generate_due

router = APIRouter(include_in_schema=False)
templates = Jinja2Templates(directory="app/templates")

FREQUENCY_LABELS = {
    Frequency.WEEKLY: "هفتگی",
    Frequency.MONTHLY: "ماهانه",
    Frequency.YEARLY: "سالانه",
}


def _render(request: Request, db: Session, message: str = ""):
    """Render the recurring list partial with an optional info message."""
    items = (
        db.query(RecurringTransaction)
        .options(
            joinedload(RecurringTransaction.category),
            joinedload(RecurringTransaction.payment_method),
        )
        .order_by(RecurringTransaction.next_date)
        .all()
    )
    return templates.TemplateResponse(
        request,
        "partials/recurring_list.html",
        {
            "items": items,
            "labels": FREQUENCY_LABELS,
            "categories": db.query(Category).order_by(Category.name).all(),
            "payment_methods": db.query(PaymentMethod).order_by(PaymentMethod.name).all(),
            "today": dt.date.today().isoformat(),
            "message": message,
        },
    )


@router.get("/recurring", response_class=HTMLResponse)
def recurring_page(request: Request):
    """Recurring page; the list is loaded by HTMX."""
    return templates.TemplateResponse(request, "recurring.html", {})


@router.get("/ui/recurring", response_class=HTMLResponse)
def recurring_list(request: Request, db: Session = Depends(get_db)):
    """Return the recurring templates list."""
    return _render(request, db)


@router.post("/ui/recurring", response_class=HTMLResponse)
def add_recurring(
    request: Request,
    amount: int = Form(gt=0),
    start_date: str = Form(...),
    description: str = Form(""),
    frequency: Frequency = Form(...),
    payment_method_id: int = Form(...),
    category_id: int = Form(...),
    db: Session = Depends(get_db),
):
    """Create a recurring template starting on the given date."""
    try:
        start = dt.date.fromisoformat(start_date)
    except ValueError:
        start = dt.date.today()
    db.add(
        RecurringTransaction(
            amount=amount,
            description=description.strip(),
            frequency=frequency,
            next_date=start,
            anchor_day=start.day,
            payment_method_id=payment_method_id,
            category_id=category_id,
        )
    )
    db.commit()
    return _render(request, db)


@router.post("/ui/recurring/generate", response_class=HTMLResponse)
def generate(request: Request, db: Session = Depends(get_db)):
    """Create all due transactions now and report how many were made."""
    count = generate_due(db)
    message = f"{count} تراکنش جدید ساخته شد." if count else "تراکنش موعدرسیده‌ای وجود نداشت."
    return _render(request, db, message)


@router.post("/ui/recurring/{item_id}/toggle", response_class=HTMLResponse)
def toggle(item_id: int, request: Request, db: Session = Depends(get_db)):
    """Pause or resume a template."""
    item = db.get(RecurringTransaction, item_id)
    if item:
        item.active = not item.active
        db.commit()
    return _render(request, db)


@router.delete("/ui/recurring/{item_id}", response_class=HTMLResponse)
def delete(item_id: int, request: Request, db: Session = Depends(get_db)):
    """Delete a template; transactions already created are kept."""
    item = db.get(RecurringTransaction, item_id)
    if item:
        db.delete(item)
        db.commit()
    return _render(request, db)
