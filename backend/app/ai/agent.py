"""Natural-language query routing for grounded economic analysis."""

from __future__ import annotations

import re
from dataclasses import dataclass

from backend.app.analytics.indicators import (
    annualized_growth,
    average_by_quarter,
    correlation,
    growth_series,
    percent_change,
    trend_label,
    window,
)
from backend.app.config.settings import SERIES_METADATA
from backend.app.fred.client import FREDClient, period_key
from backend.app.models.domain import AnalysisResult, Metric, Series
from backend.app.visualization.charts import line_chart


@dataclass(frozen=True)
class QueryIntent:
    name: str
    years: int | None = None


class EconomicAgent:
    def __init__(self, client: FREDClient | None = None) -> None:
        self.client = client or FREDClient()

    def answer(self, query: str) -> AnalysisResult:
        cleaned_query = query.strip()
        intent = classify_query(cleaned_query)
        if intent.name == "unsupported":
            result = self._unsupported(cleaned_query)
        elif not self._grounding_available(intent):
            result = self._grounding_unavailable(cleaned_query)
        else:
            try:
                if intent.name == "gdp_latest":
                    result = self._gdp_latest(cleaned_query)
                elif intent.name == "gdp_history":
                    result = self._gdp_history(cleaned_query, intent.years or 10)
                elif intent.name == "cpi_latest":
                    result = self._cpi_latest(cleaned_query)
                elif intent.name == "cpi_history":
                    result = self._cpi_history(cleaned_query, intent.years or 5)
                elif intent.name in {"comparison", "comparison_chart"}:
                    result = self._comparison(cleaned_query, intent.name == "comparison_chart")
                else:
                    result = self._summary(cleaned_query)
            except (FileNotFoundError, IndexError, KeyError, ValueError):
                result = self._grounding_unavailable(cleaned_query)
        result.sources = self._sources()
        return result

    def _grounding_available(self, intent: QueryIntent) -> bool:
        if intent.name in {"unsupported", "grounding_unavailable"}:
            return True
        required_series = {"GDP", "CPILFESL"} if intent.name in {"comparison", "comparison_chart", "summary"} else {"GDP" if intent.name.startswith("gdp") else "CPILFESL"}
        return all(self.client.get_series(series_id).observations for series_id in required_series)

    @staticmethod
    def _unsupported(query: str) -> AnalysisResult:
        subject = query or "That question"
        return AnalysisResult(
            query=query,
            intent="unsupported",
            answer=(
                f"I don't have grounded information to answer “{subject}”. "
                "I can answer questions only about the saved FRED GDP (GDP) and Core CPI (CPILFESL) datasets. "
                "Try asking for the latest value, a historical change, an inflation or growth rate, a trend, "
                "a GDP/Core CPI comparison, or a visualization."
            ),
            metrics=[Metric("Supported datasets", "GDP + Core CPI", "FRED series GDP and CPILFESL")],
        )

    @staticmethod
    def _grounding_unavailable(query: str) -> AnalysisResult:
        return AnalysisResult(
            query=query,
            intent="grounding_unavailable",
            answer=(
                "I can't answer that from grounded data right now because the required GDP/Core CPI observations "
                "are unavailable. Please check the saved grounding files or enable live FRED retrieval, then try again."
            ),
            metrics=[Metric("Grounding status", "Unavailable", "No verified observations were found for this request")],
            warnings=["No answer was generated from unverified or unrelated information."],
        )

    def _gdp_latest(self, query: str) -> AnalysisResult:
        series = self.client.get_series("GDP")
        latest = series.observations[-1]
        previous = series.observations[-2] if len(series.observations) > 1 else None
        change = percent_change(previous.value, latest.value) if previous else None
        answer = (
            f"The latest reported U.S. GDP in the connected FRED series is "
            f"{format_billions(latest.value)} ({latest.value:,.3f} billion dollars) for "
            f"{latest.period}."
        )
        if change is not None:
            answer += f" That is {change:+.2f}% from {previous.period}."
        return AnalysisResult(
            query=query,
            intent="gdp_latest",
            answer=answer,
            metrics=[
                Metric("Latest GDP", format_billions(latest.value), latest.period),
                Metric("Quarter-over-quarter", format_percent(change), "Compared with the prior reported quarter"),
                Metric("Data mode", source_mode_label(series.source_mode), ""),
            ],
            chart=line_chart(
                "U.S. GDP level",
                [{"name": "GDP", "unit": series.unit, "values": points(series)}],
                series.unit,
            ),
            warnings=self._history_warning(series, 1),
        )

    def _gdp_history(self, query: str, years: int) -> AnalysisResult:
        series = self.client.get_series("GDP")
        selected, enough_history = window(series, years)
        first, latest = selected[0], selected[-1]
        change = percent_change(first.value, latest.value)
        months = max(1, (period_key(latest.period)[0] - period_key(first.period)[0]) * 12 + period_key(latest.period)[1] - period_key(first.period)[1])
        cagr = annualized_growth(first.value, latest.value, months / 12)
        growth = growth_series(series, 4)
        answer = (
            f"Across the available {years}-year GDP window, the series moves from "
            f"{format_billions(first.value)} in {first.period} to {format_billions(latest.value)} "
            f"in {latest.period}, a total change of {format_percent(change)} and an annualized "
            f"growth rate of {format_percent(cagr)}. The latest observations suggest GDP is "
            f"{trend_label([item.value for item in selected])}."
        )
        warnings = self._history_warning(series, years)
        if not enough_history:
            warnings.append(
                f"Only {len(selected)} local/live observations cover {first.period} through {latest.period}; "
                f"the connected data does not span the full requested {years} years."
            )
        return AnalysisResult(
            query=query,
            intent="gdp_history",
            answer=answer,
            metrics=[
                Metric("Window", f"{first.period} → {latest.period}"),
                Metric("Total change", format_percent(change)),
                Metric("Annualized growth", format_percent(cagr)),
            ],
            chart=line_chart(
                f"U.S. GDP over the available {years}-year window",
                [{"name": "GDP level", "unit": series.unit, "values": points_from(selected)}],
                series.unit,
            ),
            warnings=warnings,
        )

    def _cpi_latest(self, query: str) -> AnalysisResult:
        series = self.client.get_series("CPILFESL")
        latest = series.observations[-1]
        inflation_points = growth_series(series, 12)
        inflation = inflation_points[-1] if inflation_points else None
        answer = (
            f"The latest Core CPI index is {latest.value:,.3f} for {latest.period}. "
            f"The latest year-over-year Core CPI inflation rate that can be calculated is "
            f"{format_percent(inflation['value'] if inflation else None)}."
        )
        return AnalysisResult(
            query=query,
            intent="cpi_latest",
            answer=answer,
            metrics=[
                Metric("Latest Core CPI", f"{latest.value:,.3f}", latest.period),
                Metric("Core CPI inflation", format_percent(inflation["value"] if inflation else None), "Year over year"),
                Metric("Data mode", source_mode_label(series.source_mode), ""),
            ],
            chart=line_chart(
                "Core CPI inflation rate",
                [{"name": "Core CPI YoY", "unit": "%", "values": inflation_points}],
                "Percent change from one year earlier",
            ),
            warnings=self._history_warning(series, 1),
        )

    def _cpi_history(self, query: str, years: int) -> AnalysisResult:
        series = self.client.get_series("CPILFESL")
        selected, enough_history = window(series, years)
        first, latest = selected[0], selected[-1]
        change = percent_change(first.value, latest.value)
        inflation_points = growth_series(series, 12)
        selected_periods = {item.period for item in selected}
        selected_inflation = [point for point in inflation_points if point["date"] in selected_periods]
        answer = (
            f"Over the available {years}-year Core CPI window, the index rose from "
            f"{first.value:,.3f} in {first.period} to {latest.value:,.3f} in {latest.period}, "
            f"a {format_percent(change)} change. The index trend is "
            f"{trend_label([item.value for item in selected])}."
        )
        warnings = self._history_warning(series, years)
        if not enough_history:
            warnings.append(
                f"Only {len(selected)} local/live observations cover {first.period} through {latest.period}; "
                f"the connected data does not span the full requested {years} years."
            )
        return AnalysisResult(
            query=query,
            intent="cpi_history",
            answer=answer,
            metrics=[
                Metric("Window", f"{first.period} → {latest.period}"),
                Metric("Index change", format_percent(change)),
                Metric("Latest inflation", format_percent(inflation_points[-1]["value"] if inflation_points else None), "Year over year"),
            ],
            chart=line_chart(
                f"Core CPI over the available {years}-year window",
                [{"name": "Core CPI index", "unit": series.unit, "values": points_from(selected)}],
                series.unit,
            ),
            warnings=warnings,
        )

    def _comparison(self, query: str, chart_requested: bool) -> AnalysisResult:
        gdp = self.client.get_series("GDP")
        cpi = self.client.get_series("CPILFESL")
        gdp_growth = growth_series(gdp, 4)
        cpi_inflation = growth_series(cpi, 12)
        cpi_by_quarter = average_by_quarter(cpi_inflation)
        paired = [
            (point["date"], point["value"], cpi_by_quarter[point["date"]])
            for point in gdp_growth
            if point["date"] in cpi_by_quarter
        ]
        coefficient = correlation([item[1] for item in paired], [item[2] for item in paired])
        if coefficient is None:
            relationship = "There are not enough overlapping observations to estimate a reliable relationship."
        elif coefficient > 0.3:
            relationship = "The available overlapping observations show a positive association."
        elif coefficient < -0.3:
            relationship = "The available overlapping observations show a negative association."
        else:
            relationship = "The available overlapping observations show a weak linear association."
        answer = (
            f"GDP growth and Core CPI inflation are compared at a quarterly frequency. "
            f"{relationship}"
        )
        if coefficient is not None:
            answer += f" The Pearson correlation over {len(paired)} overlapping quarters is {coefficient:+.2f}."
        if chart_requested:
            answer = "Here is the requested GDP-growth/Core-CPI comparison. " + answer
        warnings = []
        if len(paired) < 8:
            warnings.append("The comparison is based on a limited overlap in the connected data.")
        return AnalysisResult(
            query=query,
            intent="comparison_chart" if chart_requested else "comparison",
            answer=answer,
            metrics=[
                Metric("Overlapping quarters", str(len(paired))),
                Metric("Correlation", f"{coefficient:+.2f}" if coefficient is not None else "Unavailable"),
                Metric("Alignment", "Quarterly GDP growth vs. quarterly-average monthly Core CPI YoY"),
            ],
            chart=line_chart(
                "GDP growth vs. Core CPI inflation",
                [
                    {"name": "GDP growth", "unit": "%", "values": [{"date": date, "value": value} for date, value, _ in paired]},
                    {"name": "Core CPI inflation", "unit": "%", "values": [{"date": date, "value": inflation} for date, _, inflation in paired]},
                ],
                "Percent",
            ),
            warnings=warnings,
        )

    def _summary(self, query: str) -> AnalysisResult:
        gdp = self._gdp_history(query, 10)
        cpi = self._cpi_history(query, 5)
        comparison = self._comparison(query, False)
        answer = (
            f"GDP is {gdp.answer} Core CPI is {cpi.answer} "
            f"For the relationship between the series, {comparison.answer}"
        )
        return AnalysisResult(
            query=query,
            intent="summary",
            answer=answer,
            metrics=gdp.metrics[:2] + cpi.metrics[1:2] + comparison.metrics[:2],
            chart=comparison.chart,
            warnings=list(dict.fromkeys(gdp.warnings + cpi.warnings + comparison.warnings)),
        )

    def _sources(self) -> list[dict]:
        return [
            {
                "series_id": series_id,
                "name": metadata["name"],
                "url": metadata["source_url"],
                "local_grounding": "data/grounding/" + ("gdp_observations.csv" if series_id == "GDP" else "cpilfesl_observations.csv"),
            }
            for series_id, metadata in SERIES_METADATA.items()
        ]

    @staticmethod
    def _history_warning(series: Series, years: int) -> list[str]:
        if series.source_mode == "local_grounding":
            return ["Live FRED retrieval was unavailable or disabled; this answer uses the saved local grounding snapshots."]
        return []


