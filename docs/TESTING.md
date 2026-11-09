# Testing

*Last updated: Stage 1.*

## How to run

| Suite | Command | Location |
|---|---|---|
| Backend (pytest) | `cd backend && .venv/Scripts/python -m pytest` | `backend/tests/` |
| Backend lint / types | `.venv/Scripts/ruff check powershift tests` and `.venv/Scripts/mypy powershift` (from `backend/`) | |
| Frontend (Vitest) | `npm test` | `src/**/*.test.ts(x)` |
| Frontend types / lint | `npm run typecheck` and `npm run lint` | |
| Desktop shell (Rust) | `cd src-tauri && cargo test` | `src-tauri/src/backend.rs` (`mod tests`) |

## What is covered

### Backend

| Test file | Verifies |
|---|---|
| `unit/test_config.py` | Argument parsing, defaults (port 0, no token), invalid port rejected |
| `integration/test_migrations.py` | Fresh DB gets all tables; re-running migrations is a no-op with no backup; an existing DB is backed up before migrating; foreign keys and WAL are on; CHECK constraints reject impossible data |
| `integration/test_health_api.py` | Health response; missing/wrong token → 401; unknown route → JSON error without internals; CORS allows the Tauri origin and blocks others; `/docs` disabled with a token |
| `integration/test_startup.py` | Starts the real backend process exactly as the desktop shell does, reads the READY line, calls `/api/health` over real HTTP, checks the DB and log files exist |

### Frontend

| Test file | Verifies |
|---|---|
| `api/client.test.ts` | Token header sent (or omitted in browser mode), JSON body, backend errors become `ApiError` with field details, unreachable backend reported clearly |
| `api/BackendProvider.test.tsx` | Startup screen shown until ready; failure message shown; **Try again** reconnects |
| `app/AppShell.test.tsx` | Sidebar lists all nine sections; Overview shows real health data; error state with working **Check again**; navigation marks the active link |
| `app/theme/ThemeSwitcher.test.tsx` | Default "System"; Dark applies the `.dark` class and is remembered; stored choice restored |

### Desktop shell (Rust)

READY-line parsing (valid, invalid, out-of-range ports); token length and randomness;
READY line found after other output; process exiting before ready is reported;
status JSON shape matches the TypeScript type.

## Known warnings

- pytest prints a `StarletteDeprecationWarning` recommending `httpx2` for the test
  client. We stay on the widely used `httpx` until `httpx2` has been evaluated; the
  warning doesn't affect results.
- `npm audit` reports moderate issues in `minimatch`, used only by ESLint (development
  tooling). The app's shipped dependencies report 0 vulnerabilities (`npm audit --omit=dev`).
