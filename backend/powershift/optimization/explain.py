"""Substep L: explain each recommendation.

Every sentence is generated from a measured difference between the current and
the optimised schedule (prices while running, appliances overlapped, household
demand while running). If a difference does not exist, its sentence is not
produced, so nothing here is invented.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from decimal import Decimal

from powershift.calculation.peak_load import ApplianceDemand, build_demands
from powershift.calculation.tariff_engine import step_prices
from powershift.domain.appliance import ApplianceMode
from powershift.domain.tariff import TariffSpec, TariffType
from powershift.domain.time_window import format_minute
from powershift.optimization.metrics import Appliances, apply_schedule

TimeFormatter = Callable[[int], str]
EPSILON_KW = 1e-6


@dataclass(frozen=True, slots=True)
class Reason:
    code: str
    text: str


def _shared_steps(a: ApplianceDemand, b: ApplianceDemand) -> bool:
    return bool(a.operating_days & b.operating_days) and bool(a.on_steps & b.on_steps)


def _overlapping(
    target: ApplianceDemand, others: Iterable[ApplianceDemand]
) -> dict[int, ApplianceDemand]:
    return {
        o.appliance_id: o
        for o in others
        if o.appliance_id != target.appliance_id and _shared_steps(target, o)
    }


def _peak_while_running(target: ApplianceDemand, everyone: Iterable[ApplianceDemand]) -> float:
    """Highest household worst-case demand in any step and day the appliance runs."""
    everyone = list(everyone)
    return max(
        (
            sum(d.max_kw for d in everyone if d.is_on(day, step))
            for day in target.operating_days
            for step in target.on_steps
        ),
        default=0.0,
    )


def _average_price(target: ApplianceDemand, tariff: TariffSpec) -> Decimal:
    prices = [
        day_prices[step]
        for day in sorted(target.operating_days)
        if (day_prices := step_prices(tariff, day)) is not None
        for step in target.on_steps
    ]
    return sum(prices, Decimal(0)) / len(prices) if prices else Decimal(0)


def _names(demands: Iterable[ApplianceDemand]) -> str:
    return ", ".join(sorted(d.name for d in demands))


def explain(
    appliances: Appliances,
    new_starts: Mapping[int, int],
    tariff: TariffSpec | None,
    limit_kw: float | None,
    proven_optimal: bool,
    fmt: TimeFormatter = format_minute,
) -> dict[int, list[Reason]]:
    before = {d.appliance_id: d for d in build_demands(appliances)}
    after = {d.appliance_id: d for d in build_demands(apply_schedule(appliances, new_starts))}
    result: dict[int, list[Reason]] = {}

    for appliance_id, spec in appliances:
        flex = spec.flexible
        if (
            spec.mode is not ApplianceMode.FLEXIBLE
            or flex is None
            or appliance_id not in new_starts
        ):
            continue
        old, new = before[appliance_id], after[appliance_id]
        reasons: list[Reason] = []

        if new_starts[appliance_id] == flex.current_start_minute:
            text = "Kept at its usual time."
            if proven_optimal:
                text += " No other start time gives a better result for the chosen goal."
            result[appliance_id] = [Reason("unchanged", text)]
            continue

        # Price while running (only time-of-use prices change with the time of day).
        if tariff is not None and tariff.tariff_type is TariffType.TOU:
            price_old, price_new = _average_price(old, tariff), _average_price(new, tariff)
            if price_new < price_old:
                reasons.append(
                    Reason(
                        "cheaper_time",
                        f"Runs when electricity is cheaper: average price while running {price_old:.2f} → {price_new:.2f} per kWh.",
                    )
                )
            elif price_new > price_old:
                reasons.append(
                    Reason(
                        "costlier_time",
                        f"Runs at a higher average price ({price_old:.2f} → {price_new:.2f} per kWh); "
                        "this was needed to meet the constraints or the chosen goal.",
                    )
                )

        # Overlaps with appliances it must not run with.
        overlap_old, overlap_new = (
            _overlapping(old, before.values()),
            _overlapping(new, after.values()),
        )
        separated = (
            []
            if spec.allow_simultaneous
            else [
                d
                for i, d in overlap_old.items()
                if not d.allow_simultaneous and i not in overlap_new
            ]
        )
        if separated:
            reasons.append(
                Reason(
                    "separated",
                    f"No longer overlaps with {_names(separated)}, which you marked as not running at the same time.",
                )
            )
        # Overlaps with other heavy appliances (not already mentioned above).
        mentioned = {d.appliance_id for d in separated}
        heavy_gone = [
            d
            for i, d in overlap_old.items()
            if d.is_heavy and i not in overlap_new and i not in mentioned
        ]
        if heavy_gone and old.is_heavy:
            reasons.append(
                Reason(
                    "avoids_overlap", f"No longer runs at the same time as {_names(heavy_gone)}."
                )
            )
        heavy_new = [d for i, d in overlap_new.items() if d.is_heavy and i not in overlap_old]
        if heavy_new and new.is_heavy:
            reasons.append(
                Reason("new_overlap", f"Now runs at the same time as {_names(heavy_new)}.")
            )

        # Household demand while it runs.
        peak_old = _peak_while_running(old, before.values())
        peak_new = _peak_while_running(new, after.values())
        if limit_kw is not None and peak_old > limit_kw + EPSILON_KW >= peak_new:
            reasons.append(
                Reason(
                    "limit_respected",
                    f"At its usual time the household reached {peak_old:.2f} kW, above your {limit_kw:g} kW limit; "
                    f"now the highest demand while it runs is {peak_new:.2f} kW.",
                )
            )
        elif peak_new < peak_old - EPSILON_KW:
            reasons.append(
                Reason(
                    "lower_demand",
                    f"Highest household demand while it runs falls from {peak_old:.2f} to {peak_new:.2f} kW.",
                )
            )
        elif peak_new > peak_old + EPSILON_KW:
            reasons.append(
                Reason(
                    "higher_demand",
                    f"Highest household demand while it runs rises from {peak_old:.2f} to {peak_new:.2f} kW.",
                )
            )

        # Preferred window.
        preferred = flex.preferred_window
        if preferred is not None:
            span = f"{fmt(preferred.start_minute)}-{fmt(preferred.end_minute)}"
            if preferred.fits(new_starts[appliance_id], flex.run_duration_minutes):
                reasons.append(
                    Reason("preferred_kept", f"Stays inside your preferred window {span}.")
                )
            else:
                reasons.append(
                    Reason("outside_preferred", f"Runs outside your preferred window {span}.")
                )

        if not reasons:
            reasons.append(
                Reason(
                    "tie_break",
                    "Moved as part of the best overall schedule; its own price and demand are unchanged.",
                )
            )
        result[appliance_id] = reasons
    return result
