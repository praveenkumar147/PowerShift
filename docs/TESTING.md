# Testing

*Last updated: Stage 2. Totals: 78 backend, 39 frontend, 6 Rust.*

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
| `unit/test_time_window.py` | Window lengths (normal, overnight, whole day); a run fits or not; nested windows; 15-minute steps wrap midnight; overlap detection |
| `unit/test_appliance_rules.py` | Valid fixed/flexible specs pass; missing or overlapping periods; mode mismatches; run longer than window; usual start that can't finish; overnight runs accepted; preferred window inside the window and long enough |
| `unit/test_appliance_energy.py` | Hand-calculated examples: fridge with 40% duty cycle (1.44 kWh/day), quantity × power, several periods including overnight, flexible run × operating days, max power ignores duty cycle |
| `integration/test_household_api.py` | `null` before setup; save and read; second save updates the same row; trimming and uppercasing; each invalid field reported |
| `integration/test_appliances_api.py` | Full CRUD; flexible settings round-trip; sorting, search, filters, wildcard escaping; update replaces child rows; switching modes removes flexible settings; delete cascades; duplicate names (any case) → 409; 13 field-validation cases; cross-field errors by field path; invalid input never saved; load-limit warning |

The fixtures in `tests/factories.py` are test data, not product data.

### Frontend

| Test file | Verifies |
|---|---|
| `api/client.test.ts` | Token header sent (or omitted in browser mode), JSON body, backend errors become `ApiError` with field details, unreachable backend reported clearly |
| `api/BackendProvider.test.tsx` | Startup screen shown until ready; failure message shown; **Try again** reconnects |
| `app/AppShell.test.tsx` | Sidebar lists all nine sections; Overview shows real health data; error state with working **Check again**; navigation marks the active link |
| `app/theme/ThemeSwitcher.test.tsx` | Default "System"; Dark applies the `.dark` class and is remembered; stored choice restored |
| `lib/time.test.ts` | 12h/24h formatting, midnight wrap, durations, "00:00" as end-of-day, malformed input |
| `features/appliances/formModel.test.ts` | Form ↔ API conversion (duty % → fraction, overnight windows, durations); mode switching drops the other mode's data; parse errors use backend field paths; preferred times only required when switched on |
| `features/appliances/AppliancesPage.test.tsx` | Empty state; list shows usage, days, estimates and warnings; create fixed and flexible (overnight) appliances; client-side checks block bad submissions; backend rule errors shown next to the field; 409 conflict; edit pre-fills and sends PUT; delete needs confirmation and focuses Cancel; Escape closes; search/filter/clear |
| `features/household/HouseholdForm.test.tsx` | Create from empty form; pre-fill and show per-field server errors; required fields checked before sending |

UI tests run against `src/test/fakeBackend.ts`, a small in-memory stand-in for the API,
so they test the UI's behaviour without depending on the order of requests.

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
