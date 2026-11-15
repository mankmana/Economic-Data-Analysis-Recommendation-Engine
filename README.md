# Economic Data Analysis Recommendation Engine

An AI-powered application for conversing with two FRED economic datasets and turning economic observations into explainable analysis.

## Product goals

The application will allow users to:

- Ask natural-language questions about historical and latest available observations.
- Calculate economic indicators from the source observations.
- Identify trends and meaningful changes over time.
- Compare GDP growth with Core CPI inflation.
- Generate charts and other visualizations that support the answer.

The initial dataset boundary is intentionally small and explicit:

| Dataset | FRED series ID | Intended use |
| --- | --- | --- |
| Gross Domestic Product | `GDP` | GDP level and growth analysis |
| Core CPI | `CPILFESL` | Core inflation level and trend analysis |

## Repository structure

```text
.
├── backend/
│   ├── app/
│   │   ├── ai/                 # Natural-language interpretation and answer orchestration
│   │   ├── analytics/          # Indicators, trends, and cross-series comparisons
│   │   ├── api/                # HTTP endpoints and request/response contracts
│   │   ├── config/             # Runtime configuration and environment settings
│   │   ├── fred/               # FRED client, series metadata, and observation retrieval
│   │   ├── models/             # Domain and transport models
│   │   ├── services/           # Application use cases and orchestration
│   │   └── visualization/      # Chart specifications and visualization data
│   └── tests/
│       ├── integration/        # API and external-boundary tests
│       └── unit/               # Fast isolated tests
├── data/
│   ├── grounding/              # Generated, provenance-preserving grounding artifacts
│   ├── processed/              # Normalized/cacheable observations and derived data
│   └── raw/                    # Downloaded source payloads (not committed)
├── docs/                       # Architecture, data dictionary, and API notes
├── frontend/
│   └── src/
│       ├── components/         # Reusable UI and chart components
│       ├── pages/              # Conversation and analysis views
│       ├── services/           # Backend API client and query state
│       ├── types/              # Shared frontend contracts
│       └── utils/              # Formatting and presentation helpers
├── scripts/                    # Local ingestion, validation, and maintenance commands
└── .env.example                # Required local configuration names
```

## Suggested request flow

```text
User question
    -> frontend conversation UI
    -> backend query endpoint
    -> intent and series resolution
    -> FRED observation retrieval/cache
    -> indicator or comparison calculation
    -> answer + provenance + chart specification
    -> frontend response and visualization
```

Every generated answer should retain the FRED series IDs, observation dates, units, transformations, and calculation assumptions used to produce it. This makes answers auditable and helps distinguish source facts from model-generated explanation.

## Development status

The first runnable application is now implemented with a dependency-free Python backend and web frontend. It supports the example GDP/Core CPI questions through a grounded deterministic analysis agent and can optionally retrieve the latest complete series directly from FRED's graph CSV endpoint.

## Local grounding data

Run `python scripts/build_grounding.py` after adding or replacing saved FRED HTML snapshots. The command creates normalized observations and searchable table chunks under `data/grounding/` while leaving the original source pages unchanged.

## Run locally

```bash
python scripts/run_app.py
```

Open `http://127.0.0.1:8000`. Set `FRED_LIVE_DATA=false` to force answers to use only the saved local grounding files.
