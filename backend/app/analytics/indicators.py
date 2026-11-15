"""Deterministic calculations used by the conversational agent."""

from __future__ import annotations

import math
from statistics import mean

from backend.app.fred.client import period_key, periods_between
from backend.app.models.domain import Observation, Series


def percent_change(start: float, end: float) -> float | None:
    if start == 0:
        return None
    return ((end - start) / start) * 100


def window(series: Series, years: int) -> tuple[list[Observation], bool]:
    observations = series.observations
    if not observations:
        return [], False
    latest = observations[-1]
    target_months = years * 12
    selected = [
        observation
        for observation in observations
        if periods_between(observation.period, latest.period) <= target_months
    ]
    enough_history = periods_between(observations[0].period, latest.period) >= target_months
    return selected, enough_history


def growth_series(series: Series, lag_periods: int) -> list[dict]:
    observations = series.observations
    by_period = {observation.period: observation for observation in observations}
    result = []
    lag_months = lag_periods * 3 if series.frequency == "Quarterly" else lag_periods
    for current in observations:
        previous = by_period.get(offset_period(current.period, -lag_months))
        if previous is None:
            continue
        change = percent_change(previous.value, current.value)
        if change is not None:
            result.append({"date": current.period, "value": round(change, 4)})
    return result


def offset_period(period: str, month_delta: int) -> str:
    if "-Q" in period:
        year_text, quarter_text = period.split("-Q")
        total_months = int(year_text) * 12 + (int(quarter_text) - 1) * 3
        shifted = total_months + month_delta
        year, month = divmod(shifted, 12)
        return f"{year}-Q{month // 3 + 1}"
    year_text, month_text = period.split("-")[:2]
    total_months = int(year_text) * 12 + int(month_text) - 1 + month_delta
    year, month = divmod(total_months, 12)
    return f"{year}-{month + 1:02d}"


def annualized_growth(start: float, end: float, years: float) -> float | None:
    if start <= 0 or end <= 0 or years <= 0:
        return None
    return ((end / start) ** (1 / years) - 1) * 100


def trend_label(values: list[float]) -> str:
    if len(values) < 2:
        return "insufficient observations"
    change = percent_change(values[0], values[-1])
    if change is None or abs(change) < 0.5:
        return "broadly stable"
    return "increasing" if change > 0 else "decreasing"


def average_by_quarter(monthly: list[dict]) -> dict[str, float]:
    grouped: dict[str, list[float]] = {}
    for point in monthly:
        year, month = point["date"].split("-")[:2]
        quarter = ((int(month) - 1) // 3) + 1
        grouped.setdefault(f"{year}-Q{quarter}", []).append(float(point["value"]))
    return {period: mean(values) for period, values in grouped.items()}


def correlation(left: list[float], right: list[float]) -> float | None:
    if len(left) < 2 or len(left) != len(right):
        return None
    left_mean = mean(left)
    right_mean = mean(right)
    numerator = sum((a - left_mean) * (b - right_mean) for a, b in zip(left, right))
    left_denominator = math.sqrt(sum((a - left_mean) ** 2 for a in left))
    right_denominator = math.sqrt(sum((b - right_mean) ** 2 for b in right))
    if left_denominator == 0 or right_denominator == 0:
        return None
    return numerator / (left_denominator * right_denominator)
