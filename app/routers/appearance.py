from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import current_user_optional, require_user
from app.models import User
from app.services import auth
from app.services.app_settings import CURRENCIES, THEMES
from app.services.defaults import seed_defaults
from app.templating import templates

router = APIRouter(include_in_schema=False)

THEME_CHOICES = [("light", "روشن"), ("dark", "تاریک"), ("system", "پیش‌فرض سیستم")]
CURRENCY_CHOICES = [("toman", "تومان"), ("rial", "ریال")]

# Put the invitation link here when you have it; while empty the button is disabled
INVITE_URL = ""

MESSAGES = {
    "settings": "تنظیمات ذخیره شد.",
    "name": "نام ذخیره شد.",
    "password": "رمز عبور تغییر کرد. دستگاه‌های دیگر از حساب خارج شدند.",
}


def _is_https(request: Request) -> bool:
    """True when the visitor reached us over HTTPS (directly or through a proxy)."""
    forwarded = request.headers.get("x-forwarded-proto", "").split(",")[0].strip()
    return request.url.scheme == "https" or forwarded == "https"


def _set_login_cookie(request: Request, response, user: User) -> None:
    """Attach the signed session cookie to a response."""
    response.set_cookie(
        auth.COOKIE_NAME,
        auth.session_token(user),
        max_age=auth.SESSION_DAYS * 86400,
        httponly=True,
        samesite="lax",
        secure=_is_https(request),
    )


def _client_key(request: Request, username: str) -> str:
    """Key for the login throttle: username plus the visitor's address."""
    forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    ip = forwarded or (request.client.host if request.client else "")
    return f"{username}|{ip}"


def _auth_page(request: Request, template: str, error: str = "", form=None, status_code: int = 200):
    """Render the login or register page."""
    return templates.TemplateResponse(
        request, template, {"error": error, "form": form or {}}, status_code=status_code
    )


def _appearance(request: Request, user: User, message: str = "", error: str = ""):
    """Render the account/appearance page with an optional success or error message."""
    return templates.TemplateResponse(
        request,
        "appearance.html",
        {
            "themes": THEME_CHOICES,
            "currencies": CURRENCY_CHOICES,
            "invite_url": INVITE_URL,
            "message": message,
            "error": error,
        },
    )


# ---------- Register ----------
@router.get("/register", response_class=HTMLResponse)
def register_page(request: Request, user: User | None = Depends(current_user_optional)):
    """Sign-up form; signed-in users go to the main page."""
    if user:
        return RedirectResponse("/", status_code=303)
    return _auth_page(request, "register.html")


@router.post("/register", response_class=HTMLResponse)
def register(
    request: Request,
    first_name: str = Form(""),
    last_name: str = Form(""),
    username: str = Form(""),
    password: str = Form(""),
    confirm_password: str = Form(""),
    db: Session = Depends(get_db),
    current: User | None = Depends(current_user_optional),
):
    """Create an account, give it starter categories and sign the visitor in."""
    first, last = first_name.strip()[:100], last_name.strip()[:100]
    uname = auth.normalize_username(username)
    form = {"first_name": first, "last_name": last, "username": uname}

    error = ""
    if not first or not last:
        error = "نام و نام خانوادگی هر دو لازم هستند."
    elif not auth.USERNAME_RE.match(uname):
        error = "نام کاربری باید ۳ تا ۳۰ نویسه و فقط شامل حروف انگلیسی کوچک، عدد، _ و . باشد."
    elif len(password) < auth.MIN_PASSWORD_LENGTH:
        error = f"رمز عبور باید حداقل {auth.MIN_PASSWORD_LENGTH} نویسه باشد."
    elif password != confirm_password:
        error = "رمز عبور و تکرار آن یکسان نیستند."
    elif db.query(User).filter(User.username == uname).first():
        error = "این نام کاربری قبلاً گرفته شده است."
    if error:
        return _auth_page(request, "register.html", error, form, status_code=400)

    user = User(
        username=uname,
        first_name=first,
        last_name=last,
        password_hash=auth.hash_password(password),
        session_secret=auth.new_secret(),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()  # two people picked the same name at the same moment
        return _auth_page(
            request, "register.html", "این نام کاربری قبلاً گرفته شده است.", form, status_code=400
        )
    seed_defaults(db, user)

    response = RedirectResponse("/", status_code=303)
    _set_login_cookie(request, response, user)
    return response


# ---------- Login / logout ----------
@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, user: User | None = Depends(current_user_optional)):
    """Login form; signed-in users go to the main page."""
    if user:
        return RedirectResponse("/", status_code=303)
    return _auth_page(request, "login.html")


