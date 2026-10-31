from app.database import SessionLocal, Base, engine
from app.models import PaymentMethod, Category, Transaction, TransactionType

Base.metadata.create_all(bind=engine)

db = SessionLocal()

card = PaymentMethod(name="کارت بانکی")
cash = PaymentMethod(name="نقد")
food = Category(name="خوراک", type=TransactionType.EXPENSE)
salary = Category(name="حقوق", type=TransactionType.INCOME)
db.add_all([card, cash, food, salary])
db.commit()

db.add_all([
    Transaction(amount=20_000_000, description="حقوق ماه",
                payment_method=card, category=salary),
    Transaction(amount=350_000, description="خرید هفتگی",
                payment_method=cash, category=food),
])
db.commit()

for t in db.query(Transaction).all():
    print(t.id, t.date, t.category.name,
          t.payment_method.name, t.amount, t.description)

db.close()
