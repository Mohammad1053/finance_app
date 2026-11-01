import datetime as dt

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.jalali import parse_jalali
from app.models import Transaction
from app.services.csv_io import build_csv, build_xlsx, import_csv
from app.templating import templates

router = APIRouter(include_in_schema=False)

MAX_UPLOAD_BYTES = 2 * 1024 * 1024  # 2 MB is plenty for personal data


def _to_int(value: str | None) -> int | None:
    """Convert a query string value to int; empty or invalid values become None."""
    try:
        return int(value) if value else None
    except ValueError:
        return None


def _filtered(db: Session, params: dict) -> list[Transaction]:
    """Return transactions matching the same filters as the main table."""
    query = db.query(Transaction).options(
        joinedload(Transaction.category), joinedload(
            Transaction.payment_method)
    )
    date_from = parse_jalali(params.get("date_from"))
    date_to = parse_jalali(params.get("date_to"))
    category_id = _to_int(params.get("category_id"))
    method_id = _to_int(params.get("payment_method_id"))
    min_amount = _to_int(params.get("min_amount"))
    max_amount = _to_int(params.get("max_amount"))
    search = params.get("search")

    if date_from:
        query = query.filter(Transaction.date >= date_from)
    if date_to:
        query = query.filter(Transaction.date <= date_to)
    if category_id:
        query = query.filter(Transaction.category_id == category_id)
    if method_id:
        query = query.filter(Transaction.payment_method_id == method_id)
    if min_amount is not None:
        query = query.filter(Transaction.amount >= min_amount)
    if max_amount is not None:
        query = query.filter(Transaction.amount <= max_amount)
    if search:
        query = query.filter(Transaction.description.contains(search))
    return query.order_by(Transaction.date, Transaction.id).all()


def _download(content: bytes, media_type: str, extension: str) -> Response:
    """Wrap file bytes in a download response with a dated filename."""
    name = f"transactions-{dt.date.today().isoformat()}.{extension}"
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


@router.get("/data", response_class=HTMLResponse)
def data_page(request: Request):
    """Import/export page."""
    return templates.TemplateResponse(request, "data.html", {"result": None})


@router.get("/export.csv")
def export_csv(request: Request, db: Session = Depends(get_db)):
    """Download transactions as CSV, honoring the filter query string."""
    rows = _filtered(db, dict(request.query_params))
    return _download(build_csv(rows), "text/csv; charset=utf-8", "csv")


@router.get("/export.xlsx")
def export_xlsx(request: Request, db: Session = Depends(get_db)):
    """Download transactions as Excel, honoring the filter query string."""
    rows = _filtered(db, dict(request.query_params))
    return _download(
        build_xlsx(rows),
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "xlsx",
    )


@router.get("/sample.csv")
def sample_csv():
    """Download a one-row example file showing the expected format."""
    sample = "date,type,category,payment_method,amount,description\n1405/08/10,هزینه,خوراک,نقد,350000,خرید هفتگی\n"
    return _download(sample.encode("utf-8-sig"), "text/csv; charset=utf-8", "csv")


@router.post("/data/import", response_class=HTMLResponse)
async def import_file(
    request: Request, file: UploadFile = File(...), db: Session = Depends(get_db)
):
    """Import transactions from an uploaded CSV file."""
    raw = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(raw) > MAX_UPLOAD_BYTES:
        result = {"count": 0, "errors": ["حجم فایل بیشتر از ۲ مگابایت است."]}
    else:
        count, errors = import_csv(db, raw)
        result = {"count": count, "errors": errors}
    return templates.TemplateResponse(request, "data.html", {"result": result})
