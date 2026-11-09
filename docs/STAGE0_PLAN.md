# PowerShift — Stage 0: Audit and Implementation Plan

Status: **Draft, waiting for approval.** No application code has been written.
Audit date: 2026-11-09

---

## 1. Environment audit (what was actually checked)

| Item | Result | Verdict |
|---|---|---|
| Project folder | Empty (this plan is the first file) | Clean start, nothing to preserve |
| Git | 2.53 installed; folder is **not** a repository | Recommend local `git init` (no GitHub needed) |
| Default `python` | **3.15.0a7 (alpha)** | ❌ Do not use: no OR-Tools wheel exists for 3.15 (verified, pip found no distribution) |
| Python 3.13 | 3.13.12 via `py -3.13` | ✅ Use this. OR-Tools `9.15.6755-cp313-win_amd64` wheel verified available |
| Python 3.12 / 3.11 | Also installed | Fallback only |
| Node.js / npm | 24.14.1 / 11.11.0 | ✅ |
| Rust (rustup, cargo, rustc) | **Not installed** | ❌ Required by Tauri |
| MSVC C++ Build Tools | **Not installed** (no Visual Studio installer found) | ❌ Required by Rust on Windows (linker) |
| WebView2 runtime | 157.0.4341.42 | ✅ Tauri renders the UI with it |
| Hardware | i5-12500H, 15.7 GB RAM, 93 GB free, x64 | ✅ More than enough |

### Required installs before Stage 1

1. **Visual Studio 2022 Build Tools** with the *Desktop development with C++* workload (~6–8 GB, needs admin).
2. **Rust** via `rustup` (stable, `x86_64-pc-windows-msvc` toolchain).
3. Nothing else system-wide. All Python packages go into a project virtual environment
   created with `py -3.13 -m venv`; all JS packages go into `node_modules`.

Later (Stage 9 only): PyInstaller (pip, inside the venv) to freeze the backend; the Tauri
bundler downloads WiX/NSIS on first build.

---

## 2. Feasibility assessment

**Feasible.** Every requested technology runs offline on Windows. Points that need care:

- **Python version:** must pin to 3.13 (see audit). Your global default (3.15 alpha) would break OR-Tools.
- **Python inside a Tauri app:** Tauri does not run Python itself. The backend is frozen into a
  Windows executable with PyInstaller and launched by the Tauri (Rust) side. This is the
  standard, proven approach; details in §4.4.
- **Optimization size:** a 24-hour, hourly model for a household (≤ ~30 flexible appliances)
  has at most a few thousand boolean variables. CP-SAT solves this in milliseconds to
  well under a second. 15-minute slots (96 per day) remain small.
- **Honest limitation:** all consumption is *estimated* from user-entered configuration. There is
  no measured data, so "trends" are projections plus saved historical calculation snapshots,
  and the UI will say so.

---

## 3. Recommended folder structure

Tauri's convention is a web project at the root with `src-tauri/` beside it. Python lives in
its own `backend/` folder with its own tests.

