import datetime as dt

from pydantic import BaseModel, ConfigDict, Field

from app.models import TransactionType


# ---------- PaymentMethod ----------
class PaymentMethodCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class PaymentMethodRead(PaymentMethodCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int


# ---------- Category ----------
class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    type: TransactionType


class CategoryRead(CategoryCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int


# ---------- Transaction ----------
class TransactionCreate(BaseModel):
    amount: int = Field(gt=0, description="مبلغ به تومان، عدد صحیح مثبت")
    date: dt.date = Field(default_factory=dt.date.today)
    description: str = Field(default="", max_length=255)
    payment_method_id: int
    category_id: int


class TransactionUpdate(BaseModel):
    """همه‌ی فیلدها اختیاری‌ان تا بشه فقط بخشی رو ویرایش کرد"""
    amount: int | None = Field(default=None, gt=0)
    date: dt.date | None = None
    description: str | None = Field(default=None, max_length=255)
    payment_method_id: int | None = None
    category_id: int | None = None


class TransactionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    amount: int
    date: dt.date
    description: str
    payment_method: PaymentMethodRead
    category: CategoryRead
