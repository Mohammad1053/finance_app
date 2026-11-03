CURRENCY_LABELS = {"toman": "تومان", "rial": "ریال"}
RIAL_PER_TOMAN = 10


def factor(currency: str) -> int:
    """Multiplier from the stored unit (Toman) to the display unit."""
    return RIAL_PER_TOMAN if currency == "rial" else 1


def to_base(amount: int | None, currency: str) -> int | None:
    """Convert an amount typed in the display unit back to the stored unit (Toman)."""
    if amount is None or factor(currency) == 1:
        return amount
    converted = (amount + 5) // RIAL_PER_TOMAN  # round to the nearest Toman
    # A positive amount must never silently become zero
    return max(1, converted) if amount > 0 else converted