```
powershift/
├─ README.md, package.json, vite.config.ts, tsconfig.json, index.html
├─ docs/                     ARCHITECTURE.md, DATABASE_DESIGN.md, API_DOCUMENTATION.md,
│                            OPTIMIZATION_MODEL.md, TESTING.md, DEVELOPMENT_LOG.md, USER_GUIDE.md
├─ src/                      React + TypeScript frontend
│  ├─ app/                   App shell, router, providers (theme, query client)
│  ├─ components/ui/         Reusable primitives: Button, Card, Dialog, Input, Table, EmptyState…
│  ├─ components/charts/     Recharts wrappers (LoadProfileChart, BreakdownChart…)
│  ├─ features/              One folder per module
│  │   ├─ overview/  appliances/  tariffs/  energy/  peak-load/
│  │   └─ scheduler/ simulation/  reports/  settings/
│  ├─ api/                   Typed API client + generated/handwritten response types
│  ├─ lib/                   Formatting (units, currency, time), helpers
│  └─ test/                  Vitest setup
├─ src-tauri/                Rust desktop shell
│  ├─ src/main.rs, lib.rs    Window setup, backend process manager
│  ├─ tauri.conf.json        App config, bundling, resources
│  └─ capabilities/          Tauri v2 permission files
└─ backend/
   ├─ pyproject.toml         Dependencies + tool config (pytest, ruff, mypy)
   ├─ alembic.ini, migrations/
   ├─ powershift/
   │  ├─ main.py             FastAPI app factory + startup args (port, data dir, token)
   │  ├─ api/                Routers only: parse request → call service → return schema
   │  ├─ schemas/            Pydantic request/response models
   │  ├─ services/           Use cases; transaction boundaries
   │  ├─ domain/             Pure dataclasses: Appliance, Tariff, DayProfile… (no DB, no HTTP)
   │  ├─ calculation/        Energy, demand, tariff/bill engines (pure functions)
   │  ├─ optimization/       CP-SAT model builder, solver runner, validator, explainer
   │  ├─ db/                 SQLAlchemy models, session, repositories
   │  ├─ reports/            CSV and PDF builders
   │  └─ core/               Config, errors, logging, paths
   └─ tests/                 unit/ (calculation, optimization), integration/ (API + DB)
```

Rule of the layers: **calculation/ and optimization/ never import db/ or api/.** They take
plain domain objects and return plain results. That makes them easy to unit-test and to
explain.

---

## 4. Architecture

### 4.1 Big picture

