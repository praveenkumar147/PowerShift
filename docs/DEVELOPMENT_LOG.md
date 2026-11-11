# Development Log

## Stage 0 — Audit and planning (2026-11-09) ✅ approved

- Audited the machine: Node 24, npm 11, Python 3.11/3.12/3.13/3.15a, Git, WebView2 present; Rust and MSVC Build Tools missing.
- Found that the default Python (3.15 alpha) has no OR-Tools wheel; verified that OR-Tools 9.15 has a Python 3.13 wheel. Decision: Python 3.13.
- Plan written to [STAGE0_PLAN.md](STAGE0_PLAN.md). All seven decisions approved:
  Build Tools + Rust install, Python 3.13 venv, PyInstaller one-folder + Rust launcher with Job Object,
  React Router + TanStack Query, ReportLab for PDF, local git, and the modeling choices.

## Stage 1 — Project foundation (2026-11-09) ✅ approved

### Installed
- Visual Studio 2022 Build Tools (C++ workload) and Rust 1.99.1 (stable MSVC) via winget.
- Backend venv (Python 3.13.12): FastAPI 0.162, Uvicorn 0.54, Pydantic 2.14, SQLAlchemy 2.1, Alembic 1.20; dev: pytest, httpx, ruff, mypy.
- Frontend: React 19, React Router 8, TanStack Query 5, Lucide, Tauri API 2; dev: Vite 8, TypeScript 6, Tailwind 4, Vitest 5, Testing Library, ESLint 10.
- Tauri 2.12 (Rust), win32job, getrandom.

### Built
- **Backend**: config from CLI args; JSON error format; rotating file log; SQLAlchemy engine with foreign keys + WAL; `household` and `app_settings` models; Alembic migration `0001`; automatic migration at startup with a pre-migration backup; token middleware; CORS; `GET /api/health`; READY-line startup protocol with an OS-assigned port.
- **Frontend**: app shell with sidebar (9 sections), light/dark/system theme, startup screen with error and retry, typed API client, health query, Overview with a real "Local engine" status card, honest "Not built yet" pages.
- **Desktop shell**: `backend.rs` starts the backend, parses the READY line, generates a 256-bit token, uses a Job Object, stops the backend on exit, and exposes `backend_status`.
- **Docs**: README, ARCHITECTURE, DATABASE_DESIGN, API_DOCUMENTATION, TESTING, USER_GUIDE, OPTIMIZATION_MODEL (placeholder: not implemented).

### Verified
- 16 backend tests, 14 frontend tests, 6 Rust tests pass; ruff, mypy (strict), tsc (strict), ESLint and clippy are clean.
- `npm run tauri dev`: window opens; the backend is ready in about 3 s; the database is created and migrated; the UI shows live health data.
- Request without the token → 401.
- Hard-killing the app (simulated crash) left no backend processes, thanks to the Job Object.
- Normal close → "Stopping backend", exit code 0, no leftover processes.
- Second launch on an existing database → no migration, no unnecessary backup.
- Production frontend build (`npm run build`) succeeds.

### Problems met and fixed
- Alembic could not read a percent-encoded SQLite URL (`C%3A`) because its config parser treats `%` specially. Fix: give Alembic an open connection instead of a URL.
- Found that a venv `python.exe` on Windows is a launcher that starts the real interpreter as a child process. Killing only the launcher would orphan the server. The Job Object kills the whole process tree; verified.
- Alembic logged two INFO lines on every health check; quietened that logger (our own module logs the real migrations).

### Not done / deferred
- The production launch path (frozen backend exe) is written but untested until Stage 9.
- Theme preference is stored in localStorage for now; it moves to `app_settings` in the Settings stage.
- `httpx2` (suggested by a Starlette deprecation warning) was not adopted; it needs evaluation first.

## Stage 2 — Household profile and appliance management (2026-11-09) ✅ approved

