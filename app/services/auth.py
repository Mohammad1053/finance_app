import hashlib
import hmac
import re
import secrets
import time

from sqlalchemy.orm import Session

from app.models import User

COOKIE_NAME = "session"
MIN_PASSWORD_LENGTH = 6
SESSION_DAYS = 30
USERNAME_RE = re.compile(r"^[a-z0-9_.]{3,30}$")

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


# Verified against when the username does not exist, so timing does not reveal valid usernames
DUMMY_HASH = hash_password("not-a-real-password")


def normalize_username(raw: str | None) -> str:
    """Usernames are case-insensitive: store and compare them in lowercase."""
    return (raw or "").strip().lower()


def new_secret() -> str:
    """Return a fresh random session secret."""
    return secrets.token_hex(32)


def session_token(user: User) -> str:
    """Return the cookie value 'user_id.signature' that proves a successful login."""
    mac = hmac.new(user.session_secret.encode(), b"session-v1", hashlib.sha256).hexdigest()
    return f"{user.id}.{mac}"


def user_from_token(db: Session, token: str) -> User | None:
    """Return the user a cookie belongs to, or None when it is invalid or outdated."""
    try:
        id_text, mac = token.split(".", 1)
        user_id = int(id_text)
    except ValueError:
        return None
    user = db.get(User, user_id)
    if user is None or not user.session_secret:
        return None
    expected = hmac.new(user.session_secret.encode(), b"session-v1", hashlib.sha256).hexdigest()
    return user if hmac.compare_digest(mac, expected) else None


class LoginThrottle:
    """Tiny in-memory limiter: too many recent failures block a key for a while."""

    def __init__(self, max_failures: int = 5, window_seconds: int = 300):
        self.max_failures = max_failures
        self.window = window_seconds
        self._failures: dict[str, list[float]] = {}

    def _recent(self, key: str) -> list[float]:
        now = time.monotonic()
        recent = [t for t in self._failures.get(key, []) if now - t < self.window]
        if recent:
            self._failures[key] = recent
        else:
            self._failures.pop(key, None)
        return recent

    def is_blocked(self, key: str) -> bool:
        return len(self._recent(key)) >= self.max_failures

    def register_failure(self, key: str) -> None:
        self._failures.setdefault(key, []).append(time.monotonic())

    def reset(self, key: str) -> None:
        self._failures.pop(key, None)

    def clear(self) -> None:
        self._failures.clear()


throttle = LoginThrottle()
