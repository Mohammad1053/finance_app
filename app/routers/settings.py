from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from app.templating import templates
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Category, PaymentMethod, TransactionType

router = APIRouter(include_in_schema=False)


def _render(request: Request, db: Session, error: str = ""):
    """Render the lists partial with an optional error message."""
    return templates.TemplateResponse(
        request,
        "partials/settings_lists.html",
        {
            "categories": db.query(Category).order_by(Category.name).all(),
            "payment_methods": db.query(PaymentMethod).order_by(PaymentMethod.name).all(),
            "error": error,
        },
    )


@router.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request):
    """Settings page; the lists are loaded by HTMX."""
    return templates.TemplateResponse(request, "settings.html", {})


@router.get("/ui/settings", response_class=HTMLResponse)
def settings_lists(request: Request, db: Session = Depends(get_db)):
    """Return the categories and payment methods lists."""
    return _render(request, db)


@router.post("/ui/categories", response_class=HTMLResponse)
def add_category(
    request: Request,
    name: str = Form(...),
    type: TransactionType = Form(...),
    db: Session = Depends(get_db),
):
    """Create a category; report an error if the name already exists."""
    db.add(Category(name=name.strip(), type=type))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return _render(request, db, "این دسته قبلاً ثبت شده است.")
    return _render(request, db)


@router.delete("/ui/categories/{category_id}", response_class=HTMLResponse)
def delete_category(category_id: int, request: Request, db: Session = Depends(get_db)):
    """Delete a category unless transactions still use it."""
    category = db.get(Category, category_id)
    if category and category.transactions:
        return _render(request, db, "این دسته در تراکنش‌ها استفاده شده و قابل حذف نیست.")
    if category:
        db.delete(category)
        db.commit()
    return _render(request, db)


@router.post("/ui/payment-methods", response_class=HTMLResponse)
def add_payment_method(request: Request, name: str = Form(...), db: Session = Depends(get_db)):
    """Create a payment method; report an error if the name already exists."""
    db.add(PaymentMethod(name=name.strip()))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return _render(request, db, "این روش پرداخت قبلاً ثبت شده است.")
    return _render(request, db)


@router.delete("/ui/payment-methods/{pm_id}", response_class=HTMLResponse)
def delete_payment_method(pm_id: int, request: Request, db: Session = Depends(get_db)):
    """Delete a payment method unless transactions still use it."""
    pm = db.get(PaymentMethod, pm_id)
    if pm and pm.transactions:
        return _render(request, db, "این روش پرداخت در تراکنش‌ها استفاده شده و قابل حذف نیست.")
    if pm:
        db.delete(pm)
        db.commit()
    return _render(request, db)
