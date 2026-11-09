# Architecture

*Describes what is implemented. Last updated: Stage 1.*

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
| `api/` | HTTP routes, dependencies, token middleware | services, schemas, core |
| `schemas/` | Pydantic request/response models | — |
| `services/` | Use cases and transactions *(from Stage 2)* | domain, calculation, optimization, db |
| `domain/`, `calculation/`, `optimization/` | Pure logic *(from Stages 3–5)* | each other only — never `db/` or `api/` |
| `db/` | ORM models, sessions, migrations | core |
| `core/` | Config, errors, logging | — |

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