### Design decisions
- **Times as minutes since midnight** in 15-minute steps; an end ≤ start wraps past midnight. Converts directly to hourly or 15-minute scheduling slots later.
- **Fixed vs flexible** stored relationally: fixed appliances have on-periods (`appliance_usage_blocks`); flexible ones have one constraint row (`appliance_flex_constraints`) with run duration, allowed window, **usual start time** (the future savings baseline), an optional preferred window, and contiguity.
- **Rated vs actual**: max power = rated × quantity (for load limits); average power = max × duty cycle (for energy). Estimates are computed server-side in `calculation/appliance_energy.py` and returned with each appliance.
- **Four validation layers**: frontend parse checks → Pydantic field checks → domain cross-field rules → database CHECK constraints. Every error is keyed by API field path.
- **Warnings vs errors**: an appliance that alone exceeds the household load limit is a *warning* (saved, flagged), because the limit can change later; the scheduler will treat it as infeasible in Stage 5.
- Household profile lives on the Settings page (the sidebar has no separate Household section); the Overview guides first-time setup there.

### Built
- Backend: `domain/` (time windows, appliance rules), `calculation/appliance_energy.py`, repositories, services, `/api/household` and `/api/appliances` (CRUD, search, filters), migration `0002`.
- Frontend: reusable `Field`, inputs, `SegmentedControl` (theme switcher refactored onto it), accessible `Modal` (focus trap, Escape, focus return), `ConfirmDialog`, `Badge`; Settings page with household form; Appliances page with filters, table, add/edit dialog and delete confirmation; Overview household summary.

### Verified
- 78 backend tests, 39 frontend tests, 6 Rust tests pass; ruff, mypy (strict), tsc (strict), ESLint clean; production build succeeds.
- Live in the browser against the real backend: the existing dev database was backed up and migrated `0001 → 0002`; household saved; a washer with a 3-hour run in a 2-hour window was rejected with the exact backend message under Run duration; a valid overnight washer saved; the water heater load-limit warning displayed; edit dialog pre-filled in dark mode; layout checked at the 1024-pixel minimum window width.

### Problems met and fixed
- Alembic autogenerate silently skipped the expression index `lower(name)` on SQLite; added by hand to migration `0002`.
- Pydantic checked the currency pattern before uppercasing, so `"usd"` was rejected; moved normalisation to a "before" validator.
- The modal focused the close (×) button instead of the element marked `data-autofocus`, because `querySelector("a, b")` returns the first match in the page, not the first selector. Caught by the delete-confirmation test.
- Errors below the fold weren't visible after submit; the form now scrolls to the first problem. The duration dropdowns now carry `aria-invalid`.
- Form grids wrapped badly at narrow widths; two columns now start at the `md` breakpoint. Filter selects stretched full-width; fixed with an explicit grid.

### Not done / deferred
- `app_settings` (theme, default optimization goal) is not exposed through the API yet; the theme stays in localStorage until the Settings stage.
- Priority, preferred window, contiguity and "allow simultaneous" are stored and validated, but only take effect when the scheduler is built (Stage 5).
- The dev database at `backend/.data/` now contains sample entries made during browser testing ("Demo home", Refrigerator, Washing machine, Water heater).

## Stage 3 — Tariff and energy engine (2026-11-09) ✅ approved

### Design decisions
- **Typical-week model**: each appliance gets 96 fifteen-minute average-kW values per weekday. Any period = number of each weekday in it x that weekday's values. Fast and exact for a repeating routine.
- **Tariff structures**: flat, time-of-use (every day, or weekday + weekend sets, each covering 24 h exactly once), slab (telescopic or whole-usage), plus fixed-monthly, per-kWh and percentage charges. Nothing is hard-coded; the only built-in rates are in clearly labelled sample data.
- **Money as `Decimal`** end to end; stored as `NUMERIC(14,4)`.
- **Bill rounding**: each printed line rounded to 2 decimals; percentages apply to the sum of printed lines, so the bill can be re-checked with a calculator.
- **Slab tariffs** price the monthly household total; per-day and per-appliance costs use the month's average rate, and the report says so.
- **One active tariff**, enforced by a partial unique index; the first tariff created becomes active.
- **Charts**: Recharts with two validated series colours (colour-blind separation and contrast checked by script in both themes), one measure per chart (no dual axes), horizontal bars for breakdowns, a data table behind every chart.

