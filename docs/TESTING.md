# Testing

*Last updated: Stage 6. Totals: 282 backend, 91 frontend, 6 Rust.*

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

| `unit/test_tariff_rules.py` | Each type needs its own fields only; TOU gaps and overlaps reported with the time; overnight periods; weekday/weekend sets each cover the day; no mixing "every day" with weekday sets; slab limits increase and only the last is open |
| `unit/test_tariff_engine.py` | Hand-worked bills: flat + fixed + per-kWh + 5% duty = 1155.00; several percentages on the same subtotal; **percentages apply to the printed (rounded) subtotal**; total equals the sum of printed lines; slabs at 80/100/150/250/0 kWh in both slab modes; slab breakdown text; TOU step prices including weekday vs weekend |
| `unit/test_energy_model.py` | Weekday counting vs a day-by-day count (incl. leap year and year boundary); November 2026 = 62.7 kWh; daily TOU charge 18.96 / 6.96 by hand; moving the washer off-peak cuts its charge from 12.00 to 4.50; appliance breakdown; category filter; no tariff gives energy but no cost; slab average-rate allocation sums to the bill; range across two months; invalid ranges; hourly profile for a day and the weekly average; 12-month projection |
| `integration/test_tariffs_api.py` | First tariff becomes active; activation switches; exact decimals; update replaces children; deleting the active tariff; 404s; 8 invalid-tariff cases with field paths; TOU gap message |
| `integration/test_energy_api.py` | Report with and without a tariff; rounding; category filter; reversed/oversized/garbage date ranges give 422; hourly profile; monthly projection equals the bill; slab note; empty household |
| `unit/test_peak_load.py` | Worst case vs expected (duty cycle); a 15-minute spike is caught; several peak windows; violation window and culprits; exactly-at-limit is not a violation; no limit; high-demand threshold from limit or peak; heavy overlaps; "not together" conflicts; windows merged across midnight; window edge cases; operating days change each day's peak and the worst-day tie-break; empty household |
| `integration/test_peak_load_api.py` | Worst day chosen automatically with violation, headroom and contributors; requested weekday; running appliances per step; conflicts; no household limit; empty household; invalid weekday |
| `optimization/test_a_problem.py` | Candidate starts (grid, window fit, overnight, current start always kept); fixed appliances become base load; power rounds up and limit down; weekly cost per start from TOU prices (168 / 105 / 133 worked by hand); operating days; input validation messages |
| `optimization/test_b_to_f_constraints.py` | One boolean per candidate; exactly one start; out-of-window starts do not exist; contiguous runs wrap midnight; load limit separates appliances and includes fixed load; infeasibility caused by the limit (proved by relaxing it); not-simultaneous overlap rules per shared day |
| `optimization/test_g_h_objective_and_solver.py` | Cost goal picks the cheapest hours with least movement; peak used as tie-break; peak goal works under a flat tariff; preferred window never costs money; **solver equals brute-force optimum** for all goals and balance weights 0/25/75/100; goals trade off in the expected order; never worse than a valid current schedule; invalid current schedule repaired; INFEASIBLE returns no schedule; reproducible; status interpretation table incl. "never claim optimal" |
| `optimization/test_i_validation.py` | Valid schedule passes all 7 checks; missing/non-flexible appliances, off-grid times, wrong duration, out-of-window runs, load-limit violation, overlap and wrong reported numbers are each caught; solver output passes; **validator imports no OR-Tools/builder/runner** |
| `optimization/test_l_explain_and_diagnose.py` | Reasons from real before/after differences (prices, overlaps, demand, limit, preferred window, 12-hour times); no price reason under a flat tariff; costlier moves disclosed; no optimality claim without proof; diagnostics for fixed load over limit, appliance that cannot fit (with smallest workable limit), limit too low, not-simultaneous blocking |
| `integration/test_optimization_api.py` | End to end on sample data: cost goal valid and cheaper with 7 passed checks; peak goal never raises the peak; goal trade-off; runs stored and reproducible; household unchanged; infeasible household explained and stored; flat tariff gives 0 savings with a reason; 422 for unsolvable inputs; no tariff/household peak goal; request validation; finer grid at least as good; history survives deleting an appliance |
| `unit/test_scenario.py` | Changes never modify the original household (immutability); new appliances get negative ids; replace/remove target one appliance; tariff and limit changes; unknown or already-removed appliances reported by change index; inconsistent appliances reported with field paths; name clashes (any case, duplicates in one scenario, names freed by removal); change descriptions generated from the data |
| `integration/test_simulations_api.py` | **Isolation**: every real table row is identical before and after creating, running, editing and deleting a scenario that changes everything at once; scenario appliances never appear in the household. Baseline equals the normal bill, kWh and peak figures; adding an AC gives the hand-calculated +216 kWh and a higher bill; fewer washes saves energy and money; another tariff changes the bill not the energy (and scheduling saves 0 under a flat tariff); a limit too low for the scenario is INFEASIBLE with diagnostics while usual-times numbers remain; goal comparison on identical data (cost <= balanced <= peak); scheduling not attempted is explained; round trip, listing, results newest first, reproducibility; editing marks results out of date; delete cascades; 404s; 409 duplicate names; invalid changes rejected with field paths and not saved; 7 request-validation cases; a scenario that no longer fits the household is reported when run |
| `integration/test_demo_api.py` | Sample data loads and is labelled; produces a 4-line bill; refuses (409) when any real data exists or when loaded twice |

The fixtures in `tests/factories.py` are test data, not product data. Tariff rates
in tests are invented round numbers chosen to make hand arithmetic easy.

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

| `lib/dates.test.ts` | Local-date parsing, month/year ranges incl. leap years, labels |
| `features/tariffs/formModel.test.ts` | Flat/TOU/slab conversion, overnight periods, empty slab limit means "no limit", parse errors with backend field paths |
| `features/tariffs/TariffsPage.test.tsx` | "Never assumes rates" empty state; cards show rates in the household currency; create flat tariff with a charge; TOU payload and backend coverage error; switching the active tariff; warning before deleting the active tariff |
| `components/charts/chartTheme.test.ts` | Tidy axis maxima (3.76 → 4, 4.3 → 5, 0.16 → 0.2) |
| `features/peak-load/PeakLoadPage.test.tsx` | Opens on the worst day with headline figures; violation alert with times and culprits; peak contributors and conflicts; switching day sends the weekday and clears the alert; hourly data table; "set a load limit" prompt |
| `features/scheduler/SchedulerPage.test.tsx` | Empty state and defaults; run sends the chosen settings; verified optimal result with savings, schedule and checks; **time-limited result is never called optimal**; infeasible shows diagnostics and no schedule; **a schedule that fails validation is not presented**; negative savings shown honestly; 422 reason shown; latest run shown and older runs viewable |
| `features/simulation/SimulationPage.test.tsx` | Empty state states that real data is never changed; building a scenario from simple changes; **adding an appliance to a scenario through the nested form makes no write to the household**; pre-filled change from an existing appliance; backend errors shown next to the change; duplicate-name conflict; run shows signed differences (+/-) vs the current household; savings shown with a minus sign; infeasible scenario explained while usual-times numbers remain; "edited since last run"; side-by-side comparison and the unfair-comparison warning; editing pre-fills; delete needs confirmation; run failure explained |
| `features/energy/EnergyPage.test.tsx` | Headline tiles; data tables behind charts; itemised bill; calculation notes; filters sent to the API; "No tariff" state; range error shown on the date field |

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
