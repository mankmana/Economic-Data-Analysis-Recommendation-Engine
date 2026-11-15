"""Small domain objects shared by retrieval, analytics, and API layers."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Observation:
    period: str
    value: float
    unit: str
    source: str


@dataclass
class Series:
    series_id: str
    name: str
    unit: str
    frequency: str
    source_mode: str
    source_url: str
    observations: list[Observation] = field(default_factory=list)


@dataclass(frozen=True)
class Metric:
    label: str
    value: str
    detail: str = ""


@dataclass
class AnalysisResult:
    query: str
    intent: str
    answer: str
    metrics: list[Metric] = field(default_factory=list)
    chart: dict | None = None
    sources: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "query": self.query,
            "intent": self.intent,
            "answer": self.answer,
            "metrics": [metric.__dict__ for metric in self.metrics],
            "chart": self.chart,
            "sources": self.sources,
            "warnings": self.warnings,
        }
