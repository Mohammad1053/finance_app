import datetime as dt
import enum

from sqlalchemy import Date, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

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
    date: Mapped[dt.date] = mapped_column(Date, default=dt.date.today)
    description: Mapped[str] = mapped_column(String(255), default="")

    payment_method_id: Mapped[int] = mapped_column(
        ForeignKey("payment_methods.id"))
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))

    payment_method: Mapped["PaymentMethod"] = relationship(
        back_populates="transactions")
    category: Mapped["Category"] = relationship(back_populates="transactions")


class Goal(Base):
    __tablename__ = "goals"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    target_amount: Mapped[int]  # positive integer, same unit as transactions

    # Deleting a goal also deletes its contributions
    contributions: Mapped[list["GoalContribution"]] = relationship(
        back_populates="goal", cascade="all, delete-orphan"
    )

    @property
    def saved(self) -> int:
        """Total amount contributed so far."""
        return sum(c.amount for c in self.contributions)

    @property
    def percent(self) -> int:
        """Progress as a whole percentage, capped at 100."""
        if self.target_amount <= 0:
            return 0
        return min(100, int(self.saved * 100 / self.target_amount))


class GoalContribution(Base):
    __tablename__ = "goal_contributions"

    id: Mapped[int] = mapped_column(primary_key=True)
    amount: Mapped[int]
    date: Mapped[dt.date] = mapped_column(Date, default=dt.date.today)

    goal_id: Mapped[int] = mapped_column(ForeignKey("goals.id"))
    goal: Mapped["Goal"] = relationship(back_populates="contributions")


class Frequency(str, enum.Enum):
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"


class RecurringTransaction(Base):
    __tablename__ = "recurring_transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    amount: Mapped[int]
    description: Mapped[str] = mapped_column(String(255), default="")
    frequency: Mapped[Frequency] = mapped_column(Enum(Frequency))
    # Date of the next transaction that has not been created yet
    next_date: Mapped[dt.date] = mapped_column(Date)
    # Day of month the schedule is anchored to (avoids drifting after short months)
    anchor_day: Mapped[int] = mapped_column(default=1)
    active: Mapped[bool] = mapped_column(default=True)

    payment_method_id: Mapped[int] = mapped_column(
        ForeignKey("payment_methods.id"))
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))

    payment_method: Mapped["PaymentMethod"] = relationship()
    category: Mapped["Category"] = relationship()
