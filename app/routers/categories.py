from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.database import get_db
from app.models import Category, TransactionType
from app.schemas import CategoryCreate, CategoryRead

router = APIRouter(prefix="/categories", tags=["Categories"])


@router.post("/", response_model=CategoryRead, status_code=status.HTTP_201_CREATED)
def create_category(data: CategoryCreate, db: Session = Depends(get_db)):
    category = Category(name=data.name, type=data.type)
    db.add(category)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="این دسته قبلاً ثبت شده")
    db.refresh(category)
    return category


@router.get("/", response_model=list[CategoryRead])
def list_categories(type: TransactionType | None = None, db: Session = Depends(get_db)):
    query = db.query(Category)
    if type:
        query = query.filter(Category.type == type)
    return query.order_by(Category.name).all()


@router.put("/{category_id}", response_model=CategoryRead)
def update_category(category_id: int, data: CategoryCreate, db: Session = Depends(get_db)):
    category = db.get(Category, category_id)
    if not category:
        raise HTTPException(status_code=404, detail="دسته پیدا نشد")
    category.name = data.name
    category.type = data.type
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="این نام قبلاً استفاده شده")
    db.refresh(category)
    return category


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(category_id: int, db: Session = Depends(get_db)):
    category = db.get(Category, category_id)
    if not category:
        raise HTTPException(status_code=404, detail="دسته پیدا نشد")
    if category.transactions:
        raise HTTPException(
            status_code=409,
            detail="این دسته در تراکنش‌ها استفاده شده و قابل حذف نیست",
        )
    db.delete(category)
    db.commit()
