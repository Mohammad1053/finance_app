from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import Transaction, Category, PaymentMethod
from app.schemas import TransactionCreate, TransactionRead, TransactionUpdate

router = APIRouter(prefix="/transactions", tags=["Transactions"])


def _check_references(db: Session, payment_method_id: int | None, category_id: int | None):
    """مطمئن می‌شه روش پرداخت و دسته‌ای که کاربر فرستاده واقعاً وجود دارن"""
    if payment_method_id is not None and not db.get(PaymentMethod, payment_method_id):
        raise HTTPException(status_code=404, detail="روش پرداخت پیدا نشد")
    if category_id is not None and not db.get(Category, category_id):
        raise HTTPException(status_code=404, detail="دسته پیدا نشد")


@router.post("/", response_model=TransactionRead, status_code=status.HTTP_201_CREATED)
def create_transaction(data: TransactionCreate, db: Session = Depends(get_db)):
    _check_references(db, data.payment_method_id, data.category_id)
    transaction = Transaction(**data.model_dump())
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    return transaction


@router.get("/", response_model=list[TransactionRead])
def list_transactions(
    date_from: date | None = None,
    date_to: date | None = None,
    category_id: int | None = None,
    payment_method_id: int | None = None,
    min_amount: int | None = Query(default=None, ge=0),
    max_amount: int | None = Query(default=None, ge=0),
    search: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(Transaction).options(
        joinedload(Transaction.category),
        joinedload(Transaction.payment_method),
    )

    if date_from:
        query = query.filter(Transaction.date >= date_from)
    if date_to:
        query = query.filter(Transaction.date <= date_to)
    if category_id:
        query = query.filter(Transaction.category_id == category_id)
    if payment_method_id:
        query = query.filter(
            Transaction.payment_method_id == payment_method_id)
    if min_amount is not None:
        query = query.filter(Transaction.amount >= min_amount)
    if max_amount is not None:
        query = query.filter(Transaction.amount <= max_amount)
    if search:
        query = query.filter(Transaction.description.contains(search))

    return query.order_by(Transaction.date.desc(), Transaction.id.desc()).all()


@router.get("/{transaction_id}", response_model=TransactionRead)
def get_transaction(transaction_id: int, db: Session = Depends(get_db)):
    transaction = db.get(Transaction, transaction_id)
    if not transaction:
        raise HTTPException(status_code=404, detail="تراکنش پیدا نشد")
    return transaction


@router.patch("/{transaction_id}", response_model=TransactionRead)
def update_transaction(
    transaction_id: int, data: TransactionUpdate, db: Session = Depends(get_db)
):
    transaction = db.get(Transaction, transaction_id)
    if not transaction:
        raise HTTPException(status_code=404, detail="تراکنش پیدا نشد")

    changes = data.model_dump(exclude_unset=True)
    _check_references(db, changes.get("payment_method_id"),
                      changes.get("category_id"))

    for field, value in changes.items():
        setattr(transaction, field, value)

    db.commit()
    db.refresh(transaction)
    return transaction


@router.delete("/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_transaction(transaction_id: int, db: Session = Depends(get_db)):
    transaction = db.get(Transaction, transaction_id)
    if not transaction:
        raise HTTPException(status_code=404, detail="تراکنش پیدا نشد")
    db.delete(transaction)
    db.commit()