@router.post("/login", response_class=HTMLResponse)
def login(
    request: Request,
    username: str = Form(""),
    password: str = Form(""),
    db: Session = Depends(get_db),
    current: User | None = Depends(current_user_optional),
):
    """Check the credentials and start a session."""
    uname = auth.normalize_username(username)
    form = {"username": uname}
    key = _client_key(request, uname)

    if auth.throttle.is_blocked(key):
        return _auth_page(
            request, "login.html", "تلاش‌های ناموفق زیاد بود. چند دقیقه بعد دوباره امتحان کنید.",
            form, status_code=429,
        )

    user = db.query(User).filter(User.username == uname).first()
    valid = auth.verify_password(password, user.password_hash if user else auth.DUMMY_HASH)
    if user is None or not valid:
        auth.throttle.register_failure(key)
        return _auth_page(request, "login.html", "نام کاربری یا رمز عبور اشتباه است.", form, status_code=401)

    auth.throttle.reset(key)
    response = RedirectResponse("/", status_code=303)
    _set_login_cookie(request, response, user)
    return response


@router.get("/logout")
def logout():
    """End the session on this device."""
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie(auth.COOKIE_NAME)
    return response


# ---------- Appearance and account ----------
@router.get("/appearance", response_class=HTMLResponse)
def appearance_page(request: Request, saved: str = "", user: User = Depends(require_user)):
    """Appearance and account settings page."""
    return _appearance(request, user, message=MESSAGES.get(saved, ""))


@router.post("/appearance")
def save_appearance(
    theme: str = Form(...),
    currency: str = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    """Save theme and currency; unknown values are ignored."""
    if theme in THEMES:
        user.theme = theme
    if currency in CURRENCIES:
        user.currency = currency
    db.commit()
    return RedirectResponse("/appearance?saved=settings", status_code=303)


@router.post("/appearance/name")
def save_name(
    request: Request,
    first_name: str = Form(""),
    last_name: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    """Change the user's first and last name."""
    first, last = first_name.strip()[:100], last_name.strip()[:100]
    if not first or not last:
        return _appearance(request, user, error="نام و نام خانوادگی هر دو لازم هستند.")
    user.first_name, user.last_name = first, last
    db.commit()
    return RedirectResponse("/appearance?saved=name", status_code=303)


@router.post("/appearance/password")
def save_password(
    request: Request,
    current_password: str = Form(""),
    new_password: str = Form(""),
    confirm_password: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    """Change the password; every other device is signed out."""
    if not auth.verify_password(current_password, user.password_hash):
        return _appearance(request, user, error="رمز فعلی اشتباه است.")
    if len(new_password) < auth.MIN_PASSWORD_LENGTH:
        return _appearance(
            request, user, error=f"رمز جدید باید حداقل {auth.MIN_PASSWORD_LENGTH} نویسه باشد."
        )
    if new_password != confirm_password:
        return _appearance(request, user, error="رمز جدید و تکرار آن یکسان نیستند.")

    user.password_hash = auth.hash_password(new_password)
    user.session_secret = auth.new_secret()  # invalidates all old cookies
    db.commit()

    response = RedirectResponse("/appearance?saved=password", status_code=303)
    _set_login_cookie(request, response, user)  # keep this browser signed in
    return response
