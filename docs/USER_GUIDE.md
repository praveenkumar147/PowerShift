# User Guide

*Covers features available now. Last updated: Stage 2.*

All numbers PowerShift shows are **estimates** calculated from what you enter.
PowerShift does not connect to a meter and does not measure anything.

## Starting PowerShift

When you open PowerShift, a "Starting PowerShift" screen appears for a moment while
the local calculation engine and database start. No internet connection is needed.

If the engine can't start, you'll see the reason and a **Try again** button. A
detailed log is in the `logs` folder inside the app data folder.

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

## Overview

Shows your household's occupants and load limit, how many fixed and flexible
appliances you have, and the local engine status (version, database schema, database
file location).

## Theme

Use the switch at the bottom of the sidebar to choose **Light**, **Dark** or
**System** (follows Windows). Your choice is remembered.

## Not available yet

Electricity tariffs, cost estimates, energy charts, peak load analysis, the smart
scheduler, simulations, reports and backups are added in later stages. Their pages
say "Not built yet".
