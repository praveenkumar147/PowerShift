# User Guide

*Covers features available now. Last updated: Stage 8.*

All numbers PowerShift shows are **estimates** calculated from what you enter.
PowerShift does not connect to a meter and does not measure anything.

## Starting PowerShift

When you open PowerShift, a "Starting PowerShift" screen appears for a moment while
the local calculation engine and database start. No internet connection is needed.

If the engine can't start, you'll see the reason and a **Try again** button. A
detailed log is in the `logs` folder inside the app data folder.

## Trying it with sample data

On a brand-new install, the Overview offers **Load sample data**. It creates a
"Sample household (demo data)", nine typical appliances and a sample time-of-use tariff
with **invented rates, not a real utility's prices**. It only works when the database is
empty, so it never mixes with your own data.

## 1. Set up your household (Settings)

On first use, the Overview shows **Set up household**. Enter:

| Field | Meaning |
|---|---|
| Household name | Any name |
| Location | Optional, for your reference. PowerShift never guesses your tariff from it. |
| Number of occupants | People living in the home |
| Maximum household load (kW) | The most power your connection allows **at one moment**, e.g. the sanctioned load on your bill. This is power (kW), not energy (kWh). |
| Currency code | e.g. INR, USD, EUR. Display only; nothing is converted. |
| Time format | 24-hour (22:00) or 12-hour (10:00 PM) |

## 2. Add appliances (Appliances)

Click **Add appliance**.

### Power settings

- **Rated power (W)**: the number on the label, for one unit at full power.
- **Quantity**: e.g. 6 identical bulbs.
- **Duty cycle (%)**: how much of its "on" time the appliance actually draws full power.
  A fridge compressor cycles on and off, so about 40%. A kettle or heater is 100%.

**Rated power vs. actual use.** A 150 W fridge that's on all day does not use
150 W × 24 h = 3.6 kWh. At 40% duty cycle it averages 60 W, so about 1.44 kWh per day.
PowerShift uses the average for energy and the full rated power for load-limit warnings,
because your connection limit is about the highest instant, not the average.

### Usage type

- **Fixed schedule**: the appliance runs at set times and won't be moved (fridge, router,
  lights). Add one or more on-periods.
- **Flexible**: the start time can move (washing machine, dishwasher, water heater). Enter:
  - **Run duration**: how long one run takes.
  - **Earliest start / Latest finish**: the whole run must happen in this window.
  - **Usual start today**: when you normally start it now. Later stages measure savings against this.
  - **Preferred time** (optional): a softer preference inside the window.
  - **Must run without interruption**: most cycles can't pause.

### Times past midnight

An end time earlier than the start runs past midnight: 22:00 → 06:00 is an 8-hour
overnight window. **00:00 as an end time means midnight**, so 00:00 → 00:00 is all day.
Times use 15-minute steps.

### Operating days

Pick the days the appliance is used. **Every day** and **Weekdays** are shortcuts.

### Scheduling

- **Priority**: used later by the scheduler when not everything fits.
- **Can run at the same time as other heavy appliances**: untick to keep it from
  overlapping other appliances that are also unticked.

### The appliance list

Shows each appliance's power (rated, and average after duty cycle), usage, days,
and estimated energy per day. A ⚠ warning appears when one appliance alone would exceed
your household load limit. Use the search box and filters to narrow the list.
**Edit** (pencil) and **Delete** (bin) are on each row; deleting asks for confirmation.

## 3. Enter your tariff (Electricity Tariff)

Click **Add tariff** and copy the rates from your bill or your utility's published tariff.
PowerShift never assumes rates from your location.

| Type | When to use | What you enter |
|---|---|---|
| **Flat rate** | One price at all times | Price per kWh |
| **Time of use** | Price changes during the day | Periods with a price each. They must cover all 24 hours exactly once, either every day or separately for weekdays and weekends. 22:00 to 06:00 runs overnight. |
| **Slab-based** | Price depends on monthly usage | Bands such as 0-100 kWh, 100-200 kWh, and "above" (leave the last limit empty). Choose whether each band is charged at its own rate (most common) or all units at the rate of the highest band reached. |

