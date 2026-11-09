# Database Design

*Describes the schema that exists now. Last updated: Stage 1 (revision `0001`).*
The full planned schema is in [STAGE0_PLAN.md §6](STAGE0_PLAN.md#6-initial-database-design).

## Engine

- SQLite, one file: `powershift.db` in the data directory.
- `PRAGMA foreign_keys=ON` on every connection (SQLite has foreign keys off by default).
- `PRAGMA journal_mode=WAL` (write-ahead log: safer on crashes, readers don't block writers).
- All timestamps are stored in UTC.
- Every constraint has a deterministic name (naming convention in `db/base.py`) so Alembic can rebuild SQLite tables safely.

## Migrations

- Alembic scripts live in `backend/powershift/db/migrations/versions/`.
- The backend upgrades the database to the latest revision automatically at startup.
- Before migrating an **existing** database, it copies it to `backups/pre-migration-<revision>-<timestamp>.db` using SQLite's online backup API.
- To create a new migration during development:

```bash
cd backend && .venv/Scripts/alembic revision --autogenerate -m "describe change"
```

  Always read the generated file before committing it.

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

### `app_settings` (one row)

| Column | Type | Rules |
|---|---|---|
| id | INTEGER PK | |
| theme | VARCHAR(10) | `system`, `light`, `dark` (CHECK) |
| default_optimization_priority | VARCHAR(10) | `cost`, `peak`, `balanced` (CHECK) |
| created_at, updated_at | DATETIME (UTC) | |

### `alembic_version`

Managed by Alembic; stores the current schema revision.
