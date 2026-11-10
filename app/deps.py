from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.services import auth
from app.services.app_settings import snapshot


def current_user_optional(request: Request, db: Session = Depends(get_db)) -> User | None:
    """Return the logged-in user (or None) and expose the profile to templates."""
    token = request.cookies.get(auth.COOKIE_NAME, "")
    user = auth.user_from_token(db, token) if token else None
    request.state.user = user
    request.state.settings = snapshot(user) if user else None
    request.state.auth_enabled = user is not None  # templates show the logout link
    return user


def require_user(request: Request, user: User | None = Depends(current_user_optional)) -> User:
    """Return the logged-in user, or send the visitor to the login page."""
    if user is not None:
        return user
    # Full page loads are redirected; HTMX and other calls get a 401
    if request.method == "GET" and "hx-request" not in request.headers:
        raise HTTPException(status_code=303, headers={"Location": "/login"})
    raise HTTPException(status_code=401, detail="Login required", headers={"HX-Redirect": "/login"})


def currency_of(request: Request) -> str:
    """Return the selected currency ('toman' or 'rial') for this request."""
    settings = getattr(request.state, "settings", None)
    return settings.currency if settings else "toman"
