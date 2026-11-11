# API Documentation

*Lists implemented endpoints only. Last updated: Stage 6.*
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

---

## Tariffs

Rates and amounts are decimals with up to 4 decimal places, sent and received as JSON numbers.

### Tariff body (`POST` and `PUT`)

```json
{
  "name": "Night saver",
  "tariff_type": "tou",
  "effective_date": "2026-04-01",
  "flat_rate_per_kwh": null,
  "tou_periods": [
    { "day_type": "all", "start_minute": 1320, "end_minute": 360, "rate_per_kwh": 3.0 },
    { "day_type": "all", "start_minute": 360, "end_minute": 1320, "rate_per_kwh": 7.25 }
  ],
  "slabs": [],
  "slab_mode": "telescopic",
  "charges": [
    { "kind": "fixed_monthly", "label": "Meter rent", "amount": 50 },
    { "kind": "per_kwh", "label": "Fuel surcharge", "amount": 0.3 },
    { "kind": "percentage", "label": "Electricity duty", "amount": 5 }
  ]
}
```

| Field | Rules |
|---|---|
| tariff_type | `flat` needs `flat_rate_per_kwh`; `tou` needs `tou_periods`; `slab` needs `slabs`. Fields for other types must be empty. |
| tou_periods | ≤ 48. Either `day_type: "all"` only, or `weekday` + `weekend` sets; each set covers 24 h exactly once (error names the first uncovered or overlapping time) |
| slabs | ≤ 20; `up_to_kwh` increasing; only the last is `null` ("and above") |
| slab_mode | `telescopic` (default) or `whole_usage` |
| charges | ≤ 20; `percentage` amount ≤ 100 |

Response = body + `id` + `is_active`.

### Endpoints

