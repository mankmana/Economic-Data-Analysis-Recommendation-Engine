"""FRED retrieval with a live graph endpoint and grounded local fallback."""

from __future__ import annotations

import csv
import io
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

from backend.app.config.settings import ROOT, SERIES_METADATA, Settings
from backend.app.models.domain import Observation, Series


class FREDClient:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or Settings()
        self._cache: dict[str, Series] = {}

    def get_series(self, series_id: str) -> Series:
        if series_id in self._cache:
            return self._cache[series_id]
        metadata = SERIES_METADATA[series_id]
        if self.settings.fred_live_data:
            live = self._fetch_live_series(series_id)
            if live is not None and live.observations:
                self._cache[series_id] = live
                return live
        local = self._load_local_series(series_id)
        self._cache[series_id] = local
        return local

    def _fetch_live_series(self, series_id: str) -> Series | None:
        query = urllib.parse.urlencode({"id": series_id})
        url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?{query}"
        try:
            request = urllib.request.Request(
                url,
                headers={"User-Agent": "EconomicDataAnalysisRecommendationEngine/1.0"},
            )
            with urllib.request.urlopen(request, timeout=self.settings.fred_timeout_seconds) as response:
                payload = response.read().decode("utf-8")
        except (OSError, urllib.error.URLError, TimeoutError):
            return None

        metadata = SERIES_METADATA[series_id]
        observations = []
        for row in csv.DictReader(io.StringIO(payload)):
            value_text = (row.get("value") or "").strip()
            if not value_text or value_text == ".":
                continue
            try:
                value = float(value_text.replace(",", ""))
            except ValueError:
                continue
            period = self._normalize_api_period(row.get("observation_date", ""), series_id)
            if period:
                observations.append(
                    Observation(period, value, metadata["unit"], "live_fred_graph")
                )
        if not observations:
            return None
        return Series(
            series_id=series_id,
            name=metadata["name"],
            unit=metadata["unit"],
            frequency=metadata["frequency"],
            source_mode="live_fred_graph",
            source_url=url,
            observations=sorted(observations, key=lambda item: period_key(item.period)),
        )

    def _load_local_series(self, series_id: str) -> Series:
        metadata = SERIES_METADATA[series_id]
        filename = "gdp_observations.csv" if series_id == "GDP" else "cpilfesl_observations.csv"
        path = ROOT / "data" / "grounding" / filename
        observations = []
        with path.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                if row.get("series_id") != series_id:
                    continue
                observations.append(
                    Observation(
                        period=row["observation_date"],
                        value=float(row["value"]),
                        unit=row.get("unit", metadata["unit"]),
                        source="local_grounding",
                    )
                )
        return Series(
            series_id=series_id,
            name=metadata["name"],
            unit=metadata["unit"],
            frequency=metadata["frequency"],
            source_mode="local_grounding",
            source_url=str(path.relative_to(ROOT)),
            observations=sorted(observations, key=lambda item: period_key(item.period)),
        )

    @staticmethod
    def _normalize_api_period(value: str, series_id: str) -> str:
        if series_id == "GDP":
            parsed = date.fromisoformat(value)
            quarter = ((parsed.month - 1) // 3) + 1
            return f"{parsed.year}-Q{quarter}"
        return value[:7]


def period_key(period: str) -> tuple[int, int]:
    if "-Q" in period:
        year, quarter = period.split("-Q")
        return int(year), int(quarter) * 3
    parts = period.split("-")
    return int(parts[0]), int(parts[1])


def periods_between(start: str, end: str) -> int:
    start_year, start_month = period_key(start)
    end_year, end_month = period_key(end)
    return (end_year - start_year) * 12 + end_month - start_month