**Additional charges** are added after the energy charge:
- *Fixed per month*, e.g. meter rent.
- *Extra per kWh*, e.g. a fuel surcharge.
- *Percentage*, e.g. electricity duty or tax, applied to the subtotal of the lines above.

You can keep several tariffs; **Use this tariff** chooses which one is used for costs.

> Under a flat or slab tariff, running an appliance at a different time does not change
> the bill, because the total kWh are the same. Only time-of-use tariffs reward shifting.

## 4. Energy Analysis

Choose a date range (up to a year) and optionally a category. You'll see:

- **Headline figures**: total energy, average per day, energy charge, largest consumer.
- **Daily consumption**: days with flexible appliances (e.g. washing days) stand out.
- **By appliance / By category**: switch between energy and cost.
- **Hourly profile**: fixed (baseline) and flexible load through a typical day, or a chosen weekday.
- **Monthly projection**: energy per month for the year.
- **Bill estimate**: an itemised bill for any month, including fixed charges and taxes.

Every chart has **Show data table** for the exact numbers.

**Reading the costs.** Costs on charts and per appliance are *energy charges only*;
fixed charges and taxes appear in the bill estimate. With a slab tariff, a single day's
or appliance's cost uses the month's average rate, since slab prices depend on the
monthly total. The note box at the bottom of the page lists these assumptions.

## 5. Peak Load

Energy (kWh) is what you pay for. **Demand (kW)** is how hard your connection is pushed
at one moment. Your load limit is about demand: run the water heater, AC and dishwasher
together and you may exceed it even if your monthly energy is modest.

The page shows one day at a time (it opens on the day with the highest peak; pick
another day with the buttons or by clicking a bar in **Peak by day**):

- **Peak demand (worst case)**: every appliance that is on at full power at the same
  moment. Used for limit warnings, because a breaker reacts to the highest instant.
- **Expected peak**: using duty cycles; the typical highest demand.
- **Headroom / Time over limit**: how close you are to your household load limit.
- **A red alert** lists each period over the limit, by how much, and what is running.
- **24-hour load profile**: demand in 15-minute steps, fixed (blue) and flexible (orange),
  with your limit as a dashed line. Hover to see what is on.
- **At the peak**: the appliances running at the highest moment.
- **High-demand periods** (≥ 80% of the limit), **heavy appliances overlapping**
  (1 kW or more each) and **not allowed together** (appliances you marked as not
  simultaneous that currently overlap).

Only the flexible part of a peak can be moved; the Smart Scheduler (next stage) does that.

## 6. Smart Scheduler

The scheduler finds start times for your **flexible** appliances that lower your estimated
cost and/or peak demand, while keeping every run inside the window you allowed, within
your load limit, and apart from appliances you marked "not at the same time". It never
changes your appliance settings; it recommends.

1. Choose a **goal**: *Lowest cost*, *Balanced* (use the slider to weigh cost against peak),
   or *Lowest peak*.
2. Optionally choose finer **start times** (30 or 15 minutes) and a **time limit**.
3. Select **Optimize schedule**.

**Reading the result.** The banner says exactly what was proven:
*Optimal and verified* (best possible for your goal), *Valid but not proven optimal* (the
time limit ran out; a better schedule may exist), *No valid schedule exists* (with the reason),
or *No schedule found within the time limit*.

You also get: estimated bill and savings (negative if the new schedule would cost more),
peak demand and time over the limit, each appliance's usual and recommended start with the
**reasons**, before/after load profiles on one scale, and an **independent validation**
checklist. A schedule is only shown as a recommendation if every check passes.

> Savings need a **time-of-use** tariff. Under a flat or slab tariff the bill does not
> depend on the time of day, so only peak demand and conflicts can improve.

Every run is saved in **History** with its settings, so you can compare goals later.
Results are estimates from your settings, not measurements or guarantees.

## 7. Simulation Lab

Ask "what if?" without touching your real data. A **scenario** is a set of changes applied to a
**copy** of your household; your real appliances, tariffs and settings are never changed.

Select **New scenario**, name it, and add changes:

