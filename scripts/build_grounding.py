"""Build local, provenance-preserving grounding artifacts from saved FRED HTML.

The original HTML snapshots remain the source of record. This script creates
normalized observations and searchable table chunks for the initial GDP and
CPILFESL datasets without making network requests.
"""

from __future__ import annotations

import csv
import hashlib
import html
import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
GROUNDING_DIR = ROOT / "data" / "grounding"


@dataclass
class SourceConfig:
    dataset: str
    series_id: str
    directory: Path
    frequency: str
    unit: str
    target_labels: tuple[str, ...]


SOURCE_CONFIGS = (
    SourceConfig(
        dataset="gdp",
        series_id="GDP",
        directory=ROOT / "data" / "GDP",
        frequency="Quarterly",
        unit="Billions of Dollars",
        target_labels=("gross domestic product",),
    ),
    SourceConfig(
        dataset="consumer_price_index",
        series_id="CPILFESL",
        directory=ROOT / "data" / "Consumer Price Index",
        frequency="Monthly",
        unit="Index 1982-1984=100",
        target_labels=("all items less food and energy",),
    ),
)


class TableParser(HTMLParser):
    """Collect visible cell text from HTML tables."""

    def __init__(self) -> None:
        super().__init__()
        self.tables: list[list[list[str]]] = []
        self._table: list[list[str]] | None = None
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "table":
            self._table = []
        elif self._table is not None and tag == "tr":
            self._row = []
        elif self._row is not None and tag in {"td", "th"}:
            self._cell = []

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self._cell is not None and tag in {"td", "th"}:
            self._row.append(clean_text("".join(self._cell)))
            self._cell = None
        elif self._row is not None and tag == "tr":
            if self._row:
                self._table.append(self._row)
            self._row = None
        elif self._table is not None and tag == "table":
            if self._table:
                self.tables.append(self._table)
            self._table = None


def clean_text(value: str) -> str:
    return " ".join(html.unescape(value).split())


def source_url(content: str) -> str:
    saved_url = re.search(r"saved from url=\(\d+\)(.*?)-->", content, re.S)
    if saved_url:
        return html.unescape(saved_url.group(1).strip())
    content_url = re.search(r'"contentUrl"\s*:\s*"([^"]+)"', content)
    return html.unescape(content_url.group(1)) if content_url else ""


def page_title(content: str) -> str:
    match = re.search(r"<title[^>]*>(.*?)</title>", content, re.S | re.I)
    return clean_text(match.group(1)) if match else ""


def page_description(content: str) -> str:
    match = re.search(
        r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']',
        content,
        re.S | re.I,
    )
    return clean_text(match.group(1)) if match else ""


def parse_period(value: str) -> tuple[str, str] | None:
    value = clean_text(value).rstrip(":")
    quarter = re.fullmatch(r"Q([1-4])\s+(\d{4})", value)
    if quarter:
        return f"{quarter.group(2)}-Q{quarter.group(1)}", value
    month = re.fullmatch(
        r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{4})",
        value,
    )
    if month:
        month_number = {
            "Jan": "01",
            "Feb": "02",
            "Mar": "03",
            "Apr": "04",
            "May": "05",
            "Jun": "06",
            "Jul": "07",
            "Aug": "08",
            "Sep": "09",
            "Oct": "10",
            "Nov": "11",
            "Dec": "12",
        }[month.group(1)]
        return f"{month.group(2)}-{month_number}", value
    return None


def numeric_value(value: str) -> float | None:
    if clean_text(value).startswith("."):
        return None
    match = re.search(r"-?\d[\d,]*(?:\.\d+)?", value)
    return float(match.group(0).replace(",", "")) if match else None


def is_period_header(value: str) -> bool:
    return parse_period(value) is not None


def is_target_row(row: list[str], labels: Iterable[str]) -> bool:
    normalized = {clean_text(cell).lower() for cell in row}
    return any(label in normalized for label in labels)


