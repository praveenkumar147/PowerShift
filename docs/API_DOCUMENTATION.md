# API Documentation

*Lists implemented endpoints only. Last updated: Stage 2.*
The planned API is in [STAGE0_PLAN.md §7](STAGE0_PLAN.md#7-api-design).

## Conventions

- Base URL: `http://127.0.0.1:<port>`. The port is chosen at each launch.
- Authentication: every `/api` request must include `X-PowerShift-Token: <token>` when the backend was started with `--token` (the desktop app always does this).
- JSON request and response bodies.

### Error format

All errors share one shape:

```json
{ "error": { "code": "validation_error", "message": "Some values are invalid.", "fields": { "name": "Field required" } } }
```

| Status | `code` | When |
|---|---|---|
| 401 | `unauthorized` | Token missing or wrong |
| 404 | `not_found` | Unknown route or record |
| 405 | `method_not_allowed` | Wrong HTTP method |
| 409 | `conflict` | Request conflicts with current data |
| 422 | `validation_error` | Invalid input; `fields` maps field → message |
| 500 | `internal_error` | Unexpected error (details only in the local log) |

## Endpoints

### `GET /api/health`

Used by the app to confirm the backend and database work.

Response `200`:

```json
{
  "status": "ok",
  "version": "0.1.0",
  "schema_revision": "0001",
  "database_path": "C:\\...\\powershift.db"
}
```

---

## Household

### `GET /api/household`

`200` with the household, or `200` with `null` before the household has been set up.

### `PUT /api/household`

Creates or replaces the single household profile. Returns `200` with the saved profile.

| Field | Type | Rules |
|---|---|---|
| name | string | 1–100 characters, trimmed |
| occupants | integer | 1–50 |
| location_label | string \| null | ≤ 100 characters; blank becomes `null`; display only |
| max_load_kw | number | > 0 and ≤ 1000 (kW, instantaneous power) |
| currency_code | string | 3 letters; lowercase is accepted and stored uppercase |
| time_format | `"24h"` \| `"12h"` | default `"24h"` |

---

## Appliances

Times are **minutes since midnight** in 15-minute steps. Start: 0–1435. End: 15–1440.
An end ≤ start wraps past midnight; `0 → 1440` is all day.

### Appliance body (`POST` and `PUT`)

```json
{
  "name": "Washing machine",
  "category": "laundry",
  "rated_power_w": 2000,
  "quantity": 1,
  "duty_cycle": 0.5,
  "mode": "flexible",
  "priority": "medium",
  "allow_simultaneous": false,
  "operating_days": [0, 3, 5],
  "fixed_blocks": [],
  "flexible": {
    "run_duration_minutes": 90,
    "earliest_start_minute": 1320,
    "latest_end_minute": 360,
    "current_start_minute": 1380,
    "preferred_start_minute": null,
    "preferred_end_minute": null,
    "must_be_contiguous": true
  }
}
```

| Field | Rules |
|---|---|
| name | 1–100 characters; unique ignoring case (409 if taken) |
| category | `cooling`, `lighting`, `kitchen`, `laundry`, `entertainment`, `water_heating`, `electronics`, `other` |
| rated_power_w | > 0 and ≤ 100 000 W |
| quantity | 1–100 |
| duty_cycle | > 0 and ≤ 1 |
| mode | `fixed` or `flexible` |
| priority | `low`, `medium` (default), `high` |
| allow_simultaneous | default `true` |
| operating_days | 1–7 unique weekdays, 0 = Monday; returned sorted |
| fixed_blocks | `fixed` mode: 1–24 non-overlapping `{start_minute, end_minute}`; `flexible` mode: must be empty |
| flexible | `flexible` mode: required; `fixed` mode: must be `null` |
| flexible.run_duration_minutes | 15–1440; must fit inside the allowed window |
| flexible.current_start_minute | a run starting here must finish inside the allowed window |
| flexible.preferred_* | both or neither; must lie inside the allowed window and be at least as long as the run |

Unknown fields are rejected (422).

### Appliance response

The body above plus:

```json
{
  "id": 2,
  "estimates": {
    "max_power_kw": 2.0,
    "average_power_kw": 1.0,
    "on_hours_per_day": 1.5,
    "energy_per_operating_day_kwh": 1.5,
    "energy_per_week_kwh": 4.5
  },
  "warnings": []
}
```

- `max_power_kw` = rated W × quantity / 1000 (worst case, for load limits)
- `average_power_kw` = max power × duty cycle (for energy)
- `energy_per_operating_day_kwh` = average power × hours on
- `warnings`: non-blocking problems, e.g. one appliance at full power exceeds the household load limit.

All values are **estimates** from user-entered settings.

### Endpoints

| Method | Path | Success | Errors |
|---|---|---|---|
| GET | `/api/appliances?q=&category=&mode=` | 200, list sorted by name (case-insensitive) | 422 invalid filter |
| POST | `/api/appliances` | 201, the created appliance | 409 duplicate name, 422 invalid |
| GET | `/api/appliances/{id}` | 200 | 404 |
| PUT | `/api/appliances/{id}` | 200, the updated appliance (full replacement) | 404, 409, 422 |
| DELETE | `/api/appliances/{id}` | 204 (also deletes its days, blocks and flexible settings) | 404 |

`q` searches names case-insensitively; `%` and `_` are matched literally.

### Example validation error (422)

```json
{
  "error": {
    "code": "validation_error",
    "message": "Some values are inconsistent.",
    "fields": {
      "flexible.run_duration_minutes": "A 180-minute run cannot fit in the allowed window 22:00-24:00 (120 minutes)."
    }
  }
}
```
