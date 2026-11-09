"""Energy analysis use cases: build the model from stored data, run it, and
attach the assumptions the user needs to read the numbers correctly."""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from powershift.calculation.energy_model import EnergyModel, PeriodReport, month_bounds
from powershift.calculation.load_profile import build_loads
from powershift.core.errors import ValidationFailedError
from powershift.db.repositories.appliances import ApplianceRepository, to_spec
from powershift.domain.appliance import ApplianceCategory
from powershift.domain.tariff import TariffSpec, TariffType
from powershift.schemas.energy import (
    ApplianceRow,
    BillEstimate,
    BillLineRead,
    CategoryRow,
    DayRow,
    EnergyReport,
    HourlyProfile,
    HourRow,
    MonthlyProjection,
    MonthRow,
    TariffSummary,
    kwh_out,
    money_out,
)
from powershift.services.tariff_service import TariffService

NOTE_ESTIMATE = "Estimates from your appliance settings, not measured consumption."
NOTE_ROUTINE = (
    "Each weekday repeats the same routine; flexible appliances run at their usual start time. "
    "Holidays are not modelled."
)
NOTE_NO_TARIFF = "No active tariff, so costs are not calculated."
NOTE_ENERGY_ONLY = (
    "Costs here are energy charges only; fixed charges and taxes appear in the monthly bill."
)
NOTE_SLAB_SHARE = "Slab tariff: daily and per-appliance costs use each month's average energy rate."
NOTE_TOU_HOURS = "Prices are left blank for hours where the price differs between days."


class EnergyService:
    def __init__(self, session: Session) -> None:
        rows = ApplianceRepository(session).list()
        active = TariffService(session).active_spec()
        self._tariff_id: int | None = active[0] if active else None
        self._tariff: TariffSpec | None = active[1] if active else None
        self._model = EnergyModel(
            build_loads([(row.id, to_spec(row)) for row in rows]), self._tariff
        )

    # --- Endpoints ---------------------------------------------------------------

    def report(self, start: date, end: date, category: ApplianceCategory | None) -> EnergyReport:
        try:
            result = self._model.period_report(start, end, category)
        except ValueError as exc:
            raise ValidationFailedError(str(exc), {"end": str(exc)}) from exc

        notes = [NOTE_ESTIMATE, NOTE_ROUTINE, *self._cost_notes()]
        return EnergyReport(
            start=result.start,
            end=result.end,
            days=result.days,
            total_kwh=kwh_out(result.total_kwh),
            average_daily_kwh=kwh_out(result.total_kwh / result.days),
            energy_charge=money_out(result.energy_charge),
            tariff=self._tariff_summary(),
            daily=[
                DayRow(date=d.day, kwh=kwh_out(d.kwh), energy_charge=money_out(d.energy_charge))
                for d in result.daily
            ],
            appliances=[
                ApplianceRow(
                    appliance_id=a.load.appliance_id,
                    name=a.load.name,
                    category=a.load.category,
                    mode=a.load.mode,
                    kwh=kwh_out(a.kwh),
                    share=_share(a.kwh, result.total_kwh),
                    energy_charge=money_out(a.energy_charge),
                )
                for a in result.appliances
            ],
            categories=_categories(result),
            notes=notes,
        )

    def hourly_profile(
        self, weekday: int | None, category: ApplianceCategory | None
    ) -> HourlyProfile:
        hours = self._model.hourly_profile(weekday, category)
        notes = [NOTE_ESTIMATE, NOTE_ROUTINE]
        if self._tariff is None:
            notes.append(NOTE_NO_TARIFF)
        elif weekday is None and self._tariff.tariff_type is TariffType.TOU:
            notes.append(NOTE_TOU_HOURS)
        return HourlyProfile(
            weekday=weekday,
            hours=[
                HourRow(
                    hour=h.hour,
                    kwh=kwh_out(h.kwh),
                    fixed_kwh=kwh_out(h.fixed_kwh),
                    flexible_kwh=kwh_out(h.flexible_kwh),
                    price_per_kwh=float(h.price_per_kwh) if h.price_per_kwh is not None else None,
                )
                for h in hours
            ],
            tariff=self._tariff_summary(),
            notes=notes,
        )

    def monthly(self, year: int, category: ApplianceCategory | None) -> MonthlyProjection:
        notes = [NOTE_ESTIMATE, NOTE_ROUTINE]
        notes.append(
            NOTE_NO_TARIFF
            if self._tariff is None
            else "Bill totals are for the whole household, including fixed charges and taxes."
        )
        return MonthlyProjection(
            year=year,
            months=[
                MonthRow(
                    month=m.month,
                    days=m.days,
                    kwh=kwh_out(m.kwh),
                    bill_total=money_out(m.bill_total),
                )
                for m in self._model.monthly_projection(year, category)
            ],
            tariff=self._tariff_summary(),
            notes=notes,
        )

    def bill(self, year: int, month: int) -> BillEstimate:
        first, last = month_bounds(year, month)
        bill = self._model.month_bill(year, month)
        notes = [NOTE_ESTIMATE, NOTE_ROUTINE]
        if bill is None:
            notes.append(NOTE_NO_TARIFF)
        else:
            notes.append(
                "Your utility's exact rules (rounding, minimum charges, subsidies) may differ."
            )
        total_kwh = self._model.month_kwh(year, month)
        effective = bill.effective_rate_per_kwh if bill else None
        return BillEstimate(
            year=year,
            month=month,
            days=(last - first).days + 1,
            total_kwh=kwh_out(total_kwh),
            tariff=self._tariff_summary(),
            lines=[
                BillLineRead(
                    label=line.label, kind=line.kind, amount=float(line.amount), detail=line.detail
                )
                for line in (bill.lines if bill else ())
            ],
            subtotal=money_out(bill.subtotal) if bill else None,
            total=money_out(bill.total) if bill else None,
            effective_rate_per_kwh=float(effective.quantize(Decimal("0.0001")))
            if effective
            else None,
            notes=notes,
        )

    # --- Helpers -------------------------------------------------------------------

    def _tariff_summary(self) -> TariffSummary | None:
        tariff: TariffSpec | None = self._tariff
        if tariff is None or self._tariff_id is None:
            return None
        return TariffSummary(id=self._tariff_id, name=tariff.name, tariff_type=tariff.tariff_type)

    def _cost_notes(self) -> list[str]:
        if self._tariff is None:
            return [NOTE_NO_TARIFF]
        notes = [NOTE_ENERGY_ONLY]
        if self._tariff.tariff_type is TariffType.SLAB:
            notes.append(NOTE_SLAB_SHARE)
        return notes


def _share(part: float, total: float) -> float:
    return round(part / total, 4) if total else 0.0


def _categories(result: PeriodReport) -> list[CategoryRow]:
    kwh: dict[ApplianceCategory, float] = defaultdict(float)
    charge: dict[ApplianceCategory, Decimal] = defaultdict(Decimal)
    priced = result.energy_charge is not None
    for a in result.appliances:
        kwh[a.load.category] += a.kwh
        if a.energy_charge is not None:
            charge[a.load.category] += a.energy_charge
    return [
        CategoryRow(
            category=category,
            kwh=kwh_out(value),
            share=_share(value, result.total_kwh),
            energy_charge=money_out(charge[category]) if priced else None,
        )
        for category, value in sorted(kwh.items(), key=lambda item: -item[1])
    ]
