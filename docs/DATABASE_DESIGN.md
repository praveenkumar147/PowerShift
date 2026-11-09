# Database Design

*Describes the schema that exists now. Last updated: Stage 3 (revision `0003`).*
The full planned schema is in [STAGE0_PLAN.md §6](STAGE0_PLAN.md#6-initial-database-design).

## Engine

- SQLite, one file: `powershift.db` in the data directory.
- `PRAGMA foreign_keys=ON` on every connection (SQLite has foreign keys off by default).
- `PRAGMA journal_mode=WAL` (write-ahead log: safer on crashes, readers don't block writers).
- All timestamps are stored in UTC.
- Every constraint has a deterministic name (naming convention in `db/base.py`) so Alembic can rebuild SQLite tables safely.

## Migrations

| Revision | Adds |
|---|---|
| `0001` | `household`, `app_settings` |
| `0002` | `appliances`, `appliance_operating_days`, `appliance_usage_blocks`, `appliance_flex_constraints` |
| `0003` | `tariffs`, `tariff_periods`, `tariff_slabs`, `tariff_charges` |

- Alembic scripts live in `backend/powershift/db/migrations/versions/`.
- The backend upgrades the database to the latest revision automatically at startup.
- Before migrating an **existing** database, it copies it to `backups/pre-migration-<revision>-<timestamp>.db` using SQLite's online backup API.
- To create a new migration during development:

```bash
cd backend && .venv/Scripts/alembic revision --autogenerate -m "describe change"
```

  **Always read the generated file.** Example: in `0002`, autogenerate silently skipped
  the case-insensitive unique index on appliance names (SQLite expression indexes can't
  be compared), so it was added by hand.

## Time representation

Times of day are integers: **minutes since midnight**, in 15-minute steps.

- Start times: 0–1439. End times: 1–1440 (1440 = midnight at the end of the day).
- If `end <= start`, the period wraps past midnight: 22:00–06:00 is `(1320, 360)`.
- `(0, 1440)` is the whole day.

Integers avoid time-zone and date problems, make window arithmetic simple
(`(minute - start) mod 1440`), and convert directly to hourly or 15-minute scheduling slots.

## Tables

### `household` (one row)

| Column | Type | Rules |
|---|---|---|
| id | INTEGER PK | |
| name | VARCHAR(100) | required |
| occupants | INTEGER | ≥ 1 (CHECK) |
| location_label | VARCHAR(100) | optional, display only; never used to guess a tariff |
| max_load_kw | FLOAT | > 0 (CHECK); instantaneous power limit, in kW |
| currency_code | VARCHAR(3) | ISO 4217, display only |
| time_format | VARCHAR(3) | `12h` or `24h` (CHECK) |
| created_at, updated_at | DATETIME (UTC) | |

### `app_settings` (one row, not yet used by the API)

| Column | Type | Rules |
|---|---|---|
| id | INTEGER PK | |
| theme | VARCHAR(10) | `system`, `light`, `dark` (CHECK) |
| default_optimization_priority | VARCHAR(10) | `cost`, `peak`, `balanced` (CHECK) |
| created_at, updated_at | DATETIME (UTC) | |

### `appliances`

| Column | Type | Rules |
|---|---|---|
| id | INTEGER PK | |
| name | VARCHAR(100) | unique ignoring case (index `uq_appliances_name_lower` on `lower(name)`) |
| category | VARCHAR(20) | cooling, lighting, kitchen, laundry, entertainment, water_heating, electronics, other (CHECK) |
| rated_power_w | FLOAT | > 0; nameplate power of one unit |
| quantity | INTEGER | ≥ 1 |
| duty_cycle | FLOAT | 0 < x ≤ 1; share of on-time at rated power |
| mode | VARCHAR(10) | `fixed` or `flexible` |
| priority | VARCHAR(10) | `low`, `medium`, `high` |
| allow_simultaneous | BOOLEAN | false = must not overlap other "false" appliances |
| created_at, updated_at | DATETIME (UTC) | |

Index: `(category, mode)` for filtering.

### `appliance_operating_days`

| Column | Type | Rules |
|---|---|---|
| id | INTEGER PK | |
| appliance_id | FK → appliances.id, ON DELETE CASCADE | indexed |
| weekday | INTEGER | 0 = Monday … 6 = Sunday; unique per appliance |

### `appliance_usage_blocks` (fixed appliances)

| Column | Type | Rules |
|---|---|---|
| id | INTEGER PK | |
| appliance_id | FK → appliances.id, ON DELETE CASCADE | indexed |
| start_minute | INTEGER | 0–1439 |
| end_minute | INTEGER | 1–1440; may be ≤ start (wraps midnight) |

Blocks of one appliance must not overlap (checked in `domain/appliance.py`).

### `appliance_flex_constraints` (flexible appliances, 1:1)

| Column | Type | Rules |
|---|---|---|
| appliance_id | PK and FK → appliances.id, ON DELETE CASCADE | primary key = foreign key enforces one row per appliance |
| run_duration_minutes | INTEGER | 1–1440 (API: 15–1440 in 15-minute steps) |
| earliest_start_minute | INTEGER | 0–1439 |
| latest_end_minute | INTEGER | 1–1440 |
| current_start_minute | INTEGER | 0–1439; the user's current habit, the baseline for savings |
| preferred_start_minute, preferred_end_minute | INTEGER NULL | both set or both NULL (CHECK) |
| must_be_contiguous | BOOLEAN | |

### `tariffs`

| Column | Type | Rules |
|---|---|---|
| id | INTEGER PK | |
| name | VARCHAR(100) | |
| tariff_type | VARCHAR(10) | `flat`, `tou`, `slab` |
| effective_date | DATE | informational |
| flat_rate_per_kwh | NUMERIC(14,4) NULL | ≥ 0; set only for `flat` |
| slab_mode | VARCHAR(15) | `telescopic` (each slab at its own rate) or `whole_usage` (all units at the highest slab reached) |
| is_active | BOOLEAN | partial unique index `uq_tariffs_single_active ... WHERE is_active = 1`: at most one active tariff |
| created_at, updated_at | DATETIME (UTC) | |

Money columns use `NUMERIC(14,4)` and Python `Decimal`, never floats.

### `tariff_periods` (time-of-use)

| Column | Type | Rules |
|---|---|---|
| id | INTEGER PK | |
| tariff_id | FK → tariffs.id, ON DELETE CASCADE | indexed |
| position | INTEGER | display order |
| day_type | VARCHAR(10) | `all`, `weekday` (Mon–Fri), `weekend` (Sat–Sun) |
| start_minute / end_minute | INTEGER | as for appliance windows; may wrap midnight |
| rate_per_kwh | NUMERIC(14,4) | ≥ 0 |

Rule (checked in `domain/tariff.py`): either `all` periods alone, or `weekday` + `weekend`
sets; each set must cover every 15 minutes of the day exactly once.

### `tariff_slabs`

| Column | Type | Rules |
|---|---|---|
| id, tariff_id, position | | as above |
| up_to_kwh | NUMERIC(14,3) NULL | > 0; increasing; NULL only on the last slab ("and above") |
| rate_per_kwh | NUMERIC(14,4) | ≥ 0 |

### `tariff_charges`

| Column | Type | Rules |
|---|---|---|
| id, tariff_id, position | | as above |
| kind | VARCHAR(15) | `fixed_monthly`, `per_kwh`, `percentage` |
| label | VARCHAR(100) | |
| amount | NUMERIC(14,4) | ≥ 0; ≤ 100 for `percentage` |

### Why separate child tables instead of JSON columns?

Foreign keys, CHECK constraints and cascading deletes keep the data valid inside the
database itself, and the scheduler can later query "all flexible appliances" with plain SQL.

## Design notes for updates

- **Operating days are updated by difference** (remove missing days, add new ones), not by
  delete-all-then-insert. In one flush, SQLAlchemy may insert the new `(appliance, weekday)` row
  before deleting the old identical one, which would break the unique constraint.
- **The flexible-constraint row is updated in place**: its primary key is the appliance id,
  so replacing the object would try to insert a duplicate key.
