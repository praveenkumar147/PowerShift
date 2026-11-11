"""Builds the seven reports from the app's own services, so a report's figures are
exactly the figures the app shows."""

from __future__ import annotations

import calendar
from collections.abc import Callable
from datetime import UTC, date, datetime
from decimal import Decimal
from enum import StrEnum
from functools import partial

from pydantic import BaseModel, ConfigDict, model_validator
from sqlalchemy.orm import Session

from powershift.core.errors import ValidationFailedError
from powershift.db.repositories.household import HouseholdRepository
from powershift.domain.appliance import ApplianceCategory
from powershift.domain.household import HouseholdProfile, TimeFormat
from powershift.domain.tariff import ChargeKind, DayType, SlabMode, TariffSpec, TariffType
from powershift.domain.time_window import format_minute
from powershift.reports.model import Cell, Report, ReportTable
from powershift.schemas.optimization import OptimizationRunRead
from powershift.schemas.peak_load import EpisodeRead, WindowRead
from powershift.services.energy_service import EnergyService
from powershift.services.optimization_service import OptimizationService
from powershift.services.peak_load_service import PeakLoadService
from powershift.services.simulation_service import SimulationService
from powershift.services.tariff_service import TariffService

WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
TIME_FORMAT = Callable[[int], str]
Built = tuple[str, list[tuple[str, str]], list[ReportTable], list[str], bool]
"""(title, parameters, tables, assumptions, show tariff configuration)"""
PERCENT = 100
KWH_DECIMALS = 3

TYPE_LABELS = {
    TariffType.FLAT: "Flat rate",
    TariffType.TOU: "Time of use",
    TariffType.SLAB: "Slab-based",
}
DAY_LABELS = {DayType.ALL: "every day", DayType.WEEKDAY: "weekdays", DayType.WEEKEND: "weekends"}
SLAB_LABELS = {
    SlabMode.TELESCOPIC: "each slab at its own rate",
    SlabMode.WHOLE_USAGE: "all units at the highest slab reached",
}


class ReportKind(StrEnum):
    DAILY_ENERGY = "daily_energy"
    MONTHLY_ENERGY = "monthly_energy"
    APPLIANCE_CONSUMPTION = "appliance_consumption"
    BILL_ESTIMATE = "bill_estimate"
    PEAK_LOAD = "peak_load"
    OPTIMIZATION_COMPARISON = "optimization_comparison"
    SIMULATION_COMPARISON = "simulation_comparison"


class ReportFormat(StrEnum):
    CSV = "csv"
    PDF = "pdf"


class ReportParams(BaseModel):
    """Optional inputs; each report uses the ones it needs and has a sensible default."""

    model_config = ConfigDict(extra="forbid")

    start: date | None = None
    end: date | None = None
    category: ApplianceCategory | None = None
    year: int | None = None
    month: int | None = None
    weekday: int | None = None
    run_id: int | None = None
    scenario_ids: list[int] | None = None

    @model_validator(mode="after")
    def check_ranges(self) -> ReportParams:
        errors: dict[str, str] = {}
        if self.month is not None and not 1 <= self.month <= 12:
            errors["month"] = "Month must be between 1 and 12."
        if self.year is not None and not 2000 <= self.year <= 2100:
            errors["year"] = "Year must be between 2000 and 2100."
        if self.weekday is not None and not 0 <= self.weekday <= 6:
            errors["weekday"] = "Weekday must be between 0 (Monday) and 6 (Sunday)."
        if errors:
            raise ValueError("; ".join(errors.values()))
        return self


def _num(value: Decimal) -> str:
    return format(value.normalize(), "f")


