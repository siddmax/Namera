from __future__ import annotations

from namera.providers.base import Availability

# Brand palette — single source of truth for all CLI colors.
BRAND = "dark_orange3"
BRAND_DIM = "orange4"
ACCENT = "orange1"
SUCCESS = "bright_green"
DANGER = "red"
WARNING = "yellow"
MUTED = "dim"
HEADING = f"bold {ACCENT}"
ERROR = f"bold {DANGER}"

# UI element styles
PANEL_BORDER = BRAND
TABLE_HEADER = BRAND
TABLE_TITLE = f"bold {ACCENT}"
FIELD_LABEL = "bold"

# Availability status → (label, rich style)
AVAILABILITY_STYLES: dict[Availability, tuple[str, str]] = {
    Availability.AVAILABLE: ("Available", SUCCESS),
    Availability.TAKEN: ("Taken", DANGER),
    Availability.UNKNOWN: ("Unknown", WARNING),
}


def availability_style(av: Availability) -> tuple[str, str]:
    """Return (label, rich_style) for an availability status."""
    return AVAILABILITY_STYLES[av]


def styled(text: str, style: str) -> str:
    """Wrap text in Rich markup."""
    return f"[{style}]{text}[/{style}]"