| Method | Path | Notes |
|---|---|---|
| GET | `/api/tariffs` | Active tariff first, then by name |
| POST | `/api/tariffs` | 201. The **first** tariff created becomes active |
| GET | `/api/tariffs/{id}` | 404 if missing |
| PUT | `/api/tariffs/{id}` | Full replacement; does not change which tariff is active |
| DELETE | `/api/tariffs/{id}` | 204. Deleting the active tariff is allowed; costs then show as unavailable *(changed from the Stage 0 plan's 409, which would have made the only tariff undeletable)* |
| POST | `/api/tariffs/{id}/activate` | Makes this the only active tariff |

---

## Energy analysis

All figures are **estimates** from appliance settings. Each response includes `notes`
explaining the assumptions. *(The Stage 0 plan listed separate `summary` and
`appliance-breakdown` endpoints; they are combined in `/report` so one request
returns consistent numbers.)*

| Method | Path | Returns |
|---|---|---|
| GET | `/api/energy/report?start=YYYY-MM-DD&end=YYYY-MM-DD&category=` | Totals, average per day, energy charge, daily series, per-appliance and per-category breakdown (≤ 366 days; 422 with field `end` otherwise) |
| GET | `/api/energy/hourly-profile?weekday=0..6&category=` | 24 rows: `kwh`, `fixed_kwh`, `flexible_kwh`, `price_per_kwh`. Omit `weekday` for the weekly average |
| GET | `/api/energy/monthly?year=&category=` | 12 rows: `days`, `kwh`, `bill_total` (whole household) |
| GET | `/api/energy/bill?year=&month=` | Itemised bill: `lines[]` (label, kind, amount, detail), `subtotal`, `total`, `effective_rate_per_kwh` |

Without an active tariff, money fields are `null` and the notes say so.

Costs in `/report` are **energy charges only**; fixed charges and taxes appear in `/bill`.

### Example bill

```json
{
  "year": 2026, "month": 11, "days": 30, "total_kwh": 62.7,
  "tariff": { "id": 1, "name": "Flat", "tariff_type": "flat" },
  "lines": [
    { "label": "Energy charge", "kind": "energy", "amount": 407.55, "detail": "62.7 kWh @ 6.5" },
    { "label": "Meter rent", "kind": "fixed_monthly", "amount": 50.0, "detail": "per month" },
    { "label": "Duty", "kind": "percentage", "amount": 22.88, "detail": "5% of subtotal" }
  ],
  "subtotal": 457.55, "total": 480.43, "effective_rate_per_kwh": 7.6624,
  "notes": ["Estimates from your appliance settings, not measured consumption.", "..."]
}
```

---

## Sample data

| Method | Path | Notes |
|---|---|---|
| POST | `/api/demo` | 201. Loads a labelled sample household, 9 appliances and a sample TOU tariff with invented rates. **409** unless the database is empty, so it never mixes with real data |

---

## Peak load

### `GET /api/peak-load/analysis?weekday=0..6`

All power values are **kW** (demand), not kWh. Omit `weekday` to analyse the day with
the highest worst-case peak (`selected_automatically: true`).

| Field | Meaning |
|---|---|
| `load_limit_kw` | Household limit, or `null` if no household is set up |
| `peak_kw` / `peak_expected_kw` | Highest worst-case / expected demand of the day |
| `headroom_kw` | Limit − peak; negative when exceeded; `null` without a limit |
| `minutes_over_limit` | Total minutes above the limit |
| `peak_windows[]` | `start_minute`, `end_minute` (may wrap midnight; 1440 = midnight), `minutes` |
| `peak_fixed_kw`, `peak_flexible_kw`, `peak_contributors[]` | Who is on at the first peak moment, at full power |
| `steps[96]` | `start_minute`, `worst_kw`, `expected_kw`, `fixed_kw`, `flexible_kw`, `appliance_ids` |
| `violations[]`, `high_demand[]`, `overlaps[]`, `conflicts[]` | Window + `max_kw` + `appliances[]` |
| `week[7]` | Each weekday's `peak_kw`, `peak_expected_kw`, `peak_start_minute`, `minutes_over_limit` |
| `appliances[]` | Lookup of names, mode, `max_kw`, `allow_simultaneous` |
| `notes[]` | Assumptions in plain language |

422 if `weekday` is outside 0–6.

---

## Optimization

### `POST /api/optimization/run`

Solves with CP-SAT, validates the result independently, stores the run and returns it (201).
It never changes appliances, tariffs or the household.

```json
{ "priority": "balanced", "balance_weight": 50, "start_step_minutes": 60, "time_limit_seconds": 10 }
```

| Field | Rules |
|---|---|
| priority | `cost`, `peak`, `balanced` (default) |
| balance_weight | 0-100, percent importance of cost; only used for `balanced` |
| start_step_minutes | 15, 30 or 60 (default 60) |
| time_limit_seconds | 1-60 (default 10) |

**422** when the problem cannot be solved as configured: no flexible appliances (field
`appliances`), or a cost/balanced goal without an active tariff (field `priority`).
An **infeasible** problem is a successful request: status `INFEASIBLE` with `diagnostics[]`.

Response fields:

| Field | Meaning |
|---|---|
| `status`, `proven_optimal` | solver status; `proven_optimal` is true only for OPTIMAL |
| `schedule_valid` | a schedule was found **and** all independent checks passed |
| `items[]` | per flexible appliance: usual start, recommended start/end, `moved`, `reasons[]` |
| `baseline`, `optimized` | metrics: `weekly_energy_charge`, `monthly_bill`, `peak_kw`, `peak_expected_kw`, `minutes_over_limit`, `conflict_minutes` |
| `monthly_savings` | baseline − optimized bill; **negative means it costs more**; null without a priced tariff |
| `peak_reduction_kw` | baseline − optimized peak |
| `validation[]` | the independent checks: code, label, passed, detail |
| `diagnostics[]` | for INFEASIBLE: causes with plain explanations |
| `stages[]` | each objective stage: name, status, value, seconds |
| `profile` | before/after 96-step load of the worst baseline weekday |
| `solver`, `random_seed`, `solve_time_ms` | reproducibility metadata |
| `notes[]` | assumptions |

### `GET /api/optimization/history`

Most recent runs first (up to 50): id, created_at, priority, status, schedule_valid,
solve_time_ms, moved_count, baseline/optimized bill and peak.

### `GET /api/optimization/{id}`

The stored run exactly as it was returned. 404 if missing.

---

## Simulation Lab

Scenarios are what-if changes applied to **copies** of your data. No endpoint here modifies
appliances, tariffs or the household. *(The Stage 0 plan listed `POST /api/simulations/compare`;
the list endpoint returns every scenario with its latest result, which is all a comparison needs.)*

### Scenario body (`POST` and `PUT`)

```json
{
  "name": "Add bedroom AC",
  "description": "A second AC",
  "priority": "cost",
  "balance_weight": 50,
  "changes": [
    { "type": "add_appliance", "appliance": { "...": "same fields as POST /api/appliances" } },
    { "type": "replace_appliance", "appliance_id": 2, "appliance": { "...": "full appliance as it should be" } },
    { "type": "remove_appliance", "appliance_id": 4 },
    { "type": "change_tariff", "tariff_id": 3 },
    { "type": "set_load_limit", "max_load_kw": 8 }
  ]
}
```

| Field | Rules |
|---|---|
| name | 1-100 characters; unique ignoring case (409) |
| priority, balance_weight | as for the Smart Scheduler |
| changes | 0-30 items; `type` selects the shape (unknown types are 422). An empty list compares scheduling goals on today's data |
| `add_appliance`, `replace_appliance` | full appliance, validated like a real one; names must stay unique in the scenario |
| `replace_appliance`, `remove_appliance` | `appliance_id` must exist and not be removed by an earlier change |
| `change_tariff` | an existing saved tariff |

A scenario that cannot be applied is rejected with field paths such as `changes.0.appliance_id`
or `changes.1.appliance.flexible.run_duration_minutes`; nothing is saved.

### Endpoints

| Method | Path | Notes |
|---|---|---|
| GET | `/api/simulations` | By name; each with `change_descriptions`, `latest_result` and `result_is_stale` (edited after the latest result) |
| POST | `/api/simulations` | 201 |
| GET / PUT / DELETE | `/api/simulations/{id}` | 404 if missing; DELETE also deletes results (204) |
| POST | `/api/simulations/{id}/run` | 201, the stored result. 422 (with field paths) if the scenario no longer fits the current household |
| GET | `/api/simulations/{id}/results` | Up to 20, newest first |

### Result

| Field | Meaning |
|---|---|
| `baseline` | your **actual** household today at its usual times (never modified) |
| `scenario` | the scenario household at usual times, before scheduling |
| `optimized` | the scenario after CP-SAT scheduling; `null` if not attempted, infeasible or failed validation |
| `kwh_change`, `bill_change` | scenario − baseline (positive = costs more) |
| `optimized_bill_change` | optimised scenario − baseline (negative = saves overall) |
| `optimization_savings` | scenario bill − optimised bill: what scheduling alone recovers |
| `peak_change_kw` | peak after scheduling when available, else at usual times, minus baseline peak |
| `status`, `proven_optimal`, `schedule_valid`, `optimization_note` | scheduling outcome; `status` is `null` when scheduling was not attempted (no flexible appliances, or cost goal without a tariff) and the note says why |
| `items`, `validation`, `diagnostics`, `change_descriptions`, `notes` | as for the Smart Scheduler, plus generated descriptions of each change |

Money is for the current calendar month. All figures are estimates.
