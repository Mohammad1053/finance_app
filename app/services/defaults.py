from sqlalchemy.orm import Session

from app.models import Category, PaymentMethod, TransactionType
from app.services.app_settings import get_settings

DEFAULT_EXPENSE = ["خوراک", "حمل‌ونقل", "اجاره", "قبوض", "سلامت و درمان", "پوشاک", "تفریح", "آموزش", "سایر هزینه‌ها"]
DEFAULT_INCOME = ["حقوق", "درآمد جانبی", "هدیه", "سایر درآمدها"]
DEFAULT_METHODS = ["نقد", "کارت بانکی", "انتقال آنلاین"]


def seed_defaults(db: Session) -> bool:
    """Create starter categories and payment methods once, only on an empty database.

    Returns True when rows were created.
    """
    settings = get_settings(db)
    if settings.defaults_seeded:
        return False

    # Never touch a database that already has the user's own data
    if db.query(Category).count() or db.query(PaymentMethod).count():
        settings.defaults_seeded = True
        db.commit()
        return False

    db.add_all(Category(name=n, type=TransactionType.EXPENSE) for n in DEFAULT_EXPENSE)
    db.add_all(Category(name=n, type=TransactionType.INCOME) for n in DEFAULT_INCOME)
    db.add_all(PaymentMethod(name=n) for n in DEFAULT_METHODS)
    settings.defaults_seeded = True
    db.commit()
    return True
