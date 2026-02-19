"""
Utility functions for cleaning and normalizing financial data
from Brazilian format (R$ 1.234,56) to numeric format (1234.56).
"""

def parse_brl(value: str) -> float:
    """
    Convert a Brazilian Real currency string to a float.
    Examples:
        "R$ 1.234,56"  -> 1234.56
        "R$ 0,35"      -> 0.35
        "R$ 150.917,84" -> 150917.84
        ""             -> 0.0
    """
    if not value or not isinstance(value, str):
        return 0.0
    cleaned = value.replace("R$", "").strip()
    if not cleaned:
        return 0.0
    # Remove thousand separator (.) and replace decimal separator (,) with (.)
    cleaned = cleaned.replace(".", "").replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def parse_titulos(value: str) -> int | None:
    """
    Extract the numeric count from a titulos string.
    Examples:
        "1.172 títulos" -> 1172
        "9 títulos"     -> 9
        "Feriado"       -> None
        "0 títulos"     -> 0
    """
    if not value or not isinstance(value, str):
        return None
    import re
    match = re.match(r"^([\d.]+)\s+t[ií]tulos?$", value.strip(), re.IGNORECASE)
    if match:
        num_str = match.group(1).replace(".", "")
        try:
            return int(num_str)
        except ValueError:
            return None
    return None
