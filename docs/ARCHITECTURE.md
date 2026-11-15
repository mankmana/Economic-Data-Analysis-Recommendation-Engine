# Architecture notes

## Core boundaries

- `fred` owns communication with FRED and normalization of source observations.
- `analytics` contains deterministic economic calculations and trend logic. It should not depend on a language model.
- `ai` translates a user question into a constrained analysis request and turns verified results into an explanation.
- `services` coordinates retrieval, calculations, provenance, and response assembly.
- `api` exposes stable contracts to the frontend.
- `visualization` emits chart-ready specifications from validated data.

The current implementation serves the frontend and JSON API from the standard-library Python HTTP server. The browser uses a two-step flow: the query page stores the question and navigates to the answer page, which calls `POST /api/query` and renders the returned answer, metrics, sources, warnings, and SVG chart.

## Reliability expectations

1. Do not invent observations, dates, units, or source series.
2. Keep calculations deterministic and testable outside the AI layer.
3. Include source metadata and the observation window in every analytical response.
4. Clearly label unavailable, revised, or incomplete observations.
5. Treat generated narrative as an interpretation of computed results, not as the source of truth.

## Unsupported-question behavior

The agent first checks whether a question mentions GDP, Core CPI, inflation, or consumer prices. If it does not, it returns a default response explaining the supported scope and suggested question types. It does not answer unrelated questions from general model knowledge. If a supported dataset is empty or unavailable, it returns a separate grounding-unavailable response instead of calculating from missing data.

## Initial analytical capabilities

- Latest available value and date for each series.
- Period-over-period and year-over-year changes.
- GDP growth calculation from `GDPC1`.
- Core CPI inflation calculation from `CPILFESL`.
- Time-window trend summaries.
- Aligned GDP-growth/Core-CPI comparisons with explicit frequency handling.
- Line charts and comparison charts based on the same data returned in the answer.

## Data modes

- Live mode attempts the public FRED graph CSV endpoint for `GDP` and `CPILFESL`.
- If live retrieval fails, the agent falls back to `data/grounding/gdp_observations.csv` and `data/grounding/cpilfesl_observations.csv`.
- The answer always labels the source mode and exposes the FRED series links.
