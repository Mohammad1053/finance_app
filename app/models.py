from datetime import date
from sqlalchemy import String, ForeignKey, Date, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.database import Base


class TransactionType(str, enum.Enum):
    INCOME = "income"
    EXPENSE = "expense"


class PaymentMethod(Base):
    __tablename__ = "payment_methods"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)

    transactions: Mapped[list["Transaction"]] = relationship(
        back_populates="payment_method")


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    type: Mapped[TransactionType] = mapped_column(Enum(TransactionType))

    transactions: Mapped[list["Transaction"]
                         ] = relationship(back_populates="category")


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    amount: Mapped[int]  # عدد صحیح، به تومان
    date: Mapped[date] = mapped_column(Date, default=date.today)
    description: Mapped[str] = mapped_column(String(255), default="")

    payment_method_id: Mapped[int] = mapped_column(
        ForeignKey("payment_methods.id"))
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))

    payment_method: Mapped["PaymentMethod"] = relationship(
        back_populates="transactions")
    category: Mapped["Category"] = relationship(back_populates="transactions")
