import calendar
import datetime as dt

from sqlalchemy.orm import Session

from app.models import Frequency, RecurringTransaction, Transaction


def _add_months(base: dt.date, months: int, anchor_day: int) -> dt.date:
    """Add months to a date, clamping the day to the length of the target month."""
    index = base.year * 12 + (base.month - 1) + months
    year, month = divmod(index, 12)
    month += 1
    last_day = calendar.monthrange(year, month)[1]
    return dt.date(year, month, min(anchor_day, last_day))


def next_occurrence(current: dt.date, frequency: Frequency, anchor_day: int) -> dt.date:
    """Return the occurrence that follows the given date."""
    if frequency == Frequency.WEEKLY:
        return current + dt.timedelta(days=7)
    if frequency == Frequency.MONTHLY:
        return _add_months(current, 1, anchor_day)
    return _add_months(current, 12, anchor_day)


def generate_due(db: Session, today: dt.date | None = None) -> int:
    """Create transactions for every due occurrence and return how many were created."""
    today = today or dt.date.today()
    created = 0
    templates = (
        db.query(RecurringTransaction)
        .filter(RecurringTransaction.active.is_(True))
        .all()
    )
    for item in templates:
        # A template that was idle for months catches up one occurrence at a time
        while item.next_date <= today:
            db.add(
                Transaction(
                    amount=item.amount,
                    date=item.next_date,
                    description=item.description,
                    payment_method_id=item.payment_method_id,
                    category_id=item.category_id,
                )
            )
            item.next_date = next_occurrence(
                item.next_date, item.frequency, item.anchor_day)
            created += 1
    db.commit()
    return created
