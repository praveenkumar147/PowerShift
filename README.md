# PowerShift — Intelligent Household Energy Optimization System

An offline-first Windows desktop app for estimating household electricity use and
cost, analysing peak demand, and generating optimized appliance schedules with
Google OR-Tools (CP-SAT).

> **Status: Stage 3 complete.** Household profile, appliance management, configurable
> tariffs (flat, time-of-use, slab, extra charges and taxes), itemised monthly bill
> estimates and energy analysis charts work. Peak load analysis comes next in Stage 4.
> See [docs/DEVELOPMENT_LOG.md](docs/DEVELOPMENT_LOG.md).

All data stays on your computer. There are no accounts, cloud services or external APIs.

## Technology

| Layer | Technology |
|---|---|
| UI | React 19, TypeScript (strict), Vite, Tailwind CSS 4, React Router, TanStack Query, Recharts, Lucide icons |
| Desktop shell | Tauri 2 (Rust) |
| Backend | Python 3.13, FastAPI, Pydantic, SQLAlchemy 2, Alembic |
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
- [Optimization model](docs/OPTIMIZATION_MODEL.md)
- [Testing](docs/TESTING.md)
- [User guide](docs/USER_GUIDE.md)
- [Development log](docs/DEVELOPMENT_LOG.md)
- [Stage 0 plan](docs/STAGE0_PLAN.md)

## Known limitations

- Packaging as a Windows installer is not set up yet (Stage 9).
- The frontend bundle is about 810 kB (241 kB gzipped), mostly the chart library; code splitting is planned for Stage 8.
- Holidays and seasonal changes are not modelled: every Monday follows the same routine.
- All energy figures will be estimates from user-entered data, not measurements.