def describe_tariff(spec: TariffSpec, fmt: TIME_FORMAT) -> tuple[tuple[str, str], ...]:
    rows = [
        ("Tariff", spec.name),
        ("Type", TYPE_LABELS[spec.tariff_type]),
        ("Effective from", spec.effective_date.isoformat()),
    ]
    if spec.tariff_type is TariffType.FLAT and spec.flat_rate_per_kwh is not None:
        rows.append(("Price per kWh", _num(spec.flat_rate_per_kwh)))
    for period in spec.tou_periods:
        window = f"{fmt(period.window.start_minute)}-{fmt(period.window.end_minute)}"
        rows.append(
            (
                f"Price {window} ({DAY_LABELS[period.day_type]})",
                f"{_num(period.rate_per_kwh)} per kWh",
            )
        )
    if spec.slabs:
        rows.append(("Slab charging", SLAB_LABELS[spec.slab_mode]))
        lower = Decimal(0)
        for slab in spec.slabs:
            label = (
                f"Above {_num(lower)} kWh"
                if slab.up_to_kwh is None
                else f"{_num(lower)}-{_num(slab.up_to_kwh)} kWh"
            )
            rows.append((f"Slab {label}", f"{_num(slab.rate_per_kwh)} per kWh"))
            lower = slab.up_to_kwh or lower
    for charge in spec.charges:
        text = {
            ChargeKind.FIXED_MONTHLY: f"{_num(charge.amount)} per month",
            ChargeKind.PER_KWH: f"{_num(charge.amount)} per kWh",
            ChargeKind.PERCENTAGE: f"{_num(charge.amount)}% of subtotal",
        }[charge.kind]
        rows.append((charge.label, text))
    return tuple(rows)


