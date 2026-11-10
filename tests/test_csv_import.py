from app.models import Transaction
from app.services.csv_io import _normalize, build_csv, import_csv

HEADER = "date,type,category,payment_method,amount,description\n"


def csv_bytes(*lines: str) -> bytes:
    """Build CSV bytes (with BOM, like a real export) from data lines."""
    return (HEADER + "\n".join(lines) + "\n").encode("utf-8-sig")


def test_normalize_unifies_spaces_zwnj_and_arabic_letters():
    assert _normalize("حمل‌ونقل") == _normalize(
        "حمل ونقل") == _normalize("حملونقل")
    assert _normalize("خوراك") == _normalize(
        "خوراک")  # Arabic kaf vs Persian kaf
    assert _normalize("  نقد ") == _normalize("نقد")


def test_valid_file_is_imported(db_session, seed):
    raw = csv_bytes(
        "1405/08/03,هزینه,خوراک,نقد,350000,خرید هفتگی",
        "1405/08/01,درآمد,حقوق,کارت بانکی,20000000,حقوق آبان",
    )
    count, errors = import_csv(db_session, seed.user_id, raw)

    assert (count, errors) == (2, [])
    assert db_session.query(Transaction).count() == 2


def test_names_are_matched_loosely(db_session, seed):
    # Arabic kaf + double space
    raw = csv_bytes("1405/08/03,هزینه,خوراك,کارت  بانکی,350000,x")
    count, errors = import_csv(db_session, seed.user_id, raw)
    assert (count, errors) == (1, [])


def test_persian_digits_in_amount(db_session, seed):
    raw = csv_bytes("1405/08/03,هزینه,خوراک,نقد,۳۵۰۰۰۰,x")
    import_csv(db_session, seed.user_id, raw)
    assert db_session.query(Transaction).one().amount == 350000


def test_jalali_date_is_stored_as_gregorian(db_session, seed):
    import datetime as dt

    import_csv(db_session, seed.user_id, csv_bytes("1405/08/03,هزینه,خوراک,نقد,1000,x"))
    assert db_session.query(Transaction).one().date == dt.date(2026, 10, 25)


def test_any_bad_row_saves_nothing(db_session, seed):
    raw = csv_bytes(
        "1405/08/01,درآمد,حقوق,کارت بانکی,20000000,ردیف درست",
        "1405/13/40,هزینه,خوراک,نقد,350000,تاریخ نامعتبر",
        "1405/08/05,هزینه,دسته‌ی ناموجود,نقد,120000,دسته اشتباه",
        "1405/08/07,هزینه,خوراک,روش ناموجود,480000,روش اشتباه",
        "1405/08/09,هزینه,خوراک,نقد,abc,مبلغ نامعتبر",
    )
    count, errors = import_csv(db_session, seed.user_id, raw)

    assert count == 0
    assert len(errors) == 4
    assert "3" in errors[0] and "تاریخ" in errors[0]
    assert "4" in errors[1] and "دسته" in errors[1]
    assert "5" in errors[2] and "روش پرداخت" in errors[2]
    assert "6" in errors[3] and "مبلغ" in errors[3]
    # The valid first row must not have been saved either
    assert db_session.query(Transaction).count() == 0


def test_missing_columns_are_reported(db_session, seed):
    raw = "date,category,amount\n1405/08/01,خوراک,350000\n".encode("utf-8-sig")
    count, errors = import_csv(db_session, seed.user_id, raw)
    assert count == 0
    assert "type" in errors[0] and "payment_method" in errors[0]


def test_header_only_file_is_rejected(db_session, seed):
    count, errors = import_csv(db_session, seed.user_id, csv_bytes())
    assert count == 0
    assert errors


def test_export_has_bom_header_and_jalali_dates(db_session, seed):
    import datetime as dt

    db_session.add(
        Transaction(
            amount=350000,
            date=dt.date(2026, 10, 25),
            description="خرید",
            user_id=seed.user_id, payment_method_id=seed.cash_id,
            category_id=seed.food_id,
        )
    )
    db_session.commit()

    data = build_csv(db_session.query(Transaction).all())
    # BOM so Excel reads Persian correctly
    assert data.startswith(b"\xef\xbb\xbf")
    text = data.decode("utf-8-sig")
    assert text.splitlines()[
        0] == "date,type,category,payment_method,amount,description"
    assert "1405/08/03" in text and "350000" in text
