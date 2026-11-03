from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import load_settings, require_profile
from app.services.app_settings import CURRENCIES, THEMES, get_settings
from app.templating import templates

router = APIRouter(include_in_schema=False)

THEME_CHOICES = [("light", "روشن"), ("dark", "تاریک"),
                 ("system", "پیش‌فرض سیستم")]
CURRENCY_CHOICES = [("toman", "تومان"), ("rial", "ریال")]


@router.get("/welcome", response_class=HTMLResponse, dependencies=[Depends(load_settings)])
def welcome_page(request: Request):
    """Registration-style page asking for the user's name (also used to edit it)."""
    return templates.TemplateResponse(request, "welcome.html", {"error": ""})


@router.post("/welcome", response_class=HTMLResponse, dependencies=[Depends(load_settings)])
def save_profile(
    request: Request,
    first_name: str = Form(""),
    last_name: str = Form(""),
    db: Session = Depends(get_db),
):
    """Save the name, then continue to the main page."""
    first, last = first_name.strip()[:100], last_name.strip()[:100]
    if not first or not last:
        return templates.TemplateResponse(
            request, "welcome.html", {
                "error": "نام و نام خانوادگی هر دو لازم هستند."}
        )
    row = get_settings(db)
    row.first_name, row.last_name = first, last
    db.commit()
    return RedirectResponse("/", status_code=303)


@router.get("/appearance", response_class=HTMLResponse, dependencies=[Depends(require_profile)])
def appearance_page(request: Request, saved: str = ""):
    """Theme and currency settings page."""
    return templates.TemplateResponse(
        request,
        "appearance.html",
        {"themes": THEME_CHOICES, "currencies": CURRENCY_CHOICES,
            "saved": bool(saved)},
    )


@router.post("/appearance", dependencies=[Depends(require_profile)])
def save_appearance(
    theme: str = Form(...), currency: str = Form(...), db: Session = Depends(get_db)
):
    """Save theme and currency; unknown values are ignored."""
    row = get_settings(db)
    if theme in THEMES:
        row.theme = theme
    if currency in CURRENCIES:
        row.currency = currency
    db.commit()
    # Redirect so the page reloads with the new theme applied
    return RedirectResponse("/appearance?saved=1", status_code=303)
