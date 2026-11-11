# Design system

*Black and electric lime. Last updated: the UI redesign after Stage 9.*

The look is **80% calm minimalism and 20% motion**. Everything is built from the tokens in
`src/index.css`; components never contain raw colours, so a theme is just a different set of variables.

## Colour tokens

| Token (Tailwind name) | Dark (primary look) | Light | Used for |
|---|---|---|---|
| `canvas` | `#000000` | `#f4f4ef` | Page background |
| `surface` | `#111111` | `#ffffff` | Cards |
| `surface-raised` | `#1b1b1b` | `#f7f7f2` | Inputs, hover rows, tracks |
| `border` | `#292929` | `#e1e1d8` | All borders |
| `fg` | `#ffffff` | `#0a0a0a` | Headings and main text |
| `muted` | `#a3a3a3` | `#5c5c5c` | Secondary text |
| `accent` | `#c6ff33` | `#c6ff33` | **Fills**: primary buttons, active bars, chart highlights. Always paired with black text (`accent-fg`, 17.8:1) |
| `accent-ink` | `#c6ff33` | `#46720d` | Lime **as text, icons, outlines, selected borders** (olive on light, because lime on white is only 1.2:1) |
| `accent-soft` | `#272e15` | `#eef7d2` | Quiet lime tint behind selected items |
| `warning` | `#ffc857` | `#b45309` | Real warnings only |
| `danger` / `danger-fg` | `#ff5555` / `#000000` | `#c62828` / `#ffffff` | Errors and destructive buttons |
| `success` | `#c6ff33` | `#3f6212` | Success messages |

Rules: black dominates; lime is for the one thing that matters (primary action, active item, the optimum,
the flexible load); amber and red are never decoration; no neon glows.

**Contrast** (WCAG, measured): white on `#111` 18.9, grey on `#111` 7.5, lime on `#111` 16.0, red on `#111` 6.0,
amber on `#111` 12.3. In light: olive on white 5.7, olive on the soft tint 5.1. `axe-core` found no
colour-contrast violations on any of the nine pages in either theme.

**Chart colours.** Fixed load is grey (`series-1`: `#7a7a7a` dark / `#8a8a8a` light); flexible load, the part the
scheduler can move, is lime (`series-2`: `#c6ff33` dark / olive `#46720d` light). Single-series charts use the
lime. The two series differ by 3.6:1 in lightness, so they stay distinguishable without relying on hue.

## Shape and type

- Radii: cards `14px` (`rounded-card`), controls `10px` (`rounded-control`), pills fully round.
- Shadows: almost none; depth comes from borders. `shadow-float` is used only for floating cards and dialogs.
- Fonts: the system stack (Segoe UI Variable on Windows 11), no download. Page titles and big numbers use the
  display cut with tabular figures. Scale: page title 24px, section 16px, body 14px, label 12px.

## Components (`src/components/`)

| Component | Purpose |
|---|---|
| `ui/Button`, `Badge`, `Field`, `inputs`, `SegmentedControl` | Controls. One lime primary button per view. |
| `ui/Card` | Titled, labelled region. Props: `index` (staggered entrance), `floating`, `interactive`. |
| `ui/StatTile` | Headline number. Props: `highlight` (lime value), `floating`, `index`. |
| `ui/AppBackdrop` | The atmosphere: two drifting lime glows and a faint grid. |
| `ui/ProgressBeam` | Indeterminate progress bar. Shows no percentage, by design. |
| `ui/BeforeAfterBars` | Two bars on one shared scale; an improvement is lime, a worse result is amber. |
| `ui/EmptyState`, `Modal`, `ConfirmDialog`, `NotesBox`, `Spinner`, `PageHeader` | Restyled shared pieces. |
| `charts/ChartCard`, `chartTheme` | Chart frame, series colours, `chartMotion()` (entrance animation, reduced-motion aware). |
| `features/tariffs/PriceStrip` | 24-hour price strip for time-of-use tariffs. |
| `features/overview/*` | Dashboard cards (Insights, Category breakdown, Scheduler, Simulation, Your data). |

## Motion

Only `transform` and `opacity` are animated, so it all runs on the GPU and never causes layout work.

| Effect | How | Where |
|---|---|---|
| Entrance | `animate-rise`: fade plus 10px upward, 480 ms; cards are staggered 60 ms apart, capped at 8 | Cards, tiles, schedule rows |
| Page change | `animate-fade`, 240 ms | Whole page |
| Floating | `animate-float`: 5 px, 7 s loop | One featured tile per page (potential savings) |
| Atmosphere | `ps-drift-*`: 48 s and 64 s | Backdrop glows |
| Hover | 2 px lift and border brighten (`interactive` cards); small icon scale in the sidebar | |
| Charts | `chartMotion()`: 650 ms draw-in and ease between data changes | All charts |
| Scheduler | Beam, real elapsed seconds, bars growing from the left, rows rising in turn | Smart Scheduler |
| Bars | `ps-grow-x`: scale from the left, 800 ms | `BeforeAfterBars` |

At most three animations loop forever on the dashboard (two glows and one floating tile).
`prefers-reduced-motion: reduce` stops everything, including the background drift and the chart entrance.

**Honesty rule for motion:** animation may never imply something that is not true. The scheduler's progress
indicator shows only the goal, the real elapsed time and the chosen time limit. Nothing animates to a number that
was not computed.

## Themes

Dark is the primary look. The light theme is kept and uses the same tokens. The choice (Light, Dark, System) is
stored in the database (`PUT /api/settings/preferences`) and applied at start-up from local storage.
