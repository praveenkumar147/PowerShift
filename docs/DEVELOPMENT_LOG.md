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

## Stage 2 — Household profile and appliance management (2026-11-09) ✅ complete, awaiting approval

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