| Change | Example |
|---|---|
| Add a new appliance | A bedroom air conditioner |
| Add another copy of an appliance | A second refrigerator |
| Change an appliance | More AC hours, fewer washing days, a different window |
| Remove an appliance | What if I got rid of the old heater? |
| Use a different tariff | Compare your saved tariffs |
| Change the household load limit | A bigger connection |

A scenario also has a **scheduling goal**. A scenario with no changes compares goals on today's data:
make one scenario per goal and compare them.

Select **Run scenario**. For each scenario you see, **against your current household**:

- Energy per month, and the bill before and after the smart scheduler (a `+` costs more, a `−` saves).
- Peak demand, and the recommended schedule with reasons if one exists.
- If the scenario has no valid schedule (for example its load limit is too low), the reasons, while the numbers at usual times are still shown.

The **Comparison** at the top puts every scenario that has been run next to your current household.
If you change your real appliances after running a scenario, results go out of date: run them
again. The page warns when a comparison mixes results from different households. Edited
scenarios show "Edited since last run".

> Every figure is an estimate from your settings, not a measurement or a guarantee.

## Overview

Shows this month's estimated energy, bill, average per day and the share of energy
that comes from flexible appliances (what a scheduler could shift), plus the hourly
profile, your household summary, and the local engine status.

Three cards summarise your recent work, each with a link to its page:

- **Smart Scheduler**: your latest run, with the estimated change in your monthly bill and
  whether the result is proven optimal. If no valid schedule was found, it says so.
- **Simulation Lab**: how many scenarios you have and the latest result. "Edited since; run it
  again" means the figures are out of date.
- **Your data**: when you last made a backup, and a link to Settings.

If something cannot be loaded, that card says so and the others keep working.

## Theme

Use the switch at the bottom of the sidebar to choose **Light**, **Dark** or
**System** (follows Windows). Your choice is saved with your data (so it comes back with a restored
backup) and remembered by the app window.

## Keyboard and screen readers

- Press **Tab** once after the app opens to reveal **Skip to main content**, then **Enter** to jump past the menu.
- After you open another section, keyboard focus moves to the top of the page and the window title
  names the section.
- Dialogs trap focus, **Esc** closes them, and the safe button (Cancel) is selected first when something would be deleted.
- If Windows is set to reduce animations, PowerShift shows none.

## 8. Reports

Open **Reports**, choose a report, choose **PDF** or **CSV**, and select **Export**.
Your browser or the app saves the file; the page shows the file name it asked to save.

| Report | Contents |
|---|---|
| Daily energy | Energy and cost per day for a date range (and optional category) |
| Monthly energy | Each month of a year |
| Appliance consumption | What every appliance uses and costs |
| Electricity bill estimate | The itemised bill for a month |
| Peak load | The busiest day, or the weekday you pick |
| Optimization comparison | One Smart Scheduler run (the latest, or one you choose) |
| Simulation comparison | Scenarios you have run, next to your current household |

Every report states that its figures are **estimates**, lists the assumptions used and names the
tariff it depends on. CSV files open in Excel with correct characters. PDF files embed the
rupee sign when the Segoe UI font is installed. The last two reports need a run or a scenario
that has been run; the page says so and links to the right place.

## 9. Backups, restore, export and reset (Settings)

- **Create backup** saves a complete copy of your data in the backups folder. Backups are
  never deleted automatically.
- **Download** (next to a backup) saves a copy somewhere you choose.
- **Restore**: choose a stored backup or **Restore from a file**. PowerShift first checks the
  file and shows what it contains (household, appliances, tariffs, scenarios, runs). Nothing is
  replaced until you select **Replace my data**. A copy of your current data is saved first
  (`pre-restore-...`), so you can undo a restore by restoring that copy. A file that is not a
  valid PowerShift backup is rejected and your data is not changed.
- **Export data** saves all your data as one JSON file (for your own records).
- **Delete all data**: type `RESET` to confirm. A backup (`pre-reset-...`) is saved first and
  existing backups are kept.
- **About** shows the version, where your data lives and how much is stored.

## Not available yet

The Windows installer is added in Stage 9.
