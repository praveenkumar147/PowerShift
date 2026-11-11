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
- Bundle size warning (810 kB, 241 kB gzipped), mostly Recharts; fixed in Stage 8 (see below).
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

## Stage 5 — Optimization engine (2026-11-10 to 2026-11-11) ✅ approved

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

## Stage 6 — Simulation Lab (2026-11-11) ✅ complete, awaiting approval

### Design decisions
- **Scenarios store changes, not copies.** A scenario is a list of what-if edits applied to in-memory copies at run time. Isolation is structural: the scenario and pipeline modules import nothing from `db/`, domain specs are immutable, new appliances get negative ids, and only the two simulation tables are written.
- **Five change types**: add, replace (a full replacement, so hours, days, windows, power and quantity are all covered), remove, use another saved tariff, set the load limit. A scenario with no changes compares scheduling goals.
- **Three numbers side by side**: the actual household (baseline), the scenario at usual times, and the scenario after CP-SAT scheduling, so "the change costs X" and "scheduling recovers Y" are never confused.
- **Honest degraded results**: when scheduling cannot run (no flexible appliances, cost goal without a tariff) or has no valid schedule, the usual-times comparison is still returned, with the reason.
- **Results can go stale**: scenarios follow the real household. Results store the baseline used, and the UI warns when a comparison mixes baselines or when a scenario was edited after its last run.
- **Pipeline extracted from the Stage 5 service** (no behaviour change; all Stage 5 tests passed unchanged) so both features share the solver, validation and explanations.

