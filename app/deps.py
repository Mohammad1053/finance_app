from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.app_settings import SettingsView, get_settings, snapshot


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
