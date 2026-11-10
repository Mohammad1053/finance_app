import datetime as dt

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.deps import currency_of, require_user
from app.jalali import parse_jalali, today_jalali_str
from app.models import Category, PaymentMethod, Transaction, TransactionType, User
from app.ownership import owned
from app.templating import templates
from app.units import to_base

router = APIRouter(include_in_schema=False)


def _to_int(value: str | None) -> int | None:
    """Convert a form string to int; empty or invalid values become None."""
    try:
        return int(value) if value not in (None, "") else None
    except ValueError:
        return None


def _filtered_query(
    db: Session,
    user_id: int,
    date_from: dt.date | None,
    date_to: dt.date | None,
    category_id: int | None,
    payment_method_id: int | None,
    min_amount: int | None,
    max_amount: int | None,
    search: str | None,
):
    """Build the user's transactions query with all optional filters applied."""
    query = (
        db.query(Transaction)
        .options(joinedload(Transaction.category), joinedload(Transaction.payment_method))
        .filter(Transaction.user_id == user_id)
    )
    if date_from:
        query = query.filter(Transaction.date >= date_from)
    if date_to:
        query = query.filter(Transaction.date <= date_to)
    if category_id:
        query = query.filter(Transaction.category_id == category_id)
    if payment_method_id:
        query = query.filter(Transaction.payment_method_id == payment_method_id)
    if min_amount is not None:
        query = query.filter(Transaction.amount >= min_amount)
    if max_amount is not None:
        query = query.filter(Transaction.amount <= max_amount)
    if search:
        query = query.filter(Transaction.description.contains(search))
    return query


def _summary(transactions: list[Transaction]) -> dict:
    """Compute income, expense and balance for the given transactions."""
    income = sum(t.amount for t in transactions if t.category.type == TransactionType.INCOME)
    expense = sum(t.amount for t in transactions if t.category.type == TransactionType.EXPENSE)
    return {"income": income, "expense": expense, "balance": income - expense}


def _choices(db: Session, user_id: int) -> dict:
    """The user's own categories and payment methods, for form drop-downs."""
    return {
        "categories": db.query(Category).filter(Category.user_id == user_id).order_by(Category.name).all(),
        "payment_methods": db.query(PaymentMethod)
        .filter(PaymentMethod.user_id == user_id)
        .order_by(PaymentMethod.name)
        .all(),
    }


def _render_table(request: Request, db: Session, user: User, params: dict):
    """Render the table and summary partial using the given filter params."""
    currency = currency_of(request)
    query = _filtered_query(
        db,
        user.id,
        parse_jalali(params.get("date_from")),
        parse_jalali(params.get("date_to")),
        _to_int(params.get("category_id")),
        _to_int(params.get("payment_method_id")),
        # Amount filters are typed in the display unit, the database stores Toman
        to_base(_to_int(params.get("min_amount")), currency),
        to_base(_to_int(params.get("max_amount")), currency),
        params.get("search") or None,
    )
    transactions = query.order_by(Transaction.date.desc(), Transaction.id.desc()).all()
    return templates.TemplateResponse(
        request,
        "partials/table.html",
        {"transactions": transactions, "summary": _summary(transactions)},
    )


def _check_references(db: Session, user_id: int, category_id: int, payment_method_id: int) -> None:
    """Reject a category or payment method that does not belong to this user."""
    if owned(db, Category, category_id, user_id) is None or owned(
        db, PaymentMethod, payment_method_id, user_id
    ) is None:
        raise HTTPException(status_code=400, detail="Invalid category or payment method")


@router.get("/", response_class=HTMLResponse)
def index(request: Request, db: Session = Depends(get_db), user: User = Depends(require_user)):
    """Main page with the filter bar, add form and transactions table."""
    return templates.TemplateResponse(
        request, "index.html", {**_choices(db, user.id), "today": today_jalali_str()}
    )


@router.get("/ui/table", response_class=HTMLResponse)
def table(request: Request, db: Session = Depends(get_db), user: User = Depends(require_user)):
    """Return only the table partial, filtered by the query string."""
    return _render_table(request, db, user, dict(request.query_params))


@router.post("/ui/transactions", response_class=HTMLResponse)
def add_transaction(
    request: Request,
    amount: int = Form(gt=0),
    date: str = Form(...),
    description: str = Form(""),
    payment_method_id: int = Form(...),
    category_id: int = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    """Create a transaction from the form, then return the refreshed table."""
    _check_references(db, user.id, category_id, payment_method_id)
    db.add(
        Transaction(
            user_id=user.id,
            amount=to_base(amount, currency_of(request)),
            date=parse_jalali(date) or dt.date.today(),
            description=description.strip(),
            payment_method_id=payment_method_id,
            category_id=category_id,
        )
    )
    db.commit()
    return _render_table(request, db, user, {})


@router.get("/ui/transactions/{transaction_id}/edit", response_class=HTMLResponse)
def edit_form(
    transaction_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    """Return an inline edit row for one of the user's transactions."""
    transaction = owned(db, Transaction, transaction_id, user.id)
    if not transaction:
        return _render_table(request, db, user, {})
    return templates.TemplateResponse(
        request, "partials/edit_row.html", {"t": transaction, **_choices(db, user.id)}
    )


@router.put("/ui/transactions/{transaction_id}", response_class=HTMLResponse)
def update_transaction(
    transaction_id: int,
    request: Request,
    amount: int = Form(gt=0),
    date: str = Form(...),
    description: str = Form(""),
    payment_method_id: int = Form(...),
    category_id: int = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    """Save the edited transaction, then return the refreshed table."""
    transaction = owned(db, Transaction, transaction_id, user.id)
    if transaction:
        _check_references(db, user.id, category_id, payment_method_id)
        transaction.amount = to_base(amount, currency_of(request))
        transaction.date = parse_jalali(date) or transaction.date
        transaction.description = description.strip()
        transaction.payment_method_id = payment_method_id
        transaction.category_id = category_id
        db.commit()
    return _render_table(request, db, user, {})


@router.delete("/ui/transactions/{transaction_id}", response_class=HTMLResponse)
def delete_transaction(
    transaction_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    """Delete one of the user's transactions, then return the refreshed table."""
    transaction = owned(db, Transaction, transaction_id, user.id)
    if transaction:
        db.delete(transaction)
        db.commit()
    return _render_table(request, db, user, {})
