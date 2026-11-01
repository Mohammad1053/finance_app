import csv
import io

from sqlalchemy.orm import Session

from app.jalali import ASCII_DIGITS, parse_jalali, to_jalali_str
from app.models import Category, PaymentMethod, Transaction

HEADERS = ["date", "type", "category",
           "payment_method", "amount", "description"]
TYPE_LABELS = {"income": "درآمد", "expense": "هزینه"}


def _normalize(name: str | None) -> str:
    """Normalize a name for matching: unify Arabic/Persian letters and drop spaces and ZWNJ."""
    text = (name or "").strip()
    text = text.replace("ي", "ی").replace("ك", "ک")
    text = text.replace("\u200c", "").replace(" ", "")
    return text.casefold()


def transaction_rows(transactions: list[Transaction]) -> list[list]:
    """Convert transactions to plain rows: Jalali date, type, names, integer amount."""
    return [
        [
            to_jalali_str(t.date, persian_digits=False),
            TYPE_LABELS[t.category.type.value],
            t.category.name,
            t.payment_method.name,
            t.amount,
            t.description,
        ]
        for t in transactions
    ]


def build_csv(transactions: list[Transaction]) -> bytes:
    """Build a UTF-8 CSV (with BOM so Excel shows Persian text correctly)."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(HEADERS)
    writer.writerows(transaction_rows(transactions))
    return buffer.getvalue().encode("utf-8-sig")


def build_xlsx(transactions: list[Transaction]) -> bytes:
    """Build an Excel workbook with one sheet of transactions."""
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "Transactions"
    ws.sheet_view.rightToLeft = True
    ws.append(HEADERS)
    for row in transaction_rows(transactions):
        ws.append(row)
    for column, width in zip("ABCDEF", (14, 10, 22, 18, 16, 40)):
        ws.column_dimensions[column].width = width
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


def _parse_amount(text: str) -> int | None:
    """Parse an amount that may contain separators or Persian digits."""
    cleaned = (text or "").strip().translate(ASCII_DIGITS)
    cleaned = "".join(ch for ch in cleaned if ch.isdigit())
    return int(cleaned) if cleaned else None


def import_csv(db: Session, raw: bytes) -> tuple[int, list[str]]:
    """Import transactions from CSV bytes; return (created_count, error_messages).

    Rows are all-or-nothing per file: nothing is saved if any row is invalid.
    Categories and payment methods must already exist.
    """
    text = raw.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))

    missing = [h for h in HEADERS if h not in (reader.fieldnames or [])]
    if missing:
        return 0, [f"ستون‌های لازم در فایل نیست: {', '.join(missing)}"]

    categories = {_normalize(c.name): c for c in db.query(Category).all()}
    methods = {_normalize(p.name): p for p in db.query(PaymentMethod).all()}

    errors: list[str] = []
    to_add: list[Transaction] = []

    # Line 1 is the header, so data starts at line 2
    for line, row in enumerate(reader, start=2):
        date = parse_jalali(row.get("date"))
        amount = _parse_amount(row.get("amount", ""))
        category = categories.get(_normalize(row.get("category")))
        method = methods.get(_normalize(row.get("payment_method")))

        problems = []
        if date is None:
            problems.append("تاریخ نامعتبر")
        if not amount or amount <= 0:
            problems.append("مبلغ نامعتبر")
        if category is None:
            problems.append("دسته پیدا نشد")
        if method is None:
            problems.append("روش پرداخت پیدا نشد")
        if problems:
            errors.append(f"خط {line}: {'، '.join(problems)}")
            continue

        to_add.append(
            Transaction(
                amount=amount,
                date=date,
                description=(row.get("description") or "").strip()[:255],
                category_id=category.id,
                payment_method_id=method.id,
            )
        )

    if errors:
        return 0, errors[:20]
    if not to_add:
        return 0, ["فایل هیچ ردیفی ندارد."]

    db.add_all(to_add)
    db.commit()
    return len(to_add), []
