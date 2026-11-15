# Local FRED grounding data

This directory is generated from the saved HTML snapshots under `data/GDP/` and `data/Consumer Price Index/`.
The HTML snapshots remain the source of record; generated files are normalized retrieval artifacts.

- Source HTML files: 22
- Searchable table chunks: 22
- GDP observation rows before deduplication: 20
- CPILFESL observation rows before deduplication: 34

## Generated files

- `source_manifest.json`: source filenames, URLs, hashes, page types, and extraction counts.
- `grounding_chunks.jsonl`: searchable table text with source provenance per chunk.
- `gdp_observations.csv`: deduplicated GDP observations extracted from the saved pages.
- `cpilfesl_observations.csv`: deduplicated CPILFESL observations extracted from the saved pages.

## Important scope note

The saved release-table snapshots expose selected periods and latest/prior-year comparisons, not a complete historical time series. Use these artifacts as grounded local evidence; future ingestion can add the complete FRED API series while preserving the same provenance fields.
