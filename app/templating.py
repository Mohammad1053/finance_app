from fastapi import Request
from fastapi.templating import Jinja2Templates
from jinja2 import pass_context

from app.jalali import PERSIAN_DIGITS, to_jalali_str
from app.units import CURRENCY_LABELS, factor


def _settings_context(request: Request) -> dict:
    """Make the saved settings, unit label and auth state available to every template."""
    settings = getattr(request.state, "settings", None)
    currency = settings.currency if settings else "toman"
    return {
        "app_settings": settings,
        "unit_label": CURRENCY_LABELS.get(currency, "تومان"),
        "auth_enabled": getattr(request.state, "auth_enabled", False),
    }


templates = Jinja2Templates(
    directory="app/templates", context_processors=[_settings_context]
)


@pass_context
def money(context, value) -> str:
    """Format an amount in the selected currency with Persian digits and separators."""
    if value is None or value == "":
        return ""
    settings = context.get("app_settings")
    multiplier = factor(settings.currency if settings else "toman")
    return f"{int(value) * multiplier:,}".replace(",", "،").translate(PERSIAN_DIGITS)


def fa_digits(value) -> str:
    """Convert every ASCII digit in the value to a Persian digit."""
    return str(value).translate(PERSIAN_DIGITS)


# Usage in templates: {{ d|jdate }}, {{ amount|money }}, {{ count|fa }}
templates.env.filters["jdate"] = to_jalali_str
templates.env.filters["money"] = money
templates.env.filters["fa"] = fa_digits
