from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_user
from app.models import Category, PaymentMethod, TransactionType, User
from app.ownership import owned
from app.templating import templates

router = APIRouter(include_in_schema=False)


def _render(request: Request, db: Session, user: User, error: str = ""):
    """Render the lists partial with an optional error message."""
    return templates.TemplateResponse(
        request,
        "partials/settings_lists.html",
        {
            "categories": db.query(Category).filter(Category.user_id == user.id).order_by(Category.name).all(),
            "payment_methods": db.query(PaymentMethod)
            .filter(PaymentMethod.user_id == user.id)
            .order_by(PaymentMethod.name)
            .all(),
            "error": error,
        },
    )


@router.get("/settings", response_class=HTMLResponse, dependencies=[Depends(require_user)])
def settings_page(request: Request):
    """Settings page; the lists are loaded by HTMX."""
    return templates.TemplateResponse(request, "settings.html", {})


@router.get("/ui/settings", response_class=HTMLResponse)
def settings_lists(request: Request, db: Session = Depends(get_db), user: User = Depends(require_user)):
    """Return the categories and payment methods lists."""
    return _render(request, db, user)


@router.post("/ui/categories", response_class=HTMLResponse)
def add_category(
    request: Request,
    name: str = Form(...),
    type: TransactionType = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    """Create a category; report an error if the user already has that name."""
    if not name.strip():
        return _render(request, db, user, "نام دسته نمی‌تواند خالی باشد.")
    db.add(Category(user_id=user.id, name=name.strip(), type=type))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return _render(request, db, user, "این دسته قبلاً ثبت شده است.")
    return _render(request, db, user)


@router.delete("/ui/categories/{category_id}", response_class=HTMLResponse)
def delete_category(
    category_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    """Delete a category unless transactions still use it."""
    category = owned(db, Category, category_id, user.id)
    if category and category.transactions:
        return _render(request, db, user, "این دسته در تراکنش‌ها استفاده شده و قابل حذف نیست.")
    if category:
        db.delete(category)
        db.commit()
    return _render(request, db, user)


@router.post("/ui/payment-methods", response_class=HTMLResponse)
def add_payment_method(
    request: Request,
    name: str = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    """Create a payment method; report an error if the user already has that name."""
    if not name.strip():
        return _render(request, db, user, "نام روش پرداخت نمی‌تواند خالی باشد.")
    db.add(PaymentMethod(user_id=user.id, name=name.strip()))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return _render(request, db, user, "این روش پرداخت قبلاً ثبت شده است.")
    return _render(request, db, user)


@router.delete("/ui/payment-methods/{pm_id}", response_class=HTMLResponse)
def delete_payment_method(
    pm_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    """Delete a payment method unless transactions still use it."""
    pm = owned(db, PaymentMethod, pm_id, user.id)
    if pm and pm.transactions:
        return _render(request, db, user, "این روش پرداخت در تراکنش‌ها استفاده شده و قابل حذف نیست.")
    if pm:
        db.delete(pm)
        db.commit()
    return _render(request, db, user)
