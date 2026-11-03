import hashlib
import hmac
import secrets

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import AuthSettings

COOKIE_NAME = "session"
MIN_PASSWORD_LENGTH = 6
SESSION_DAYS = 30

# scrypt cost parameters (about 16 MB of memory per hash)
_N, _R, _P = 2**14, 8, 1


def hash_password(password: str) -> str:
    """Return 'scrypt$salt$hash' for the given password."""
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=_N, r=_R, p=_P)
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """Check a password against a stored hash in constant time."""
    try:
        scheme, salt_hex, digest_hex = stored.split("$")
        if scheme != "scrypt":
            return False
        digest = hashlib.scrypt(
            password.encode(), salt=bytes.fromhex(salt_hex), n=_N, r=_R, p=_P
        )
    except ValueError:
        return False
    return hmac.compare_digest(digest.hex(), digest_hex)


def get_auth(db: Session) -> AuthSettings:
    """Return the auth row, creating an empty one (no password) on first use."""
    row = db.get(AuthSettings, 1)
    if row is None:
        row = AuthSettings(id=1, password_hash="", secret="")
        db.add(row)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            row = db.get(AuthSettings, 1)
    return row


def password_enabled(row: AuthSettings) -> bool:
    """True when the user has set a password."""
    return bool(row.password_hash)


def set_password(db: Session, row: AuthSettings, password: str) -> None:
    """Store a new password and rotate the secret so old sessions stop working."""
    row.password_hash = hash_password(password)
    row.secret = secrets.token_hex(32)
    db.commit()


def clear_password(db: Session, row: AuthSettings) -> None:
    """Remove the password; the app becomes open again."""
    row.password_hash = ""
    row.secret = ""
    db.commit()


def session_token(row: AuthSettings) -> str:
    """Return the cookie value that proves a successful login."""
    return hmac.new(row.secret.encode(), b"session-v1", hashlib.sha256).hexdigest()


def is_authenticated(row: AuthSettings, token: str) -> bool:
    """Check a cookie value against the expected token."""
    if not password_enabled(row) or not token:
        return False
    return hmac.compare_digest(token, session_token(row))