### Deviations from the Stage 0 plan
- No separate `POST /api/simulations/compare`: the list endpoint returns each scenario with its latest result.
- No snapshot of the base household inside the scenario (the plan's `base_snapshot_json`); see above. Results record their baseline instead.

### Built
- Backend: `simulation/scenario.py`, `simulation/describe.py`, `optimization/pipeline.py`, migration `0005`, scenario CRUD, run and results endpoints.
- Frontend: Simulation Lab page (scenario cards, run, details, comparison chart and table), scenario editor with a change builder; the appliance form can return values instead of saving; shared schedule table and validation card.

### Verified
- 282 backend, 91 frontend and 6 Rust tests pass; ruff, mypy (strict), tsc (strict), ESLint clean; build succeeds.
- Live on sample data: three scenarios run through the real solver. Bedroom AC: +216 kWh (1.5 kW x 0.6 x 8 h x 30 days) and +1,088.64 bill (216 x 4.50 + 0.30 per kWh, then 5% duty), with the dishwasher moved to 05:00-07:00 because the AC would otherwise push the household to 5.26 kW over the 5 kW limit. Wash less: -12 kWh and -110.88 (12 kWh at the 8.50 peak rate with surcharge and duty). The real appliance and tariff lists were unchanged.

### Problems met and fixed
- A name-uniqueness check based on object identity missed duplicates when the same object was added twice; replaced with "count the names in the final scenario household".
- `POST` returned timestamps with a `Z` while `GET` returned them without (SQLite drops time zones); the read models now always emit UTC. The stale-result comparison hit the same naive/aware mix and now normalises both.
- A method named `list` shadowed the built-in inside its class for type annotations; renamed.
- An unused import of a module that did not exist slipped into a first draft of `pipeline.py`; caught by the first import and rewritten.

### Not done / deferred
- The Overview does not show scenario results (Stage 8).
- Scenario results are for the current calendar month only.
- Scenarios cannot yet be duplicated with one click.

## Stage 7 — Reports and data management (2026-11-11) ✅ complete, awaiting approval

### Design decisions
- **A report is data first, file second.** Builders produce one format-neutral `Report`; CSV and PDF are renderers. This keeps the numbers identical in both files and identical to the screens (builders reuse the existing services).
- **CSV is safe for Excel**: UTF-8 BOM, and any cell starting with `= + - @`, tab or return gets a leading apostrophe so imported text cannot run as a formula.
- **Backups are validated before they are trusted.** Size, SQLite header, integrity check, required tables, a single known migration revision, foreign-key check. Newer revisions are refused; older ones are upgraded after restore.
- **Every destructive step makes a safety copy first** (`pre-restore`, `pre-reset`), and the UI tells you its name so the action can be undone.
- **Check, then confirm.** Restore shows the backup's contents after validation and only then offers "Replace my data". Reset needs the exact word `RESET`.
- **Raw-body upload** (no multipart library) keeps the dependency list small.
- **Commit before respond.** Found while testing: FastAPI ran the session's commit after the response had gone out. The session dependency is now `scope="function"`, and a test watches the database at the moment the response starts.

### Deviations from the Stage 0 plan
- No `PUT /api/settings` for preferences/theme: the theme stays in local storage and moves to the database in Stage 8.
- Restore takes a stored backup or a raw uploaded file rather than a server-side file path, so the server never opens arbitrary paths.
- Files reach the user through the browser download mechanism (no native save dialog yet).

### Built
- Backend: `reports/` (model, CSV, PDF), `services/report_service.py`, `api/reports.py`, `db/backup.py`, `services/data_service.py`, `api/settings.py`, `schemas/data.py`; `OperationFailedError` (500) and `PayloadTooLargeError` (413); CORS exposes `Content-Disposition`.
- Frontend: Reports page (seven reports, options per report, PDF/CSV), Settings gained Backups, Data and About cards and a restore dialog; `download()`/`upload()` in the API client; the placeholder "pending" page was removed because every section now exists.

### Verified
- 391 backend, 120 frontend and 6 Rust tests pass; ruff, mypy (strict), tsc (strict) and ESLint are clean; production build succeeds.
- Live against the real backend with sample data: PDF and CSV exports return real bytes and the browser can read the server's filename; a backup was created; **restore through the UI** after deleting an appliance validated first (data unchanged while checking), then restored all 9 appliances and created a safety copy; **reset through the UI** with `RESET` removed 1 household, 9 appliances, 1 tariff, 1 scenario and 1 run and saved `pre-reset-...`; the raw-upload check accepted that backup and rejected a non-database file (422); the upload restore brought back 9 appliances; `/api/health` stayed `ok`.

### Problems met and fixed
- Existing `backup_database` left SQLite connections open (Windows file locks) and produced WAL-mode backups that were not self-contained; now closes connections, uses `journal_mode=DELETE` and unique names.
- Writes were committed after the response (see above).
- A router module named `settings` shadowed the `settings` argument of `create_app`; imported under another name.
- mypy: ReportLab has no type stubs (override added); `rowcount` needed a cast.
- A first PDF table helper was lost by the formatter; found by failing tests.
- Rewriting four source files with PowerShell re-encoded their non-ASCII characters; found by two failing tests and repaired.

### Not done / deferred, and honest caveats
- **PDF layout was not looked at.** Tests prove the PDF is valid and its text is extractable; I could not render pages here.
- **Downloads inside the packaged Tauri window (WebView2) are unverified.** They work in a browser; confirm in Stage 8/9, and switch to a native save dialog if needed.
- Old backups are never pruned.
- The Overview does not yet show scheduler/simulation/report information (Stage 8).
- OPTIMIZATION_MODEL.md is unchanged: Stage 7 does not touch the model.

## Stage 8 — Integration and polish (2026-11-11) ✅ complete, awaiting approval

### Design decisions
- **The database owns the theme; local storage is a start-up cache.** The first paint must not flash the wrong colours, and the backend is not available yet at that moment, so the stored value is applied first and the database value replaces it as soon as it answers.
- **No new "dashboard" page.** The Overview gained three summary cards built on the existing queries, so it cannot disagree with the pages it links to. Wording follows what was proven: a bill change is shown only for a valid schedule, "proven optimal" only for `OPTIMAL`.
- **Split by page, not by hand-picked library.** `React.lazy` per page lets the bundler place shared code and the chart library by itself.
- **A failed request is a state of its own.** Where a page used `data ?? []`, "failed to load" was indistinguishable from "none yet".
- **Test accessibility with a tool, not by eye.** `axe-core` (a development dependency only) runs over every page and two dialogs, with a negative control proving it can fail.

### Deviations from the Stage 0 plan
- `PUT /api/settings` is `PUT /api/settings/preferences` and carries only the theme. The table also has `default_optimization_priority`, but nothing in the UI uses it, so it is not exposed (no feature was added without a use).
- The dashboard is the existing Overview rather than a new screen.

### Built
- Backend: `services/preferences_service.py`, `GET/PUT /api/settings/preferences`, `Preferences` schemas.
- Frontend: `ThemeSync`, `ActivityCards` (Scheduler, Simulation, Your data), lazy routes and `preloadPages`, skip link, title and focus handling, labelled card regions, reduced-motion CSS, dark-mode danger button colour, loading and error states for the month tiles and the Reports page.

### Verified
- 395 backend, 145 frontend and 6 Rust tests pass; ruff, mypy (strict), tsc (strict) and ESLint are clean; build succeeds.
- Bundle: the first screen went from 810 kB (241 kB gzipped) to 372 kB (117 kB gzipped); the 353 kB chart library is a separate chunk.
- Live, real backend with sample data: the theme chosen in the UI was stored in the database and **restored after the browser's local storage was cleared**; the Overview cards matched the API (a cost-goal run: -400.47 per month, matching the stored `monthly_savings`; it also raised the peak 3.76 to 3.96 kW, which the card shows rather than hides); `axe-core` with colour contrast found no violations on any page in light and dark mode after the fix below; every non-destructive button on all nine pages was clicked (no console errors, no unnamed control, no dialog left open); deleting an appliance through its confirmation dialog removed it, with Cancel focused first and the count unchanged until confirmed. Reset and restore were verified in Stage 7.

### Problems met and fixed
- **Real accessibility bug:** in dark mode the red "Delete all data" button had white text on a light red (2.8:1; 4.5:1 needed). Found by the in-browser contrast scan; fixed with a dedicated dark-mode foreground colour.
- The Reports page would have said "No optimization runs yet" after a failed request; the month tiles showed nothing on failure. Both fixed and tested.
- Lazy pages made existing tests look for headings before the page had loaded; fixed by preloading pages in the test renderer and awaiting headings after navigation.
- A cards test looked for a region that had no accessible name; this exposed that titled cards were not labelled regions for screen readers. `Card` now labels itself.
- Vite served a stale stylesheet after an edit, which made the first contrast fix look ineffective; a forced rebuild showed it was working.

### Not done / deferred, and honest caveats
- **Screen readers were not run.** Axe checks names, roles and labels; I did not listen to NVDA or Narrator.
- **Downloads inside the packaged Tauri window (WebView2) are still unverified.** The desktop shell was not driven this stage. It should be confirmed on the packaged build in Stage 9.
- The Overview does not show report history (there is none to show: reports are generated on demand and not stored).
- `default_optimization_priority` is stored but unused.
- A very narrow window was not redesigned: the sidebar keeps its width and the content scrolls.

## Stage 9 — Packaging and final verification (2026-11-11) ✅ complete

### What was done
- **Frozen backend** (`scripts/build-backend.ps1`, `npm run build:backend`): PyInstaller one-folder build, 188 MB. Hidden imports and data files were listed deliberately (OR-Tools native libraries, Uvicorn, Alembic, migration scripts as files).
- **Bundle configuration**: `tauri.conf.json` ships that folder as the `backend/` resource and builds an NSIS installer for the current user.
- `npm run package` runs both steps; PyInstaller is a dev dependency; `test_frozen_backend.py` runs the frozen executable.

### The installer build, and how the blocker was solved
`tauri build` first failed at the NSIS step: its downloader timed out (`timeout: global`) although `curl` reached the same address quickly. With your approval the missing pieces were obtained under these rules:
- **Only official sources**: `github.com/tauri-apps/...` releases.
- **Exact versions read from the tool itself**: the URLs and SHA-1 hashes are embedded in the installed Tauri CLI (2.12.4), so nothing was guessed. The CLI needs the NSIS 3.13 zip and **one** extra file, `nsis_tauri_utils.dll` v0.5.3. (It does not use `ApplicationID.dll`, which I had wrongly assumed earlier, so that file was not downloaded.)
- **Integrity checked three ways**: the DLL's SHA-1 (`75197fee3c6a814fe035788d1c34ead39349b860`) equals the hash embedded in the CLI; its SHA-256 (`5ba143b5db4a87d32d6e7802e033330aae56cbceabe0d1e3ba41948385ad4709`) equals the digest GitHub publishes for that release asset (published by `github-actions[bot]`); the NSIS zip's SHA-1 (`db14f8af2ea346b786c6ae19343f61aaf5e09b8e`) equals the embedded hash.
- Both files were placed in Tauri's own cache folder (`%LOCALAPPDATA%\tauri\NSIS`). No security setting was changed.

### Results
- **Installer**: `src-tauri/target/release/bundle/nsis/PowerShift_0.1.0_x64-setup.exe`, 60,787,893 bytes (57.97 MiB), SHA-256 `2AA84D96DD5E79E78D67F659144C6F3E7CBF2DC7B3B23EDEE92BF2B816A46138`. Not code-signed (`NotSigned`).
- **Install** (silent, `/S`, exit code 0, no administrator rights): `%LOCALAPPDATA%\PowerShift\` with `powershift.exe`, `uninstall.exe`, `backend\powershift-backend.exe` (1,194 files, 194 MB); registry uninstall entry (PowerShift 0.1.0); Start-menu shortcut `PowerShift.lnk` pointing at the installed exe. No desktop shortcut.
- **Launch** from the Start-menu shortcut: window titled PowerShift; the frozen backend ran as a child process from the install folder; the UI showed "Backend connected", version 0.1.0.
- **Database**: created at `%APPDATA%\com.powershift.app\powershift.db` (schema `0005`), plus `backups\` and `logs\`.
- **Persistence**: sample data loaded, a new appliance added through the form and the Dark theme chosen; the database file held 10 appliances and `dark`; the window was closed (app and backend both exited); on relaunch the appliance, the sample data and the Dark theme were all there.
- **Exports** (real mouse clicks in the installed app): PDF (valid `%PDF-`), JSON export (10 appliances including the new one), backup `.db` (SQLite integrity check ok, contains the new appliance and the Dark theme). Windows renamed repeats to `name (1)`.
- **Uninstall** (silent, exit code 0): install folder, Start-menu shortcut and registry entry removed; no PowerShift processes left. **User data untouched**: all five files in `%APPDATA%\com.powershift.app` had identical size and SHA-256 before and after.
- Earlier in the stage: frozen backend alone (migrate, CP-SAT OPTIMAL saving 400.47 identical to source, PDF, backup); PDFs rendered and inspected as images (layout clean, bill total 3,317.48 matches the dashboard).
- 396 backend (with the frozen backend built), 145 frontend and 6 Rust tests pass; ruff, mypy, tsc and ESLint clean.

### Problems met
- Tauri's NSIS download timed out (solved as above). Tauri also deleted a manually unpacked NSIS folder when it found a file missing, so the folder had to be rebuilt from the verified files.
- WebView2 asks "Download multiple files" when downloads are started by scripted clicks; real mouse clicks do not trigger it.
- Git Bash rewrote a `#/settings` argument into a Windows path (test script only).

### Known limitations and caveats
- **Sandbox redirection.** The shell used for testing runs inside the Claude desktop app's package, so Windows stores some writes under `%LOCALAPPDATA%\Packages\Claude_*\LocalCache` and shows them at the normal path only to processes in that package. The installer, app, backend, data and uninstall all worked from that view, but I could not prove the files are visible in the user's own Explorer or that the Start-menu shortcut is visible in the user's own Start menu. A short manual check on the user's side is recommended (see the report).
- **Unsigned installer**: SmartScreen may warn when a downloaded copy is first run. The locally built file has no internet-download mark, so no warning appeared during testing, and none was bypassed.
- **Silent mode only**: the installer's wizard pages (language, folder choice, "Delete the application data" checkbox on uninstall) were not exercised.
- Reinstalling over existing data and upgrading from an earlier version were not tested.
- Screen readers were not run (Stage 8 caveat unchanged).
- The 194 MB backend is mostly OR-Tools; it could be trimmed later.
- WebView2 saves downloads silently to Downloads; there is no "Save as" dialog.
- The test data created by this verification (sample data, one appliance, one backup) remains in `%APPDATA%\com.powershift.app` and in Downloads; nothing was cleaned up, as requested.

## UI redesign: black and electric lime (after Stage 9)

Branch `redesign/black-lime`, built on the Stage 9 baseline `8573d87` (history untouched).

### Decisions
- **Presentation only.** No backend, API, database or migration change. Every number on screen comes from a query that already existed.
- **Tokens, then components, then pages.** All colours were already semantic tokens, so replacing the token values re-themed the whole app; components were restyled once and the pages followed.
- **Lime has two jobs, so two tokens.** A lime fill with black text works everywhere (17.8:1); lime as text works on dark but fails on white (1.2:1), so text and outlines use `accent-ink` (olive in the light theme).
- **Chart colours carry meaning.** Grey is fixed load; lime is the flexible load the scheduler can move. Single-series charts use lime.
- **Motion budget.** Only `transform` and `opacity`; at most three infinite animations on the dashboard; one featured floating tile; no blur filters; none of it runs under reduced motion. The proposed particle dots were left out (glow plus faint grid only), as agreed.
- **Honest motion.** The scheduler's running state shows real elapsed seconds and the chosen limit, never a percentage. The potential-savings tile floats and turns lime only for a validated, cost-reducing run.
- **Open questions answered with the recommended defaults:** Appliances stays a table; light theme kept; system font (no new dependency); no particle dots.

### Built
- Tokens and motion CSS; `Button`, `Card`, `StatTile`, `Badge`, `EmptyState`, `SegmentedControl`, inputs, `Modal` restyled; new `AppBackdrop`, `ProgressBeam`, `BeforeAfterBars`.
- Collapsible sidebar (remembered), lime active indicator, page fade, backdrop.
- Dashboard: energy, bill, peak and savings tiles; hourly profile; scheduler summary with before/after; category breakdown; insights; the existing household, engine, simulation and backup cards.
- Charts re-coloured and animated (draw-in, bar growth, restyled tooltips); 24-hour price strip on time-of-use tariffs.
- Smart Scheduler: running panel, staggered result, before/after comparison for bill and peak.
- `docs/DESIGN_SYSTEM.md`.

### Verified
- 396 backend, 157 frontend (12 new) and 6 Rust tests pass; ruff, mypy, tsc and ESLint clean; production build succeeds (first-screen bundle 374 kB, was 372 kB).
- In a real browser, dark and light, all nine pages: `axe-core` including colour contrast reported 0 violations, and the page console showed no errors from the app. Screens inspected visually: Overview (dark and light, collapsed sidebar), Appliances, Tariff, Energy, Peak Load, Scheduler (result), Reports, Settings.
- Measured on the dashboard: three infinite animations (two glows, one floating tile); only `transform` and `opacity` animated.

### Problems met and fixed
- Light-theme badge contrast 4.48:1 (needs 4.5); the olive was darkened to `#46720d` (5.1:1).
- Several axe results were measured mid-animation or mid-theme-transition; they disappeared when measured after the animation, and the scan waits 3 s per page.
- The heavier Overview made one accessibility test exceed the 5-second default under parallel load; the suite timeout was raised to 20 s (nothing was skipped).
- A shell heredoc failure again required writing larger files with the file tool.

### Known limitations
- The default theme is still "System": a new installation follows Windows, and a fresh database cannot tell "never chosen" from "chose System". Making Dark the default needs a small backend or settings change, which was not made without approval.
- Frame rate on slow hardware was not measured.
- The installer that existed before the redesign does **not** contain it; see the packaging notes below this entry once the new installer is built.
