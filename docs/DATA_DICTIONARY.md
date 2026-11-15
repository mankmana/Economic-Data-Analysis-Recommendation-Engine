# Initial FRED data dictionary

| Field | Description |
| --- | --- |
| `series_id` | Stable FRED identifier, initially `GDPC1` or `CPILFESL` |
| `observation_date` | Date associated with an observation |
| `value` | Numeric observation value after parsing FRED's response |
| `unit` | Unit supplied by FRED or derived by a documented transformation |
| `frequency` | Source observation frequency |
| `source_updated_at` | Timestamp indicating when the source data was retrieved |
| `is_missing` | Whether the source reported a missing observation |

## Series notes

- `GDPC1` is Real Gross Domestic Product, reported quarterly.
- `CPILFESL` is the Consumer Price Index for All Urban Consumers: All Items Less Food and Energy, reported monthly.
- Comparisons across these series must document frequency alignment and aggregation choices.
