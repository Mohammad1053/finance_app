from dataclasses import dataclass

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import AppSettings

THEMES = ("light", "dark", "system")
CURRENCIES = ("toman", "rial")


@dataclass(frozen=True)
class SettingsView:
    """Read-only copy of the settings, safe to use in templates after the session closes."""

    first_name: str
    last_name: str
    theme: str
    currency: str


def get_settings(db: Session) -> AppSettings:
    """Return the settings row, creating it with defaults on first use."""
    row = db.get(AppSettings, 1)
    if row is None:
        row = AppSettings(id=1, first_name="", last_name="",
                          theme="light", currency="toman")
        db.add(row)
        try:
            db.commit()
        except IntegrityError:
            # Another request created it at the same moment
            db.rollback()
            row = db.get(AppSettings, 1)
    return row


def snapshot(row: AppSettings) -> SettingsView:
    """Copy the row into an immutable view."""
    return SettingsView(row.first_name, row.last_name, row.theme, row.currency)
