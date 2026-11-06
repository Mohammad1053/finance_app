from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.app_settings import SettingsView, get_settings, snapshot
from app.services.auth import COOKIE_NAME, get_auth, is_authenticated, password_enabled


def load_settings(request: Request, db: Session = Depends(get_db)) -> SettingsView:
    """Load the settings and expose them to templates through request.state."""
    view = snapshot(get_settings(db))
    request.state.settings = view
    return view


def require_profile(
    request: Request, settings: SettingsView = Depends(load_settings)
) -> None:
    """Send first-time users to /welcome when they open a full page."""
    # HTMX partial requests carry the HX-Request header and must not be redirected
    is_page_load = request.method == "GET" and "hx-request" not in request.headers
    if is_page_load and not settings.first_name:
        raise HTTPException(status_code=307, headers={"Location": "/welcome"})


def currency_of(request: Request) -> str:
    """Return the selected currency ('toman' or 'rial') for this request."""
    settings = getattr(request.state, "settings", None)
    return settings.currency if settings else "toman"


PUBLIC_PATHS = {"/login", "/service-worker.js"}


def require_login(request: Request, db: Session = Depends(get_db)) -> None:
    """Block everything except /login when a password is set and the user is not logged in."""
    row = get_auth(db)
    enabled = password_enabled(row)
    # used by templates to show the logout link
    request.state.auth_enabled = enabled
    if not enabled or request.url.path in PUBLIC_PATHS or request.url.path.startswith("/static/"):
        return
    if is_authenticated(row, request.cookies.get(COOKIE_NAME, "")):
        return
    # Full page loads go to the login page; HTMX and API calls get a 401
    if request.method == "GET" and "hx-request" not in request.headers:
        raise HTTPException(status_code=303, headers={"Location": "/login"})
    raise HTTPException(status_code=401, detail="Login required", headers={
                        "HX-Redirect": "/login"})
