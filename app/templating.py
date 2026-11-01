from fastapi.templating import Jinja2Templates

from app.jalali import PERSIAN_DIGITS, to_jalali_str

templates = Jinja2Templates(directory="app/templates")


def money(value) -> str:
    """Format an integer with Persian digits and the Persian thousands separator."""
    if value is None or value == "":
        return ""
    return f"{int(value):,}".replace(",", "،").translate(PERSIAN_DIGITS)


def fa_digits(value) -> str:
    """Convert every ASCII digit in the value to a Persian digit."""
    return str(value).translate(PERSIAN_DIGITS)


# Usage in templates: {{ d|jdate }}, {{ amount|money }}, {{ count|fa }}
templates.env.filters["jdate"] = to_jalali_str
templates.env.filters["money"] = money
templates.env.filters["fa"] = fa_digits
