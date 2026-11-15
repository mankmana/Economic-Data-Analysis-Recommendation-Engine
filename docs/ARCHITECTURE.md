# Architecture notes

## Core boundaries

- `fred` owns communication with FRED and normalization of source observations.
- `analytics` contains deterministic economic calculations and trend logic. It should not depend on a language model.
- `ai` translates a user question into a constrained analysis request and turns verified results into an explanation.
- `services` coordinates retrieval, calculations, provenance, and response assembly.
- `api` exposes stable contracts to the frontend.
- `visualization` emits chart-ready specifications from validated data.

## Reliability expectations

1. Do not invent observations, dates, units, or source series.
2. Keep calculations deterministic and testable outside the AI layer.
3. Include source metadata and the observation window in every analytical response.
4. Clearly label unavailable, revised, or incomplete observations.
5. Treat generated narrative as an interpretation of computed results, not as the source of truth.

## Initial analytical capabilities

- Latest available value and date for each series.
- Period-over-period and year-over-year changes.
- GDP growth calculation from `GDPC1`.
- Core CPI inflation calculation from `CPILFESL`.
- Time-window trend summaries.
- Aligned GDP-growth/Core-CPI comparisons with explicit frequency handling.
- Line charts and comparison charts based on the same data returned in the answer.
