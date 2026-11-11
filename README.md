# PowerShift — Intelligent Household Energy Optimization System

An offline-first Windows desktop app for estimating household electricity use and
cost, analysing peak demand, and generating optimized appliance schedules with
Google OR-Tools (CP-SAT).

> **Status: Stage 9 in progress: the app runs in packaged form, the installer is not built yet.** Household profile, appliance management, configurable
> tariffs, bill estimates, energy analysis, peak load analysis, the **CP-SAT Smart
> Scheduler**, the **Simulation Lab**, **PDF/CSV reports** and **data management**
> (backups, validated restore, export, reset) work, and the Overview now summarises the scheduler, the
> Simulation Lab and your backups. The frozen backend and the release app were verified end to end
> (see [Packaging](#packaging-windows)); producing the `.exe` installer is blocked on one build tool (see Known limitations).
> See [docs/DEVELOPMENT_LOG.md](docs/DEVELOPMENT_LOG.md).

All data stays on your computer. There are no accounts, cloud services or external APIs.

## Technology

| Layer | Technology |
|---|---|
| UI | React 19, TypeScript (strict), Vite, Tailwind CSS 4, React Router, TanStack Query, Recharts, Lucide icons |
| Desktop shell | Tauri 2 (Rust) |
| Backend | Python 3.13, FastAPI, Pydantic, SQLAlchemy 2, Alembic, Google OR-Tools (CP-SAT) |
| Database | SQLite (one local file) |
| Tests | pytest, Vitest, React Testing Library, cargo test |

## Prerequisites (Windows)

- Node.js 20+ and npm
- Python **3.13** (the `py` launcher must list it: `py -0p`)
- Rust (stable, MSVC toolchain) via rustup
- Visual Studio 2022 Build Tools, "Desktop development with C++" workload
- WebView2 runtime (preinstalled on Windows 11)

## Setup

```bash
npm install
```

```bash
py -3.13 -m venv backend/.venv
```

```bash
backend/.venv/Scripts/python -m pip install -e "backend[dev]"
```

## Run the desktop app (development)

```bash
npm run tauri dev
```

This starts Vite, compiles the Rust shell, and the shell starts the Python backend
automatically. Development data is stored in `backend/.data/`.

### Browser-only frontend work (optional)

Start the backend by hand on a fixed port without a token, then run Vite:

```bash
backend/.venv/Scripts/python -m powershift --port 8000
```

```bash
npm run dev
```

Open http://localhost:1420. API docs are at http://127.0.0.1:8000/docs in this mode only.

## Tests and checks

```bash
npm test
```

```bash
npm run typecheck
```

```bash
npm run lint
```

```bash
cd backend && .venv/Scripts/python -m pytest
```

```bash
cd src-tauri && cargo test
```

See [docs/TESTING.md](docs/TESTING.md).

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Database design](docs/DATABASE_DESIGN.md)
- [API](docs/API_DOCUMENTATION.md)
- [Optimization model](docs/OPTIMIZATION_MODEL.md) (math, constraints, objective, statuses)
- [Testing](docs/TESTING.md)
- [User guide](docs/USER_GUIDE.md)
- [Development log](docs/DEVELOPMENT_LOG.md)
- [Stage 0 plan](docs/STAGE0_PLAN.md)

## Packaging (Windows)

```bash
npm run build:backend
```

Freezes the Python backend (with OR-Tools, ReportLab and the migrations) into `backend/dist/powershift-backend/` (about 190 MB) using PyInstaller.

```bash
npm run package
```

Runs the step above, then `tauri build`, which compiles the release app and creates an NSIS installer (`src-tauri/target/release/bundle/nsis/`). Tauri downloads the NSIS tools the first time; see Known limitations if that download fails.

## Known limitations

- **The installer (`.exe`) has not been produced.** `tauri build` compiles the release app and the frozen backend works, but the NSIS packaging step could not download its tools (`timeout: global`) on the machine used for development. Everything up to that step was verified (see the development log).
- Exports are saved through the WebView2 download mechanism straight to your Downloads folder (verified in the real window for PDF, backup and JSON). There is no "Save as" dialog; a repeated name gets "(1)" added.
- PDF layout was checked by tests (text, structure, fonts), not by looking at the pages.
- Backups are never deleted automatically; remove old ones from the backups folder yourself.
- The first screen downloads about 372 kB (117 kB gzipped). The chart library (353 kB, 103 kB gzipped) loads only with pages that draw charts, including the Overview.
- Holidays and seasonal changes are not modelled: every Monday follows the same routine.
- All energy figures will be estimates from user-entered data, not measurements.
