"""Chart specifications consumed by the dependency-free frontend renderer."""

from __future__ import annotations


def line_chart(title: str, series: list[dict], y_label: str) -> dict:
    return {
        "type": "line",
        "title": title,
        "y_label": y_label,
        "series": series,
    }
