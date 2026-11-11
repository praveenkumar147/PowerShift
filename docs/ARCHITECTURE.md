# Architecture

*Describes what is implemented. Last updated: Stage 6.*

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
| `optimization/` | CP-SAT scheduler: `problem`, `builder`, `runner`, `validation`, `diagnose`, `explain`, `metrics` | domain, calculation (never `db/` or `api/`) |
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

## Peak load analysis (`calculation/peak_load.py`)

Works only in **kW (power)**. For each 15-minute step of a weekday:

| Figure | Formula | Used for |
|---|---|---|
| Worst-case demand | Σ rated W × quantity / 1000 of appliances that are on | Load-limit violations, peak, high-demand periods |
| Expected demand | Σ worst-case × duty cycle | Context ("typical" peak) |
| Fixed / flexible split | worst case of fixed vs flexible appliances | Shows how much of the peak the scheduler could move |

Consecutive flagged steps become **windows**; a window touching both 23:45 and 00:00
is merged across midnight. Episodes found per day:

- **Violations**: worst case > load limit (exactly at the limit is fine).
- **High demand**: ≥ 80% of the limit (or of the day's peak without a limit).
- **Overlaps**: ≥ 2 appliances of ≥ 1 kW on together.
- **Conflicts**: ≥ 2 appliances marked "not simultaneous" on together.

`GET /api/peak-load/analysis` without a weekday analyses the day with the highest peak.

## Smart Scheduler pipeline

```
OptimizationService.run
 1 build_problem + validate_problem   plain inputs, integer scaling, explain unsolvable setups
 2 build_model (builder.py)            variables, constraints C-F, objective terms
 3 solve (runner.py)                   multi-stage objective; one worker + fixed seed = reproducible
 4 overall_status                      OPTIMAL only if every stage is proven optimal
 5 measure (metrics.py)                before/after bill + peak via the Stage 3-4 engines
 6 validate_schedule (validation.py)   re-check WITHOUT the solver; invalid = not shown
 7 explain / diagnose                  reasons from measured differences / causes of infeasibility
 8 store OptimizationRun (+ items)     inputs, settings, seed, versions, full result
```

`validation.py` deliberately imports nothing from OR-Tools, the builder, the runner or the
problem module (enforced by a test), so a bug in the model cannot hide itself.

## Simulation Lab and isolation

A scenario is stored as a **list of changes** (add / replace / remove an appliance, use another
saved tariff, set the load limit), never as copies of data. Running one:

```
SimulationService.run(scenario)
  read real appliances, household, active tariff        (read-only)
  simulation.scenario.apply_changes(...)                builds NEW in-memory lists; specs are immutable
  optimization.pipeline.run_pipeline(real household)    -> baseline ("current household")
  optimization.pipeline.run_pipeline(scenario household)-> usual-times metrics + CP-SAT result + validation
  write ONE row to simulation_results                   (the only write)
```

Isolation is structural, not just a promise:

- `simulation/scenario.py` and `optimization/pipeline.py` import nothing from `db/`; they cannot write.
- Domain specs are frozen dataclasses; a change builds a new object, it cannot edit the original.
- New appliances in a scenario get **negative ids**, so they can never match a real row.
- The only tables written are `simulation_scenarios` and `simulation_results`.
- A test snapshots every real table (household, appliances and children, tariffs and children)
  and the optimization history before and after creating, running, editing and deleting a
  scenario that changes everything at once, and requires identical rows.

`optimization/pipeline.py` is shared by the Smart Scheduler and the Simulation Lab (extracted in
Stage 6 with no behaviour change), so a scenario is optimised by exactly the same code as the
real household, including independent validation.

On the frontend, the appliance form accepts `onSubmitInput` so the Simulation Lab reuses it to
edit scenario appliances without saving them. While it is open the scenario dialog is not shown
(dialogs never nest) but its draft stays in the parent component.