def classify_query(query: str) -> QueryIntent:
    normalized = query.lower()
    if not normalized.strip():
        return QueryIntent("unsupported")
    mentions_gdp = "gdp" in normalized or "gross domestic product" in normalized
    mentions_cpi = "cpi" in normalized or "inflation" in normalized or "consumer price" in normalized
    if not mentions_gdp and not mentions_cpi:
        return QueryIntent("unsupported")
    if any(token in normalized for token in ("visual", "chart", "graph", "plot")) and ("gdp" in normalized or "cpi" in normalized or "inflation" in normalized):
        return QueryIntent("comparison_chart")
    if any(token in normalized for token in ("relationship", "correlation", "compare", "versus", " vs ")) and ("gdp" in normalized or "cpi" in normalized or "inflation" in normalized):
        return QueryIntent("comparison")
    if any(token in normalized for token in ("summarize", "summary", "key economic trends", "overall")):
        return QueryIntent("summary")
    if mentions_cpi:
        if any(token in normalized for token in ("latest", "current", "now", "reported")) and not any(token in normalized for token in ("past", "year", "change", "trend", "history")):
            return QueryIntent("cpi_latest")
        return QueryIntent("cpi_history", extract_years(normalized, 5))
    if mentions_gdp:
        if any(token in normalized for token in ("latest", "current", "now", "reported")) and not any(token in normalized for token in ("past", "year", "change", "trend", "history")):
            return QueryIntent("gdp_latest")
        return QueryIntent("gdp_history", extract_years(normalized, 10))
    return QueryIntent("summary")


def extract_years(query: str, default: int) -> int:
    digit_match = re.search(r"(\d+)\s*years?", query)
    if digit_match:
        return max(1, min(int(digit_match.group(1)), 50))
    word_years = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "ten": 10}
    for word, years in word_years.items():
        if f"{word} year" in query:
            return years
    return default


def points(series: Series) -> list[dict]:
    return points_from(series.observations)


def points_from(observations: list) -> list[dict]:
    return [{"date": observation.period, "value": round(observation.value, 4)} for observation in observations]


def format_billions(value: float) -> str:
    return f"${value / 1000:,.2f} trillion"


def format_percent(value: float | None) -> str:
    return "Unavailable" if value is None else f"{value:+.2f}%"


def source_mode_label(source_mode: str) -> str:
    return "Live FRED" if source_mode == "live_fred_graph" else "Saved grounding"
