from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import load_settings, require_profile
from app.models import AuthSettings
from app.services import auth
from app.services.app_settings import CURRENCIES, THEMES, get_settings
from app.templating import templates

router = APIRouter(include_in_schema=False)

THEME_CHOICES = [("light", "روشن"), ("dark", "تاریک"), ("system", "پیش‌فرض سیستم")]
CURRENCY_CHOICES = [("toman", "تومان"), ("rial", "ریال")]

# Put the invitation link here when you have it; while empty the button is disabled
INVITE_URL = ""

MESSAGES = {
    "settings": "تنظیمات ذخیره شد.",
    "name": "نام ذخیره شد.",
    "password": "رمز عبور ذخیره شد.",
    "password_removed": "رمز عبور حذف شد.",
}


def _set_login_cookie(request: Request, response, row: AuthSettings) -> None:
    """Attach the signed session cookie to a response."""
    response.set_cookie(
        auth.COOKIE_NAME,
        auth.session_token(row),
        max_age=auth.SESSION_DAYS * 86400,
        httponly=True,
        samesite="lax",
        secure=request.url.scheme == "https",
    )


def _appearance(request: Request, db: Session, message: str = "", error: str = ""):
    """Render the appearance page with an optional success or error message."""
    return templates.TemplateResponse(
        request,
        "appearance.html",
        {
            "themes": THEME_CHOICES,
            "currencies": CURRENCY_CHOICES,
            "has_password": auth.password_enabled(auth.get_auth(db)),
            "invite_url": INVITE_URL,
            "message": message,
            "error": error,
        },
    )


# ---------- Welcome / profile ----------
@router.get("/welcome", response_class=HTMLResponse, dependencies=[Depends(load_settings)])
def welcome_page(request: Request):
    """Registration-style page asking for the user's name."""
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
            request, "welcome.html", {"error": "نام و نام خانوادگی هر دو لازم هستند."}
        )
    row = get_settings(db)
    row.first_name, row.last_name = first, last
    db.commit()
    return RedirectResponse("/", status_code=303)


# ---------- Login / logout ----------
@router.get("/login", response_class=HTMLResponse, dependencies=[Depends(load_settings)])
def login_page(request: Request, db: Session = Depends(get_db)):
    """Password prompt; users who do not need it are sent to the main page."""
    row = auth.get_auth(db)
    if not auth.password_enabled(row) or auth.is_authenticated(
        row, request.cookies.get(auth.COOKIE_NAME, "")
    ):
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(request, "login.html", {"error": ""})


@router.post("/login", response_class=HTMLResponse, dependencies=[Depends(load_settings)])
def login(request: Request, password: str = Form(""), db: Session = Depends(get_db)):
    """Check the password and start a session."""
    row = auth.get_auth(db)
    if not auth.password_enabled(row):
        return RedirectResponse("/", status_code=303)
    if not auth.verify_password(password, row.password_hash):
        return templates.TemplateResponse(
            request, "login.html", {"error": "رمز عبور اشتباه است."}, status_code=401
        )
    response = RedirectResponse("/", status_code=303)
    _set_login_cookie(request, response, row)
    return response


@router.get("/logout")
def logout():
    """End the session."""
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie(auth.COOKIE_NAME)
    return response


# ---------- Appearance ----------
@router.get("/appearance", response_class=HTMLResponse, dependencies=[Depends(require_profile)])
def appearance_page(request: Request, saved: str = "", db: Session = Depends(get_db)):
    """Appearance and account settings page."""
    return _appearance(request, db, message=MESSAGES.get(saved, ""))


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
    return RedirectResponse("/appearance?saved=settings", status_code=303)


@router.post("/appearance/name", dependencies=[Depends(require_profile)])
def save_name(
    request: Request,
    first_name: str = Form(""),
    last_name: str = Form(""),
    db: Session = Depends(get_db),
):
    """Change the user's first and last name."""
    first, last = first_name.strip()[:100], last_name.strip()[:100]
    if not first or not last:
        return _appearance(request, db, error="نام و نام خانوادگی هر دو لازم هستند.")
    row = get_settings(db)
    row.first_name, row.last_name = first, last
    db.commit()
    return RedirectResponse("/appearance?saved=name", status_code=303)


@router.post("/appearance/password", dependencies=[Depends(require_profile)])
def save_password(
    request: Request,
    current_password: str = Form(""),
    new_password: str = Form(""),
    confirm_password: str = Form(""),
    db: Session = Depends(get_db),
):
    """Set or change the app password."""
    row = auth.get_auth(db)
    if auth.password_enabled(row) and not auth.verify_password(current_password, row.password_hash):
        return _appearance(request, db, error="رمز فعلی اشتباه است.")
    if len(new_password) < auth.MIN_PASSWORD_LENGTH:
        return _appearance(
            request, db, error=f"رمز جدید باید حداقل {auth.MIN_PASSWORD_LENGTH} نویسه باشد."
        )
    if new_password != confirm_password:
        return _appearance(request, db, error="رمز جدید و تکرار آن یکسان نیستند.")

    auth.set_password(db, row, new_password)
    response = RedirectResponse("/appearance?saved=password", status_code=303)
    _set_login_cookie(request, response, row)  # keep this browser logged in
    return response


@router.post("/appearance/password/remove", dependencies=[Depends(require_profile)])
def remove_password(
    request: Request, current_password: str = Form(""), db: Session = Depends(get_db)
):
    """Remove the app password after confirming the current one."""
    row = auth.get_auth(db)
    if auth.password_enabled(row) and not auth.verify_password(current_password, row.password_hash):
        return _appearance(request, db, error="رمز فعلی اشتباه است.")
    auth.clear_password(db, row)
    response = RedirectResponse("/appearance?saved=password_removed", status_code=303)
    response.delete_cookie(auth.COOKIE_NAME)
    return response
