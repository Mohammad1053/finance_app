import datetime as dt

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.deps import currency_of, require_user
from app.jalali import parse_jalali, today_jalali_str
from app.models import Category, Frequency, PaymentMethod, RecurringTransaction, User
from app.ownership import owned
from app.services.recurring import generate_due
from app.templating import templates
from app.units import to_base

router = APIRouter(include_in_schema=False)

FREQUENCY_LABELS = {
    Frequency.WEEKLY: "هفتگی",
    Frequency.MONTHLY: "ماهانه",
    Frequency.YEARLY: "سالانه",
}


def _render(request: Request, db: Session, user: User, message: str = ""):
    """Render the recurring list partial with an optional info message."""
    items = (
        db.query(RecurringTransaction)
        .options(
            joinedload(RecurringTransaction.category),
            joinedload(RecurringTransaction.payment_method),
        )
        .filter(RecurringTransaction.user_id == user.id)
        .order_by(RecurringTransaction.next_date)
        .all()
    )
    return templates.TemplateResponse(
        request,
        "partials/recurring_list.html",
        {
            "items": items,
            "labels": FREQUENCY_LABELS,
            "categories": db.query(Category).filter(Category.user_id == user.id).order_by(Category.name).all(),
            "payment_methods": db.query(PaymentMethod)
            .filter(PaymentMethod.user_id == user.id)
            .order_by(PaymentMethod.name)
            .all(),
            "today": today_jalali_str(),
            "message": message,
        },
    )


@router.get("/recurring", response_class=HTMLResponse, dependencies=[Depends(require_user)])
def recurring_page(request: Request):
    """Recurring page; the list is loaded by HTMX."""
    return templates.TemplateResponse(request, "recurring.html", {})


@router.get("/ui/recurring", response_class=HTMLResponse)
def recurring_list(request: Request, db: Session = Depends(get_db), user: User = Depends(require_user)):
    """Return the recurring templates list."""
    return _render(request, db, user)


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
    user: User = Depends(require_user),
):
    """Create a recurring template starting on the given date."""
    if owned(db, Category, category_id, user.id) is None or owned(
        db, PaymentMethod, payment_method_id, user.id
    ) is None:
        raise HTTPException(status_code=400, detail="Invalid category or payment method")

    start = parse_jalali(start_date) or dt.date.today()
    db.add(
        RecurringTransaction(
            user_id=user.id,
            amount=to_base(amount, currency_of(request)),
            description=description.strip(),
            frequency=frequency,
            next_date=start,
            anchor_day=start.day,
            payment_method_id=payment_method_id,
            category_id=category_id,
        )
    )
    db.commit()
    return _render(request, db, user)


@router.post("/ui/recurring/generate", response_class=HTMLResponse)
def generate(request: Request, db: Session = Depends(get_db), user: User = Depends(require_user)):
    """Create this user's due transactions now and report how many were made."""
    count = generate_due(db, user_id=user.id)
    message = f"{count} تراکنش جدید ساخته شد." if count else "تراکنش موعدرسیده‌ای وجود نداشت."
    return _render(request, db, user, message)


@router.post("/ui/recurring/{item_id}/toggle", response_class=HTMLResponse)
def toggle(
    item_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    """Pause or resume one of the user's templates."""
    item = owned(db, RecurringTransaction, item_id, user.id)
    if item:
        item.active = not item.active
        db.commit()
    return _render(request, db, user)


@router.delete("/ui/recurring/{item_id}", response_class=HTMLResponse)
def delete(
    item_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    """Delete a template; transactions already created are kept."""
    item = owned(db, RecurringTransaction, item_id, user.id)
    if item:
        db.delete(item)
        db.commit()
    return _render(request, db, user)
