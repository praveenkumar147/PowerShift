# User Guide

*Covers features available now. Last updated: Stage 3.*

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

## Overview

Shows this month's estimated energy, bill, average per day and the share of energy
that comes from flexible appliances (what a scheduler could shift), plus the hourly
profile, your household summary, and the local engine status.

## Theme

Use the switch at the bottom of the sidebar to choose **Light**, **Dark** or
**System** (follows Windows). Your choice is remembered.

## Not available yet

Peak load analysis, the smart scheduler, simulations, reports and backups are added
in later stages. Their pages say "Not built yet".