### Deviations from the Stage 0 plan
- Deleting the active tariff is allowed (plan said 409), because a 409 would make a household's only tariff impossible to delete; costs simply show as unavailable.
- `/api/energy/summary` and `/api/energy/appliance-breakdown` became one `/api/energy/report`, so totals and breakdowns always come from the same calculation; `/monthly` and `/bill` were added.
- Calculation snapshots (saved history of estimates) are deferred to the Reports stage.

### Built
- Backend: `domain/tariff.py`, `calculation/{load_profile,tariff_engine,energy_model}.py`, tariff repository/service/API, energy service/API, sample-data service/API, migration `0003`.
- Frontend: Electricity Tariff page (cards, editor with flat/TOU/slab/charges, activate, delete), Energy Analysis page (filters, headline tiles, daily chart, appliance and category breakdowns, hourly profile, monthly projection, itemised bill, assumptions), Overview dashboard (month tiles, hourly profile) and "Load sample data".

### Verified
- 148 backend, 60 frontend and 6 Rust tests pass; ruff, mypy (strict), tsc (strict) and ESLint are clean; production build succeeds.
- Live against a fresh database: sample data loaded; Overview showed 511.35 kWh and a Rs 3,317.48 bill for November; the hourly chart's 07:00 spike is the 3 kW water heater; appliance totals matched hand calculations (air conditioner 0.9 kW x 7 h x 30 = 189 kWh); the bill re-adds by hand.

### Problems met and fixed
- **Bill not checkable by hand**: a 5% duty was computed on the unrounded subtotal (157.97 instead of 5% of the printed 3,159.50 = 157.98). Changed to round lines first; added a regression test.
- The "kWh" unit was repeated on every y-axis tick and wrapped; now stated once above each chart.
- Breakdown bar labels wrapped in the narrow category card; gave labels more room.
- During the live check, navigating within the single-page app kept cached data; a real reload confirmed the fix (not a code issue).

### Not done / deferred
- Bundle size warning (810 kB, 241 kB gzipped), mostly Recharts; code splitting in Stage 8.
- Holidays, seasons and real meter data are not modelled.
- The main dev database (`backend/.data/`) still has the Stage 2 test entries and no tariff; the sample-data check used a separate test database that was deleted afterwards.

## Stage 4 — Peak load analyzer (2026-11-09) ✅ approved

