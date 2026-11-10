from dataclasses import dataclass

from app.models import User

THEMES = ("light", "dark", "system")
CURRENCIES = ("toman", "rial")


@dataclass(frozen=True)
class SettingsView:
    """Read-only copy of a user's profile, used by templates as `app_settings`."""

    username: str
    first_name: str
    last_name: str
    theme: str
    currency: str


def snapshot(user: User) -> SettingsView:
    """Copy the user's profile fields into an immutable view."""
    return SettingsView(user.username, user.first_name, user.last_name, user.theme, user.currency)