class ReportService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._household: HouseholdProfile | None = HouseholdRepository(session).get()
        self._currency = self._household.currency_code if self._household else None
        twelve = bool(self._household and self._household.time_format is TimeFormat.H12)
        self._fmt: TIME_FORMAT = partial(format_minute, twelve_hour=twelve)

    # --- Entry point ---------------------------------------------------------------------

    def build(self, kind: ReportKind, params: ReportParams, now: datetime | None = None) -> Report:
        builders = {
            ReportKind.DAILY_ENERGY: self._daily_energy,
            ReportKind.MONTHLY_ENERGY: self._monthly_energy,
            ReportKind.APPLIANCE_CONSUMPTION: self._appliance_consumption,
            ReportKind.BILL_ESTIMATE: self._bill_estimate,
            ReportKind.PEAK_LOAD: self._peak_load,
            ReportKind.OPTIMIZATION_COMPARISON: self._optimization,
            ReportKind.SIMULATION_COMPARISON: self._simulation,
        }
        title, parameters, tables, assumptions, show_tariff = builders[kind](params)
        active = TariffService(self._session).active_spec()
        return Report(
            kind=kind.value,
            title=title,
            generated_at=now or datetime.now(UTC),
            household=self._household.name if self._household else None,
            currency=self._currency,
            parameters=tuple(parameters),
            tariff=describe_tariff(active[1], self._fmt) if show_tariff and active else (),
            tables=tuple(tables),
            assumptions=tuple(assumptions),
        )

    # --- Helpers ----------------------------------------------------------------------------

    def _money(self, label: str) -> str:
        return f"{label} ({self._currency})" if self._currency else label

    @staticmethod
    def _month_range(today: date) -> tuple[date, date]:
        return today.replace(day=1), today.replace(
            day=calendar.monthrange(today.year, today.month)[1]
        )

    def _period(self, params: ReportParams) -> tuple[date, date]:
        first, last = self._month_range(date.today())
        return params.start or first, params.end or last

    @staticmethod
    def _year_month(params: ReportParams) -> tuple[int, int]:
        today = date.today()
        return params.year or today.year, params.month or today.month

    # --- The seven reports ---------------------------------------------------------------------
    # Each returns (title, parameters, tables, assumptions, show_tariff_configuration).

    def _daily_energy(self, p: ReportParams) -> Built:
        start, end = self._period(p)
        r = EnergyService(self._session).report(start, end, p.category)
        priced = r.energy_charge is not None
        charge = [self._money("Energy charge")] if priced else []
        rows = tuple(
            (
                d.date.isoformat(),
                WEEKDAYS[d.date.weekday()],
                d.kwh,
                *([d.energy_charge] if priced else []),
            )
            for d in r.daily
        )
        total = ("Total", f"{r.days} days", r.total_kwh, *([r.energy_charge] if priced else []))
        table = ReportTable(
            "Energy per day", ("Date", "Weekday", "Energy (kWh)", *charge), (*rows, total), True
        )
        params = [
            ("Period", f"{r.start} to {r.end} ({r.days} days)"),
            ("Category", p.category.value if p.category else "All categories"),
        ]
        return "Daily energy report", params, [table], r.notes, True

    def _monthly_energy(self, p: ReportParams) -> Built:
        year, _ = self._year_month(p)
        r = EnergyService(self._session).monthly(year, p.category)
        priced = any(m.bill_total is not None for m in r.months)
        rows: tuple[tuple[Cell, ...], ...] = tuple(
            (calendar.month_name[m.month], m.days, m.kwh, *([m.bill_total] if priced else []))
            for m in r.months
        )
        total: tuple[Cell, ...] = (
            "Total",
            sum(m.days for m in r.months),
            round(sum(m.kwh for m in r.months), KWH_DECIMALS),
            *([round(sum(m.bill_total or 0 for m in r.months), 2)] if priced else []),
        )
        bill = [self._money("Estimated bill")] if priced else []
        table = ReportTable(
            "Energy per month", ("Month", "Days", "Energy (kWh)", *bill), (*rows, total), True
        )
        params = [
            ("Year", str(year)),
            ("Category", p.category.value if p.category else "All categories"),
        ]
        return "Monthly energy report", params, [table], r.notes, True

    def _appliance_consumption(self, p: ReportParams) -> Built:
        start, end = self._period(p)
        r = EnergyService(self._session).report(start, end, p.category)
        priced = r.energy_charge is not None
        charge = [self._money("Energy charge")] if priced else []
        appliances = ReportTable(
            "By appliance",
            ("Appliance", "Category", "Type", "Energy (kWh)", "Share of energy (%)", *charge),
            tuple(
                (
                    a.name,
                    a.category.value,
                    a.mode.value,
                    a.kwh,
                    round(a.share * PERCENT, 1),
                    *([a.energy_charge] if priced else []),
                )
                for a in r.appliances
            ),
        )
        categories = ReportTable(
            "By category",
            ("Category", "Energy (kWh)", "Share of energy (%)", *charge),
            tuple(
                (
                    c.category.value,
                    c.kwh,
                    round(c.share * PERCENT, 1),
                    *([c.energy_charge] if priced else []),
                )
                for c in r.categories
            ),
        )
        params = [
            ("Period", f"{r.start} to {r.end} ({r.days} days)"),
            ("Category", p.category.value if p.category else "All categories"),
            ("Total energy (kWh)", str(r.total_kwh)),
        ]
        return "Appliance consumption report", params, [appliances, categories], r.notes, True

    def _bill_estimate(self, p: ReportParams) -> Built:
        year, month = self._year_month(p)
        b = EnergyService(self._session).bill(year, month)
        summary = ReportTable(
            "Summary",
            ("Measure", "Value"),
            (
                ("Energy (kWh)", b.total_kwh),
                ("Days", b.days),
                *(
                    (
                        (
                            "Effective price per kWh (" + (self._currency or "currency") + ")",
                            b.effective_rate_per_kwh,
                        ),
                    )
                    if b.effective_rate_per_kwh
                    else ()
                ),
            ),
        )
        tables = [summary]
        if b.total is not None:
            rows = tuple((line.label, line.detail, line.amount) for line in b.lines)
            tables.append(
                ReportTable(
                    "Itemised estimate",
                    ("Item", "Basis", self._money("Amount")),
                    (*rows, ("Estimated total", "", b.total)),
                    True,
                )
            )
        params = [("Month", f"{calendar.month_name[month]} {year}"), ("Scope", "Whole household")]
        return "Electricity bill estimate", params, tables, b.notes, True

    def _peak_load(self, p: ReportParams) -> Built:
        a = PeakLoadService(self._session).analysis(p.weekday)
        fmt = self._fmt

        def span(e: WindowRead) -> str:
            return f"{fmt(e.start_minute)}-{fmt(e.end_minute)}"

        summary = ReportTable(
            "Summary (power in kW, not energy in kWh)",
            ("Measure", "Value"),
            (
                ("Day analysed", WEEKDAYS[a.weekday]),
                ("Peak demand, worst case (kW)", a.peak_kw),
                ("Expected peak, using duty cycles (kW)", a.peak_expected_kw),
                ("Household load limit (kW)", a.load_limit_kw),
                ("Headroom (kW)", a.headroom_kw),
                ("Time over the limit (minutes)", a.minutes_over_limit),
                ("Peak at", ", ".join(span(w) for w in a.peak_windows) or "n/a"),
                ("Fixed load at the peak (kW)", a.peak_fixed_kw),
                ("Flexible load at the peak (kW)", a.peak_flexible_kw),
            ),
        )
        hours = ReportTable(
            "Highest demand in each hour",
            ("Hour", "Worst case (kW)", "Expected (kW)"),
            tuple(
                (
                    f"{fmt(h * 60)}-{fmt((h + 1) * 60)}",
                    max(s.worst_kw for s in a.steps[h * 4 : (h + 1) * 4]),
                    max(s.expected_kw for s in a.steps[h * 4 : (h + 1) * 4]),
                )
                for h in range(24)
            ),
        )
        contributors = ReportTable(
            "Appliances running at the peak",
            ("Appliance", "Type", "Power (kW)"),
            tuple((c.name, c.mode.value, c.kw) for c in a.peak_contributors),
        )

        def episodes(title: str, rows: list[EpisodeRead]) -> ReportTable:
            return ReportTable(
                title,
                ("Time", "Highest demand (kW)", "Appliances"),
                tuple((span(e), e.max_kw, ", ".join(x.name for x in e.appliances)) for e in rows),
            )

        week = ReportTable(
            "Peak by weekday",
            ("Day", "Peak (kW)", "Starts", "Minutes over limit"),
            tuple(
                (WEEKDAYS[d.weekday], d.peak_kw, fmt(d.peak_start_minute), d.minutes_over_limit)
                for d in a.week
            ),
        )
        tables = [
            summary,
            hours,
            contributors,
            episodes("Load-limit violations", a.violations),
            episodes("High-demand periods", a.high_demand),
            episodes("Heavy appliances overlapping", a.overlaps),
            episodes("Appliances not allowed together, overlapping", a.conflicts),
            week,
        ]
        return "Peak load report", [("Day", WEEKDAYS[a.weekday])], tables, a.notes, False

    def _optimization(self, p: ReportParams) -> Built:
        service = OptimizationService(self._session)
        run_id = p.run_id
        if run_id is None:
            history = service.history()
            if not history:
                raise ValidationFailedError(
                    "There are no optimization runs yet.",
                    {"run_id": "Run the Smart Scheduler first."},
                )
            run_id = history[0].id
        run: OptimizationRunRead = service.get(run_id)
        fmt, b, o = self._fmt, run.baseline, run.optimized
        currency = self._currency or "currency"

        def pair(label: str, before: Cell, after: Cell) -> tuple[Cell, ...]:
            return (label, before, after if o else None)

        summary = ReportTable(
            "Current schedule and optimized schedule",
            ("Measure", "Current schedule", "Optimized schedule"),
            (
                pair(
                    f"Estimated bill, {run.bill_year}-{run.bill_month:02d} ({currency})",
                    b.monthly_bill,
                    o.monthly_bill if o else None,
                ),
                pair(
                    "Energy charge per typical week",
                    b.weekly_energy_charge,
                    o.weekly_energy_charge if o else None,
                ),
                pair("Peak demand, worst case (kW)", b.peak_kw, o.peak_kw if o else None),
                pair("Expected peak (kW)", b.peak_expected_kw, o.peak_expected_kw if o else None),
                pair(
                    "Minutes over the load limit per week",
                    b.minutes_over_limit,
                    o.minutes_over_limit if o else None,
                ),
                pair(
                    "Overlap of 'not simultaneous' appliances (min/week)",
                    b.conflict_minutes,
                    o.conflict_minutes if o else None,
                ),
                ("Estimated monthly savings (negative = costs more)", None, run.monthly_savings),
                ("Peak reduction (kW)", None, run.peak_reduction_kw),
            ),
        )
        outcome = ReportTable(
            "Solver outcome",
            ("Item", "Value"),
            (
                ("Status", run.status.value),
                ("Proven optimal", "yes" if run.proven_optimal else "no"),
                ("Schedule passed independent validation", "yes" if run.schedule_valid else "no"),
                ("Solve time (ms)", run.solve_time_ms),
                ("Solver", run.solver),
                ("Random seed", run.random_seed),
            ),
        )
        tables = [summary, outcome]
        if run.items:
            tables.append(
                ReportTable(
                    "Recommended schedule",
                    ("Appliance", "Power (kW)", "Usual start", "Recommended", "Reasons"),
                    tuple(
                        (
                            i.name,
                            i.power_kw,
                            fmt(i.baseline_start_minute),
                            f"{fmt(i.start_minute)}-{fmt(i.end_minute)}"
                            if i.moved
                            else "No change",
                            " ".join(r.text for r in i.reasons),
                        )
                        for i in run.items
                    ),
                )
            )
        if run.validation:
            tables.append(
                ReportTable(
                    "Independent validation",
                    ("Check", "Result", "Detail"),
                    tuple(
                        (c.label, "Pass" if c.passed else "FAIL", c.detail) for c in run.validation
                    ),
                )
            )
        if run.diagnostics:
            tables.append(
                ReportTable(
                    "Why no schedule exists",
                    ("Reason",),
                    tuple((d.message,) for d in run.diagnostics),
                )
            )
        params = [
            ("Run", f"#{run.id}, {run.created_at:%Y-%m-%d %H:%M} UTC"),
            ("Goal", run.priority.value),
        ]
        tariff = (
            (("Tariff", run.tariff.name), ("Type", TYPE_LABELS[run.tariff.tariff_type]))
            if run.tariff
            else ()
        )
        report_params = [*params, *tariff]
        return "Optimization comparison report", report_params, tables, run.notes, False

    def _simulation(self, p: ReportParams) -> Built:
        scenarios = [
            s for s in SimulationService(self._session).list_scenarios() if s.latest_result
        ]
        if p.scenario_ids is not None:
            scenarios = [s for s in scenarios if s.id in p.scenario_ids]
        if not scenarios:
            raise ValidationFailedError(
                "No scenario results to report.",
                {"scenario_ids": "Run at least one scenario first."},
            )
        base = scenarios[0].latest_result.baseline  # type: ignore[union-attr]
        results = [s.latest_result for s in scenarios if s.latest_result]
        money = self._currency or "currency"

        def row(label: str, current: Cell, values: list[Cell]) -> tuple[Cell, ...]:
            return (label, current, *values)

        comparison = ReportTable(
            "Per month, against the current household",
            ("Measure", "Current household", *(r.scenario_name for r in results)),
            (
                row(
                    "Estimated energy (kWh)",
                    base.monthly_kwh,
                    [r.scenario.monthly_kwh for r in results],
                ),
                row(
                    f"Estimated bill at usual times ({money})",
                    base.monthly_bill,
                    [r.scenario.monthly_bill for r in results],
                ),
                row(
                    f"Estimated bill after scheduling ({money})",
                    None,
                    [r.optimized.monthly_bill if r.optimized else None for r in results],
                ),
                row(
                    "Bill change at usual times (+ costs more)",
                    None,
                    [r.bill_change for r in results],
                ),
                row(
                    "Bill change after scheduling (+ costs more)",
                    None,
                    [r.optimized_bill_change for r in results],
                ),
                row("Saved by scheduling alone", None, [r.optimization_savings for r in results]),
                row(
                    "Peak demand at usual times (kW)",
                    base.peak_kw,
                    [r.scenario.peak_kw for r in results],
                ),
                row(
                    "Peak demand after scheduling (kW)",
                    None,
                    [r.optimized.peak_kw if r.optimized else None for r in results],
                ),
                row(
                    "Minutes over load limit per week, usual times",
                    base.minutes_over_limit,
                    [r.scenario.minutes_over_limit for r in results],
                ),
                row("Scheduling goal", None, [r.priority.value for r in results]),
                row(
                    "Scheduling result",
                    None,
                    [
                        (r.status.value if r.status else "not attempted")
                        + ("" if r.schedule_valid or not r.status else " (no valid schedule)")
                        for r in results
                    ],
                ),
            ),
        )
        changes = ReportTable(
            "What each scenario changes",
            ("Scenario", "Changes"),
            tuple(
                (r.scenario_name, "; ".join(r.change_descriptions) or "No changes") for r in results
            ),
        )
        month = f"{calendar.month_name[results[0].bill_month]} {results[0].bill_year}"
        notes = [
            results[0].notes[0],
            "Scenarios are calculated on copies of the household; the real data is never changed.",
            "Results reflect the household at the time each scenario was run.",
        ]
        return (
            "Simulation comparison report",
            [("Month", month), ("Scenarios", ", ".join(r.scenario_name for r in results))],
            [comparison, changes],
            notes,
            True,
        )