def table_is_calendar(table: list[list[str]]) -> bool:
    joined = " ".join(" ".join(row) for row in table[:3]).lower()
    return "monday" in joined and "tuesday" in joined


def table_as_text(table: list[list[str]]) -> str:
    lines = []
    for row in table:
        lines.append(" | ".join(cell.replace("|", "\\|") for cell in row))
    return "\n".join(lines)


def extract_observations(
    config: SourceConfig,
    tables: list[list[list[str]]],
    source: dict[str, str],
) -> list[dict[str, object]]:
    observations: list[dict[str, object]] = []
    source_type = source["source_type"]

    for table_index, table in enumerate(tables):
        if table_is_calendar(table):
            continue

        if source_type == "series_page":
            for row in table:
                if len(row) < 2:
                    continue
                parsed = parse_period(row[0])
                value = numeric_value(row[1])
                if parsed and value is not None:
                    observations.append(
                        observation_record(
                            config,
                            source,
                            table_index,
                            parsed,
                            value,
                            row[1],
                        )
                    )
            continue

        header: list[str] | None = None
        header_index = -1
        period_positions: list[tuple[int, tuple[str, str]]] = []
        for index, row in enumerate(table):
            candidates = [(position, parse_period(cell)) for position, cell in enumerate(row)]
            periods = [(position, parsed) for position, parsed in candidates if parsed]
            if len(periods) >= 2:
                header = row
                header_index = index
                period_positions = periods
                break
        if header is None:
            continue

        for row in table[header_index + 1 :]:
            if not is_target_row(row, config.target_labels):
                continue
            for position, parsed in period_positions:
                if position >= len(row):
                    continue
                value = numeric_value(row[position])
                if value is None:
                    continue
                observations.append(
                    observation_record(
                        config,
                        source,
                        table_index,
                        parsed,
                        value,
                        row[position],
                    )
                )

    return observations


def observation_record(
    config: SourceConfig,
    source: dict[str, str],
    table_index: int,
    parsed: tuple[str, str],
    value: float,
    raw_value: str,
) -> dict[str, object]:
    return {
        "dataset": config.dataset,
        "series_id": config.series_id,
        "observation_date": parsed[0],
        "observation_label": parsed[1],
        "value": value,
        "raw_value": clean_text(raw_value),
        "unit": config.unit,
        "frequency": config.frequency,
        "source_file": source["source_file"],
        "source_url": source["source_url"],
        "source_type": source["source_type"],
        "source_table": str(table_index),
        "source_sha256": source["source_sha256"],
    }


