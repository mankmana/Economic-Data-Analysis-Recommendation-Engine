"""Runtime configuration for the local economic analysis application."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    host: str = os.getenv("BACKEND_HOST", "127.0.0.1")
    port: int = int(os.getenv("BACKEND_PORT", "8000"))
    fred_live_data: bool = _env_bool("FRED_LIVE_DATA", True)
    fred_timeout_seconds: float = float(os.getenv("FRED_HTTP_TIMEOUT", "8"))


SERIES_METADATA = {
    "GDP": {
        "name": "Gross Domestic Product",
        "short_name": "GDP",
        "unit": "Billions of Dollars",
        "frequency": "Quarterly",
        "source_url": "https://fred.stlouisfed.org/series/GDP",
    },
    "CPILFESL": {
        "name": "Consumer Price Index: All Items Less Food and Energy",
        "short_name": "Core CPI",
        "unit": "Index 1982-1984=100",
        "frequency": "Monthly",
        "source_url": "https://fred.stlouisfed.org/series/CPILFESL",
    },
}
