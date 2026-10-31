from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.database import get_db
from app.models import PaymentMethod
from app.schemas import PaymentMethodCreate, PaymentMethodRead

router = APIRouter(prefix="/payment-methods", tags=["Payment Methods"])


@router.post("/", response_model=PaymentMethodRead, status_code=status.HTTP_201_CREATED)
def create_payment_method(data: PaymentMethodCreate, db: Session = Depends(get_db)):
    pm = PaymentMethod(name=data.name)
    db.add(pm)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="این روش پرداخت قبلاً ثبت شده")
    db.refresh(pm)
    return pm


@router.get("/", response_model=list[PaymentMethodRead])
def list_payment_methods(db: Session = Depends(get_db)):
    return db.query(PaymentMethod).order_by(PaymentMethod.name).all()


@router.put("/{pm_id}", response_model=PaymentMethodRead)
def update_payment_method(pm_id: int, data: PaymentMethodCreate, db: Session = Depends(get_db)):
    pm = db.get(PaymentMethod, pm_id)
    if not pm:
        raise HTTPException(status_code=404, detail="روش پرداخت پیدا نشد")
    pm.name = data.name
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="این نام قبلاً استفاده شده")
    db.refresh(pm)
    return pm


@router.delete("/{pm_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_payment_method(pm_id: int, db: Session = Depends(get_db)):
    pm = db.get(PaymentMethod, pm_id)
    if not pm:
        raise HTTPException(status_code=404, detail="روش پرداخت پیدا نشد")
    if pm.transactions:
        raise HTTPException(
            status_code=409,
            detail="این روش پرداخت در تراکنش‌ها استفاده شده و قابل حذف نیست",
        )
    db.delete(pm)
    db.commit()