### Design decisions
- **kW only.** Peak analysis never mixes in kWh. Two figures per step: **worst case** (all running appliances at full rated power; drives limit warnings) and **expected** (duty-cycle average).
- **15-minute resolution**, not hourly, so a short spike (a 15-minute kettle on top of a washer) is not averaged away. The data table still offers an hourly view (highest step per hour).
- **Windows wrap midnight** (22:30-02:00 is one period, not two).
- **Thresholds are named constants**: high demand = 80% of the limit (or of the day's peak); heavy appliance = 1 kW. Both are stated in the page notes.
- **Conflicts** (appliances marked "not simultaneous" that overlap at their usual start times) are reported now; the scheduler resolves them in Stage 5.
- No database changes: peak analysis is derived from appliances and the household limit.

### Built
- Backend: `calculation/peak_load.py`, `services/peak_load_service.py`, `GET /api/peak-load/analysis`.
- Frontend: Peak Load page (day picker, headline tiles, violation alert, 15-minute step chart with limit line, peak contributors, clickable peak-by-day chart, high-demand/overlap/conflict lists, notes); shared `NotesBox`; `niceCeiling` for readable chart axes. Saving the household now refreshes all energy and peak figures.

### Verified
- 168 backend, 67 frontend and 6 Rust tests pass; ruff, mypy (strict), tsc (strict), ESLint clean; build succeeds.
- Live on sample data: peak 3.76 kW at 22:00-22:30 = dishwasher 1.8 + AC 1.5 + fans 0.225 + fridge 0.15 + lights 0.072 + router 0.012 (checked by hand). The expected peak (3.07 kW) falls at 07:00, a different time. Lowering the limit to 3 kW in Settings immediately showed two violations (07:00-08:00 at 3.16 kW, 22:00-22:30 at 3.76 kW) and 90 minutes over. Clicking a bar switched the analysed day.

### Problems met and fixed
- The limit reference line stretched the y-axis to awkward ticks (0.95, 1.9, 2.85); axes now end on tidy values (1, 2, 5 x 10^n steps).
- Accessibility: inline contribution bars got `role="img"` so their share is announced.

### Not done / deferred
- The Overview does not yet surface peak warnings; dashboard integration is Stage 8.

## Stage 5 — Optimization engine (2026-11-10 to 2026-11-11) ✅ complete, awaiting approval

Substeps A-L, each tested before the next.

### Design decisions
- **One start time per flexible appliance**, used on every operating day. Keeps the model small and the advice usable ("run the washer at 16:00"). Per-day schedules are a possible extension.
- **Candidate starts on a grid** (60/30/15 min) whose whole run fits the window, **plus the usual start**, so a valid current schedule is always available as a fallback and the solver can never return something worse.
- **Integer scaling**: watts (appliance power rounded up, limit rounded down) and money in 1/10 000. Rounding goes in the safe direction for the limit.
- **Multi-stage (lexicographic) objectives** with locking constraints, instead of one weighted sum, so goals have a clear priority and no arbitrary magic weights; the *balanced* goal uses a normalised blend (each term divided by its current-schedule value) so money and kilowatts are never added directly.
- **Movement is the last tie-break**, giving a unique answer and the least change to habits.
- **Honest statuses**: OPTIMAL only if every stage is OPTIMAL; otherwise FEASIBLE.
- **Independent validation** in a module that imports nothing from the solver side; a test enforces this. A schedule failing validation is not displayed.
- **Explanations from measured differences** (prices, overlaps, demand, limit), never templates applied blindly.
- **History stores JSON snapshots** (inputs and full result) plus items with `ON DELETE SET NULL`, so old runs stay reproducible and readable.

### Built
- `optimization/`: `problem.py`, `builder.py`, `runner.py`, `metrics.py`, `validation.py`, `diagnose.py`, `explain.py`.
- Migration `0004`; `POST /api/optimization/run`, `GET /history`, `GET /{id}`.
- Smart Scheduler page: goal, balance slider, start step, time limit, verdict banner, before/after tiles and load profiles, schedule table with reasons, validation checklist, solver details, history.

### Verified
- 245 backend tests (incl. brute-force optimum comparison), 76 frontend tests.
- Live on sample data (lowest cost, 54 ms, OPTIMAL, 7/7 checks): November bill 3,317.48 to 2,920.42 (saving 397.06, re-derived by hand); dishwasher 20:30 to 23:00-01:00 (7.50 to 4.50 per kWh), washer 19:00 to 16:00 (8.50 to 6.00), water heater 07:00 to 05:00 (6.00 to 4.50); peak 3.76 to 3.69 kW; before/after charts share one scale and match the table.

### Problems met and fixed
- A test assumed the sample household's current schedule was valid; it overlaps two "not together" appliances. Replaced with one valid household plus a separate test that an invalid current schedule is repaired.
- A validator test expected the wrong overlap minutes (210/week = 30 min x 7 days).
- mypy: OR-Tools `clear_hints` is untyped; a status variable changed type. Used a distinct name for the combined status.
- Package metadata used for the solver version, because `ortools.__version__` is not exposed.

### Not done / deferred
- No button to apply a schedule to the appliances (outside agreed scope; the app recommends only).
- Overview does not yet show scheduler results (Stage 8 dashboard integration).
- Per-day start times and per-appliance weights are possible extensions.
