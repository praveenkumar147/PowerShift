# Architecture

*Describes what is implemented. Last updated: Stage 3.*

## Overview

```
┌──────────────────────── PowerShift (Tauri window) ───────────────────────┐
│  React UI (WebView2)                                                      │
│     │ 1. invoke("backend_status")  ──►  Rust shell                         │
│     │                                   │ starts python -m powershift       │
│     │                                   │ --port 0 --token <random>         │
│     │                                   ▼                                   │
│     │                         Python backend prints "POWERSHIFT_READY port=N"│
│     │ 2. HTTP http://127.0.0.1:N/api/...  (header X-PowerShift-Token)       │
│     └────────────────────────────►  FastAPI → SQLite (powershift.db)       │
└───────────────────────────────────────────────────────────────────────────┘
```

## Folder layout

| Path | Purpose |
|---|---|
| `src/` | React frontend |
| `src/app/` | App shell: providers, router, sidebar, theme, startup screen |
| `src/api/` | Backend discovery (`connection.ts`), HTTP client (`client.ts`), query hooks |
| `src/components/ui/` | Reusable UI primitives (Button, Card, EmptyState, PageHeader, Spinner) |
| `src/features/<module>/` | One folder per product module |
| `src-tauri/` | Rust desktop shell; `src/backend.rs` manages the Python process |
| `backend/powershift/` | Python backend package |
| `backend/tests/` | `unit/` and `integration/` tests |
| `docs/` | Project documentation |

## Backend layers

| Package | Responsibility | May import |
|---|---|---|
| `api/` | HTTP routes only: parse the request, call a service, return a schema | services, schemas, core |
| `schemas/` | Pydantic request/response models; per-field checks (types, ranges, 15-minute steps) | domain, calculation |
| `services/` | Use cases: validate, persist, attach estimates and warnings. One request = one transaction | domain, calculation, db, schemas |
| `domain/` | Pure dataclasses and rules (`ApplianceSpec`, `TimeWindow`, `validate_appliance`) | — |
| `calculation/` | Pure formulas: `appliance_energy.py` (rated vs average power), `load_profile.py` (96 × 15-minute average-kW profile per appliance per weekday), `tariff_engine.py` (step prices, slabs, itemised bill), `energy_model.py` (periods, months, hours) | domain |
| `optimization/` | CP-SAT scheduler *(Stage 5)* | domain, calculation |
| `db/models/` | SQLAlchemy tables | domain (enum values for CHECK constraints) |
| `db/repositories/` | Queries, plus conversion between rows and domain objects | db/models, domain |
| `core/` | Config, errors, logging | — |

`domain/` and `calculation/` never import `db/` or `api/`, so the formulas and rules
are tested without a database (`backend/tests/unit/`).

### Where validation happens

1. **Frontend** (`formModel.ts`): only checks that values can be parsed (a number is a number), for fast feedback.
2. **Pydantic schema**: each field on its own (`rated_power_w > 0`, times are multiples of 15 minutes).
3. **Domain rules** (`validate_appliance`): rules involving several fields (the run fits the window; periods don't overlap).
4. **Database CHECK constraints**: the last line of defence if a bug ever bypasses the layers above.

Every error is returned with the API field path as its key (e.g. `flexible.current_start_minute`),
so the UI shows each message next to the right input.

## Backend startup sequence (`powershift/main.py`)

1. Parse `--data-dir`, `--port`, `--token`.
2. Create `data/`, `backups/`, `logs/`; configure a rotating log file.
3. Upgrade the database with Alembic. If an existing database needs migrating, copy it to `backups/` first.
4. Bind a socket on `127.0.0.1`. Port `0` lets Windows pick a free port, so there are never port clashes.
5. Print `POWERSHIFT_READY port=<n>` on stdout.
6. Serve with Uvicorn.

## Desktop shell (`src-tauri/src/backend.rs`)

- **Development** (`npm run tauri dev`): runs `backend/.venv/Scripts/python.exe -m powershift`, data in `backend/.data/`.
- **Production** (Stage 9): will run the PyInstaller-frozen `powershift-backend.exe` from the bundle's resources, data in `%APPDATA%\com.powershift.app\`. *This path is written but not yet tested.*
- Starts the backend on a background thread so the window appears immediately.
- Waits up to 45 s for the READY line; reports the exit code and last stderr lines on failure.
- Assigns the process to a Windows **Job Object** with kill-on-close, so the backend can never be left running, even if the app crashes.
- Kills the backend on normal exit.
- Exposes one command, `backend_status`, returning `starting` / `ready {port, token}` / `failed {message}`.

## Security model

- The backend listens only on `127.0.0.1`.
- A 256-bit random token is generated at every launch; every `/api` request must send it in `X-PowerShift-Token` (compared in constant time).
- CORS only allows the Tauri origin (`http://tauri.localhost`) and the Vite dev server.
- The Tauri content security policy only allows connections to `127.0.0.1` and Tauri IPC.
- Interactive API docs (`/docs`) are disabled whenever a token is set.
- Errors returned to the UI never contain stack traces; details go to `logs/backend.log`.

## Frontend structure

- `App.tsx`: `ThemeProvider` → `BackendProvider` (startup screen until the backend is ready) → `QueryClientProvider` → hash router.
- Hash routing (`#/appliances`) is used because the packaged app loads files locally, where there is no server to rewrite URLs.
- Server state uses TanStack Query. Components don't call `fetch` directly; they use typed hooks in `src/api/`.
- Colours are semantic design tokens (CSS variables) in `src/index.css`, switched by a `.dark` class.
- Modules that aren't built yet show an honest "Not built yet" page with no fake data and no buttons.

## Energy and cost calculation pipeline

```
appliance settings ──► load_profile ──► 7 weekday profiles per appliance (96 steps of average kW)
                                              │
active tariff ──► tariff_engine.step_prices ──┤  (price per step; none for slab tariffs)
                                              ▼
                                   energy_model.EnergyModel
             precomputes, per appliance per weekday: kWh, and kWh × price (flat/TOU)
                                              │
     any period = Σ over weekdays (number of that weekday in the period × its values)
                                              │
       ┌────────────────────┬─────────────────┼──────────────────┬───────────────────┐
  period report      hourly profile    monthly projection    monthly bill (tariff_engine.compute_bill)
```

- Energy uses **average power** (rated × quantity × duty cycle); every value is an estimate.
- Money is `Decimal` end to end; each printed bill line is rounded to 2 decimals, and
  percentages apply to the sum of the printed lines, so the bill can be checked by hand.
- Slab tariffs price the **monthly household total**; individual appliances and days are
  priced at that month's average energy rate (stated in the report notes).

## Frontend data flow

- Server data is cached by TanStack Query under keys: `appliances`, `household`, `tariffs`, `energy`.
- Any change to appliances, tariffs, the household or sample data invalidates the `energy`
  queries, so every chart recalculates from the backend.
- Charts (Recharts) each have a "Show data table" view; colours are CSS tokens
  (`--ps-series-1/2`) validated for colour-blind separation and contrast in both themes.
