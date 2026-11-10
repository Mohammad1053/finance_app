from sqlalchemy.orm import Session

from app.models import Category, PaymentMethod, TransactionType, User

DEFAULT_EXPENSE = ["خوراک", "حمل‌ونقل", "اجاره", "قبوض", "سلامت و درمان", "پوشاک", "تفریح", "آموزش", "سایر هزینه‌ها"]
DEFAULT_INCOME = ["حقوق", "درآمد جانبی", "هدیه", "سایر درآمدها"]
DEFAULT_METHODS = ["نقد", "کارت بانکی", "انتقال آنلاین"]


def seed_defaults(db: Session, user: User) -> bool:
    """Create starter categories and payment methods for a user, once.

    Returns True when rows were created.
    """
    if user.defaults_seeded:
        return False

    # Never touch an account that already has its own data
    has_data = (
        db.query(Category).filter(Category.user_id == user.id).count()
        or db.query(PaymentMethod).filter(PaymentMethod.user_id == user.id).count()
    )
    if has_data:
        user.defaults_seeded = True
        db.commit()
        return False

    db.add_all(Category(user_id=user.id, name=n, type=TransactionType.EXPENSE) for n in DEFAULT_EXPENSE)
    db.add_all(Category(user_id=user.id, name=n, type=TransactionType.INCOME) for n in DEFAULT_INCOME)
    db.add_all(PaymentMethod(user_id=user.id, name=n) for n in DEFAULT_METHODS)
    user.defaults_seeded = True
    db.commit()
    return True