def build() -> None:
    GROUNDING_DIR.mkdir(parents=True, exist_ok=True)
    all_sources: list[dict[str, object]] = []
    all_observations: list[dict[str, object]] = []
    chunks: list[dict[str, object]] = []

    for config in SOURCE_CONFIGS:
        for path in sorted(config.directory.glob("*.html")):
            content = path.read_text(encoding="utf-8", errors="replace")
            digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
            parser = TableParser()
            parser.feed(content)
            url = source_url(content)
            source_type = "series_page" if "/series/" in url else "release_table"
            source = {
                "dataset": config.dataset,
                "series_id": config.series_id,
                "source_file": path.relative_to(ROOT).as_posix(),
                "source_url": url,
                "source_type": source_type,
                "title": page_title(content),
                "description": page_description(content),
                "source_sha256": digest,
            }
            observations = extract_observations(config, parser.tables, source)
            all_observations.extend(observations)
            all_sources.append(
                {
                    **source,
                    "table_count": len(parser.tables),
                    "data_table_count": sum(
                        not table_is_calendar(table) for table in parser.tables
                    ),
                    "target_observation_count": len(observations),
                }
            )

            for table_index, table in enumerate(parser.tables):
                if table_is_calendar(table):
                    continue
                chunks.append(
                    {
                        "chunk_id": f"{config.dataset}-{digest[:12]}-table-{table_index}",
                        "dataset": config.dataset,
                        "series_id": config.series_id,
                        "source_file": source["source_file"],
                        "source_url": url,
                        "source_type": source_type,
                        "title": source["title"],
                        "text": (
                            f"Source: {source['title']}\n"
                            f"FRED URL: {url}\n"
                            f"Series ID: {config.series_id}\n"
                            f"Dataset: {config.dataset}\n"
                            f"Table index: {table_index}\n\n"
                            f"{table_as_text(table)}"
                        ),
                    }
                )

    write_json(GROUNDING_DIR / "source_manifest.json", all_sources)
    write_jsonl(GROUNDING_DIR / "grounding_chunks.jsonl", chunks)
    write_observations(all_observations)
    write_summary(all_sources, all_observations, chunks)


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: Iterable[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_observations(rows: list[dict[str, object]]) -> None:
    grouped: dict[tuple[str, str, float], dict[str, object]] = {}
    source_fields = ("source_file", "source_url", "source_type", "source_table", "source_sha256")
    for row in rows:
        key = (str(row["dataset"]), str(row["observation_date"]), float(row["value"]))
        if key not in grouped:
            grouped[key] = {**row, "source_files": [], "source_urls": [], "source_count": 0}
        target = grouped[key]
        for field in source_fields:
            output_field = f"{field}s" if field in {"source_file", "source_url"} else field
            if field in {"source_file", "source_url"}:
                values = target[output_field]
                if row[field] not in values:
                    values.append(row[field])
        target["source_count"] = int(target["source_count"]) + 1

    output_fields = [
        "dataset",
        "series_id",
        "observation_date",
        "observation_label",
        "value",
        "raw_value",
        "unit",
        "frequency",
        "source_count",
        "source_files",
        "source_urls",
    ]
    for dataset, filename in (("gdp", "gdp_observations.csv"), ("consumer_price_index", "cpilfesl_observations.csv")):
        dataset_rows = [row for row in grouped.values() if row["dataset"] == dataset]
        dataset_rows.sort(key=lambda row: str(row["observation_date"]))
        with (GROUNDING_DIR / filename).open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=output_fields)
            writer.writeheader()
            for row in dataset_rows:
                writer.writerow(
                    {
                        field: "; ".join(row[field]) if isinstance(row[field], list) else row[field]
                        for field in output_fields
                    }
                )


def write_summary(
    sources: list[dict[str, object]],
    observations: list[dict[str, object]],
    chunks: list[dict[str, object]],
) -> None:
    grouped = defaultdict(set)
    for row in observations:
        grouped[str(row["dataset"])].add(str(row["observation_date"]))
    summary = [
        "# Local FRED grounding data",
        "",
        "This directory is generated from the saved HTML snapshots under `data/GDP/` and `data/Consumer Price Index/`.",
        "The HTML snapshots remain the source of record; generated files are normalized retrieval artifacts.",
        "",
        f"- Source HTML files: {len(sources)}",
        f"- Searchable table chunks: {len(chunks)}",
        f"- GDP observation rows before deduplication: {sum(1 for row in observations if row['dataset'] == 'gdp')}",
        f"- CPILFESL observation rows before deduplication: {sum(1 for row in observations if row['dataset'] == 'consumer_price_index')}",
        "",
        "## Generated files",
        "",
        "- `source_manifest.json`: source filenames, URLs, hashes, page types, and extraction counts.",
        "- `grounding_chunks.jsonl`: searchable table text with source provenance per chunk.",
        "- `gdp_observations.csv`: deduplicated GDP observations extracted from the saved pages.",
        "- `cpilfesl_observations.csv`: deduplicated CPILFESL observations extracted from the saved pages.",
        "",
        "## Important scope note",
        "",
        "The saved release-table snapshots expose selected periods and latest/prior-year comparisons, not a complete historical time series. Use these artifacts as grounded local evidence; future ingestion can add the complete FRED API series while preserving the same provenance fields.",
        "",
    ]
    (GROUNDING_DIR / "README.md").write_text("\n".join(summary), encoding="utf-8")


if __name__ == "__main__":
    build()
