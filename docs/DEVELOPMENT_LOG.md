# Development Log

## Stage 0 — Audit and planning (2026-11-09) ✅ approved

- Audited the machine: Node 24, npm 11, Python 3.11/3.12/3.13/3.15a, Git, WebView2 present; Rust and MSVC Build Tools missing.
- Found that the default Python (3.15 alpha) has no OR-Tools wheel; verified that OR-Tools 9.15 has a Python 3.13 wheel. Decision: Python 3.13.
- Plan written to [STAGE0_PLAN.md](STAGE0_PLAN.md). All seven decisions approved:
  Build Tools + Rust install, Python 3.13 venv, PyInstaller one-folder + Rust launcher with Job Object,
  React Router + TanStack Query, ReportLab for PDF, local git, and the modeling choices.

## Stage 1 — Project foundation (2026-11-09) ✅ complete, awaiting approval

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