```
┌──────────────────────── PowerShift.exe (Tauri) ─────────────────────────┐
│  WebView2 window  ──HTTP (127.0.0.1:<random port>, token header)──┐      │
│  React UI                                                          │      │
│                                                                    ▼      │
│  Rust shell: starts/stops ─────────────►  powershift-backend.exe (Python) │
│                                           FastAPI → services → engines    │
│                                                         │                 │
│                                                         ▼                 │
│                              %APPDATA%\PowerShift\powershift.db (SQLite)  │
└──────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Request flow example — "Optimize my schedule"

1. React calls `POST /api/optimization/run` with `{ "priority": "balanced" }`.
2. Router validates the body with Pydantic and calls `OptimizationService.run()`.
3. Service loads household, appliances and active tariff through repositories and converts
   them to domain objects.
4. `optimization.builder` creates the CP-SAT model; `optimization.runner` solves it.
5. `optimization.validator` re-checks the schedule with plain Python (not the solver).
6. `optimization.explainer` compares baseline vs optimized and produces reasons.
7. Service saves the run (inputs snapshot, parameters, status, results) in one transaction.
8. Router returns a typed response; React renders charts and the schedule table.

### 4.3 Frontend

- React + TypeScript (strict), Vite, Tailwind CSS, Lucide icons, Recharts.
- **React Router** for the 9 sections and **TanStack Query** for server state (caching,
  loading/error states, refetch after mutations). These two are small, standard additions I
  recommend; they replace a lot of hand-written fetch/loading code. *(Needs your approval.)*
- Forms: plain controlled components + shared validation helpers; the backend is the source
  of truth for validation and returns field-level errors.
- Theme: Tailwind `dark` class, stored in the settings table.

### 4.4 Desktop shell and backend lifecycle (the key integration decision)

**Development:** you run `npm run tauri dev`. Tauri starts Vite; the Rust shell starts the
backend with `.venv\Scripts\python -m powershift.main` so code changes reload quickly.

**Production (recommended approach):**

1. PyInstaller freezes the backend in **one-folder mode** (`--onedir`) and the folder is
   shipped as a Tauri *resource*.
   - Why not one-file mode? One-file unpacks itself to a temp folder on every launch (slow
     start, 3–10 s) and is more often flagged by antivirus software.
2. On app start, Rust:
   - asks the OS for a free localhost port,
   - generates a random per-launch token,
   - starts `powershift-backend.exe --port P --data-dir <app data dir> --token T`
     inside a **Windows Job Object** so the backend is killed even if the app crashes,
   - polls `GET /api/health` until ready (timeout → friendly error screen with log path),
   - passes `P` and `T` to the frontend through a Tauri command.
3. On window close, Rust stops the backend.

Security: the backend binds only to `127.0.0.1`, and every request must carry the token, so
other local programs or web pages cannot read or change your data. CORS is limited to the
Tauri origin.

Alternative: Tauri's built-in "sidecar" feature (`externalBin`). It is simpler to configure but
expects a single executable (i.e. one-file mode, with the drawbacks above). *(Approval item.)*

### 4.5 Data location

- Production: `%APPDATA%\com.powershift.app\powershift.db` (Tauri's app data dir), plus
  `backups\` and `logs\` next to it.
- Development: `backend/.data/powershift.db` (git-ignored).
- Alembic migrations run automatically on backend start; a backup copy is made before any
  migration that changes an existing database.

---

## 5. Modeling decisions (the engineering core)

### 5.1 Rated power vs estimated actual consumption

- **Rated power (W)** — nameplate maximum, e.g. a fridge says 150 W.
- **Duty cycle (0–1)** — fraction of time the appliance actually draws that power. A fridge
  compressor runs about 30–50% of the time.
- **Estimated average power** = rated W × duty cycle × quantity.

Formulas (all in code exactly like this):

```
Power demand (kW) in slot t      = rated_W × quantity × duty_cycle × on(t) / 1000
Energy (kWh) in slot t           = Power (kW) × slot_length_hours
Daily energy (kWh)               = Σ over slots of Energy(t)
```

Peak-load analysis uses two numbers per slot, and the UI shows both:
- **Expected demand** (uses duty cycle) — used for energy and cost.
- **Worst-case demand** (duty cycle = 1, everything that is "on" draws rated power) — used for
  load-limit warnings, because a breaker trips on instantaneous power, not on averages.

kW (power, a rate) and kWh (energy, an amount) are separate types in the domain code so they
can't be mixed accidentally.

### 5.2 Day model

- 24 hourly slots, slot length a configurable constant (designed so 15-min = 96 slots works later).
- The day is **cyclic**: a window like 22:00 → 06:00 wraps past midnight. This matters for
  water heaters and dishwashers that typically run overnight.
- Fixed appliances: a set of on-hours ("usual hours") + duty cycle → baseline load.
- Flexible appliances: run duration, allowed window, and **current usual start time**. The
  current start time is essential: it defines the *baseline* schedule that savings are
  measured against. Without it, "savings" would be meaningless.
- Operating days (Mon–Sun) and runs per week turn a typical-day result into weekly/monthly
  estimates: monthly kWh = Σ per weekday (daily kWh × occurrences of that weekday in the month).

### 5.3 Tariffs

- **Flat:** one price per kWh.
- **Time-of-use (TOU):** price periods by hour range and day type.
- **Slab:** price depends on cumulative monthly kWh (e.g. 0–100 kWh at rate A, 101–200 at B).
  Applied to the *monthly* total, never per slot.
- **Charges:** fixed (per month), per-kWh additional, and percentage (tax) applied in a
  defined order: energy charge → fixed/additional → percentage adjustments.

Important honest consequence, which the app will explain to the user: **moving an appliance
to a different hour does not change the bill under a flat or slab tariff**, because the total
kWh stays the same. Only TOU tariffs reward shifting. Under flat/slab tariffs the optimizer
still helps by reducing peak demand.

---

## 6. Initial database design

All tables have integer primary keys, `created_at` / `updated_at`. Money is stored as
`Numeric` (no float rounding errors); energy/power as `Float` with documented units in the
column name (`rated_power_w`, `max_load_kw`).

| Table | Purpose | Key columns / relations |
|---|---|---|
| `household` | Single household profile (one row) | name, occupants, location_label, max_load_kw, currency, time_format, `active_tariff_id` → tariffs |
| `app_settings` | Preferences | theme, default_optimization_priority, schema_version info |
| `appliances` | Appliance definitions | name, category (enum), rated_power_w, quantity, duty_cycle, mode (fixed/flexible), priority, allow_simultaneous, runs_per_week, active |
| `appliance_operating_days` | Which weekdays it runs | appliance_id FK, weekday (0–6); unique(appliance_id, weekday) |
| `appliance_usage_blocks` | Fixed appliances' usual on-hours | appliance_id FK, start_slot, end_slot |
| `appliance_flex_constraints` | Flexible appliances only (1:1) | appliance_id FK unique, run_duration_slots, earliest_start_slot, latest_end_slot, current_start_slot, must_be_contiguous |
| `tariffs` | Tariff header | name, type (flat/tou/slab), effective_date, flat_rate, is_estimate |
| `tariff_periods` | TOU periods | tariff_id FK, start_slot, end_slot, day_type, rate_per_kwh |
| `tariff_slabs` | Slabs | tariff_id FK, from_kwh, to_kwh (nullable = ∞), rate_per_kwh |
| `tariff_charges` | Fixed / per-kWh / percentage charges | tariff_id FK, kind, label, amount, apply_order |
| `calculation_snapshots` | Saved energy/bill calculations (history) | created_at, period, tariff_id, inputs_json, results_json |
| `optimization_runs` | One per solver run | priority, status, objective_value, solve_time_ms, solver_params_json, inputs_snapshot_json, app_version, baseline_cost, optimized_cost, baseline_peak_kw, optimized_peak_kw, validation_passed |
| `optimization_run_items` | Scheduled tasks of a run | run_id FK, appliance_id (nullable if deleted later), appliance_name, start_slot, end_slot, baseline_start_slot, reasons_json |
| `simulation_scenarios` | What-if scenarios | name, description, base_snapshot_json, changes_json |
| `simulation_results` | Results per scenario run | scenario_id FK, optimization_run_id FK (nullable), kwh, cost, peak_kw, created_at |

Indexes: foreign keys, `appliances(category, mode)`, `optimization_runs(created_at)`,
`simulation_results(scenario_id, created_at)`.

Why JSON snapshots in runs and scenarios? Reproducibility and isolation. An optimization run
stores *exactly* what the solver saw, so it can be re-run or investigated even after the user
edits appliances. A scenario stores its own copy of the household, so simulations can never
modify real data.

---

## 7. API design

All under `/api`, JSON in/out, Pydantic schemas, errors as
`{ "error": { "code": "...", "message": "...", "fields": {...} } }` with no stack traces.

| Area | Endpoints |
|---|---|
| Health | `GET /api/health` |
| Household | `GET /api/household`, `PUT /api/household` |
| Appliances | `GET /api/appliances?category=&mode=&q=`, `POST /api/appliances`, `GET/PUT/DELETE /api/appliances/{id}` |
| Tariffs | `GET /api/tariffs`, `POST /api/tariffs`, `GET/PUT/DELETE /api/tariffs/{id}`, `POST /api/tariffs/{id}/activate` |
| Energy | `GET /api/energy/summary`, `GET /api/energy/appliance-breakdown`, `GET /api/energy/category-breakdown`, `GET /api/energy/hourly-profile`, `GET /api/energy/projection?from=&to=`, `POST /api/energy/snapshots`, `GET /api/energy/snapshots` |
| Peak load | `GET /api/peak-load/analysis` |
| Optimization | `POST /api/optimization/run`, `GET /api/optimization/history`, `GET /api/optimization/{id}` |
| Simulation | `POST /api/simulations`, `GET /api/simulations`, `GET/PUT/DELETE /api/simulations/{id}`, `POST /api/simulations/{id}/run`, `GET /api/simulations/{id}/results`, `POST /api/simulations/compare` |
| Reports | `POST /api/reports/export` (`{type, format: csv\|pdf, params}` → file saved to a user-chosen path) |
| Settings | `GET/PUT /api/settings`, `POST /api/settings/backup`, `POST /api/settings/restore`, `POST /api/settings/export`, `POST /api/settings/reset`, `GET /api/settings/about` |
| Demo data | `POST /api/demo/load` (clearly labeled sample household; only allowed when DB is empty) |

Status codes: 200/201/204 success, 404 missing, 409 conflict (e.g. deleting the active
tariff), 422 validation, 500 generic internal error (details only in the local log file).

---

## 8. Optimization model overview (CP-SAT)

Plain-language version: *"For every flexible appliance, pick one start hour from the hours it
is allowed to start, so that each appliance runs for its required time inside its window, the
house never exceeds its load limit, and the total cost and/or peak is as small as possible."*

**Inputs:** slots T = {0..23}; flexible appliances A; for each a: power Pₐ (W), duration dₐ,
allowed start set Sₐ (derived from window, wrapping past midnight); baseline load Bₜ from
fixed appliances; price cₜ per kWh; load limit L.

**Decision variables**
- `x[a,s] ∈ {0,1}` — appliance a starts at slot s (one per allowed start).
- `on[a,t]` — derived: 1 if a is running in slot t (sum of starts that cover t).
- `peak` — integer, the highest household load in any slot.

**Constraints**
1. Each appliance starts exactly once: Σₛ x[a,s] = 1. → guarantees required duration.
2. Contiguity: a start at s covers slots s…s+dₐ−1 (mod 24), so runs are uninterrupted by construction.
3. Window: only starts whose whole run fits inside the window are created at all.
4. Load: Bₜ + Σₐ Pₐ·on[a,t] ≤ L for every t (worst-case power).
5. Peak definition: peak ≥ Bₜ + Σₐ Pₐ·on[a,t] for every t.
6. No-overlap pairs: if two appliances are marked "not simultaneous", Σ on[a,t] ≤ 1 per t.

**Objective**
- Cost(x) = Σₜ cₜ · (energy in slot t), scaled to integers (CP-SAT needs integer coefficients;
  prices in 1/1000 currency units, power in watts).
- *Lowest cost*: two stages — minimize cost; then fix cost at its optimum and minimize peak
  (tie-break, so we never pick a needlessly peaky schedule).
- *Lowest peak*: the reverse order.
- *Balanced*: minimize w·(Cost/Cost_ref) + (1−w)·(Peak/Peak_ref), where the "ref" values are
  the baseline cost and baseline peak. Dividing by the reference makes both terms unit-free
  percentages, so we never add money to kilowatts. Default w = 0.5.

**Solver handling:** fixed random seed and `num_workers` recorded for reproducibility; time
limit (e.g. 10 s). OPTIMAL → "optimal"; FEASIBLE → "best found within time limit, not proven
optimal"; INFEASIBLE → run diagnostics (e.g. "Water heater needs 3 h but window is 2 h",
"Fixed load alone already exceeds the limit at 19:00", or relax the load limit to find which
constraint group blocks a solution); UNKNOWN / MODEL_INVALID → clear error, nothing saved as valid.

**Independent validator** (plain Python, no solver): re-checks window, duration, contiguity,
load limit, no-overlap pairs, and recomputes cost and peak with the normal calculation engine.
If the solver's numbers and the validator's numbers disagree, the run is marked invalid.

**Explanations** are derived rules, e.g. "moved from 19:00 (₹8/kWh) to 13:00 (₹5/kWh)" only if
the price actually differs; "avoids overlap with Water Heater" only if they overlapped in the
baseline and don't now; "peak at 19:00 reduced from 5.2 kW to 3.4 kW" from the two profiles.

Full derivation goes into `docs/OPTIMIZATION_MODEL.md` in Stage 5.

---

## 9. Stage breakdown

| Stage | Deliverable | Exit check |
|---|---|---|
| 0 | This plan | Your approval |
| 1 Foundation | Vite+React+Tailwind shell with sidebar, Tauri window, FastAPI with `/api/health`, SQLite + Alembic, Rust backend launcher (dev mode), pytest + Vitest wired, docs skeleton | `npm run tauri dev` opens the app showing "Backend connected"; all tests pass |
| 2 Appliances | Household profile + appliance CRUD, validation, search/filter, UI | CRUD + validation tests |
| 3 Tariff & Energy | Tariff editor (flat/TOU/slab/charges), calculation engine, bill estimate, Overview + Energy Analysis charts, demo data | Hand-computed test cases for every tariff type |
| 4 Peak Load | Hourly demand model, limit violations, contributors, 24 h chart | Edge cases: midnight wrap, duty cycle, empty house |
| 5 Optimization | Substeps A–L as you specified | Constraint-by-constraint tests, infeasible cases, validator tests |
| 6 Simulation | Isolated scenarios, compare view | Test proves real tables unchanged |
| 7 Reports & Data | CSV + PDF (ReportLab, offline), backup/restore with validation, reset | Round-trip backup tests |
| 8 Polish | Empty/loading/error states, themes, accessibility, every button verified | Manual walkthrough checklist |
| 9 Release | PyInstaller + Tauri installer, offline test, persistence test | Installed app works with network disabled |

---

## 10. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Wrong Python version (3.15 alpha default) | Venv created explicitly with `py -3.13`; version checked at backend startup |
| Rust/MSVC install issues | Install first, verify with `cargo --version` and a hello-world build before Stage 1 code |
| Backend process left running / port collision | Random free port, Job Object kill-on-close, health check with timeout |
| PyInstaller missing OR-Tools/SQLAlchemy hidden files | Test the frozen exe early (end of Stage 1 smoke test, not only at Stage 9) |
| Antivirus flags the frozen exe | One-folder mode, no UPX compression |
| Slow first launch | One-folder mode; splash/loading state while health check runs |
| CP-SAT needs integers | Explicit scaling constants, documented and tested for rounding |
| Users misreading estimates as measured savings | "Estimated" labels everywhere, assumptions block in reports |
| Overnight windows | Cyclic day model, dedicated tests |
| Scope creep / giant components | Stage gates; feature folders; component size review each stage |
| Data loss | Auto-backup before migrations and restores; restore validates schema first |

---

## 11. Estimated timeline

Assuming ~15–20 hours/week, working together and including time for you to understand
each part:

| Stage | Estimate |
|---|---|
| Setup + 1 | 1 week |
| 2 | 1 week |
| 3 | 1.5–2 weeks |
| 4 | 0.5–1 week |
| 5 | 2–3 weeks (most important; don't rush) |
| 6 | 1 week |
| 7 | 1 week |
| 8 | 1 week |
| 9 | 1 week |
| **Total** | **~10–12 weeks** |

---

## 12. Decisions needed before Stage 1

1. Install **VS 2022 Build Tools (C++ workload)** and **Rust (rustup)** — you install, or approve me running the `winget` commands.
2. Use **Python 3.13** in a project venv (not your 3.15 alpha default).
3. Backend packaging: **PyInstaller one-folder + Rust launcher with Job Object** (recommended) vs Tauri sidecar one-file.
4. Add **React Router** and **TanStack Query** to the frontend stack.
5. Use **ReportLab** for offline PDF export (Stage 7).
6. Run `git init` locally (no remote) so every stage is a commit you can review and roll back.
7. Confirm the modeling choices: cyclic 24 h day, "current usual start time" per flexible appliance as the savings baseline, expected vs worst-case demand, two-stage objectives for cost/peak and normalized weighting for balanced.
