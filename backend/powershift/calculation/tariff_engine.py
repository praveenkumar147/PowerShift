"""Turns energy into money according to a tariff.

Bill for one month, in this order:

    1. Energy charge
         flat : total kWh x rate
         TOU  : sum over 15-minute steps of (kWh in step x price at that time)
         slab : telescopic  -> each band's kWh x that band's rate
                whole usage -> all kWh x rate of the band reached
    2. Fixed monthly charges          (amount per month)
    3. Per-kWh charges                (amount x total kWh)
       subtotal = 1 + 2 + 3
    4. Percentage charges / taxes     (percent x subtotal; each applied to the same subtotal)
       total = subtotal + 4

All money is Decimal. Each printed line is rounded to 2 decimal places; the
subtotal is the sum of the rounded lines and percentages apply to that subtotal,
so every number on the bill can be re-checked with a calculator.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from powershift.domain.tariff import ChargeKind, Slab, SlabMode, TariffSpec, TariffType
from powershift.domain.time_window import STEPS_PER_DAY

CENT = Decimal("0.01")
KWH_PRECISION = Decimal("0.000001")
HUNDRED = Decimal(100)


def money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def to_decimal_kwh(kwh: float) -> Decimal:
    """Floats come from the load profile; convert once, at micro-kWh precision."""
    return Decimal(repr(kwh)).quantize(KWH_PRECISION, rounding=ROUND_HALF_UP)


def step_prices(tariff: TariffSpec, weekday: int) -> tuple[Decimal, ...] | None:
    """Price per kWh for each 15-minute step of a weekday; None for slab tariffs,
    where the price depends on the monthly total rather than the time."""
    if tariff.tariff_type is TariffType.FLAT:
        assert tariff.flat_rate_per_kwh is not None  # guaranteed by validate_tariff
        return (tariff.flat_rate_per_kwh,) * STEPS_PER_DAY
    if tariff.tariff_type is TariffType.SLAB:
        return None
    prices: list[Decimal | None] = [None] * STEPS_PER_DAY
    for period in tariff.tou_periods:
        if period.day_type.applies_to(weekday):
            for step in period.window.steps():
                prices[step] = period.rate_per_kwh
    if any(price is None for price in prices):
        raise ValueError("Time-of-use periods do not cover the whole day")
    return tuple(p for p in prices if p is not None)


def kwh_by_price(
    profile_kw: Iterable[float], prices: tuple[Decimal, ...], step_hours: float
) -> dict[Decimal, float]:
    """Groups a day's energy by price, so money is multiplied once per price level."""
    grouped: dict[Decimal, float] = defaultdict(float)
    for kw, price in zip(profile_kw, prices, strict=True):
        if kw:
            grouped[price] += kw * step_hours
    return grouped


def priced_energy_charge(energy_by_price: Mapping[Decimal, float]) -> Decimal:
    return sum((price * to_decimal_kwh(kwh) for price, kwh in energy_by_price.items()), Decimal(0))


@dataclass(frozen=True, slots=True)
class SlabUse:
    from_kwh: Decimal
    to_kwh: Decimal | None
    kwh: Decimal
    rate_per_kwh: Decimal
    amount: Decimal


def slab_charge(
    slabs: tuple[Slab, ...], mode: SlabMode, total_kwh: Decimal
) -> tuple[Decimal, list[SlabUse]]:
    """Energy charge for a monthly total under a slab tariff, with a per-band breakdown."""
    uses: list[SlabUse] = []
    lower = Decimal(0)
    for slab in slabs:
        if total_kwh <= lower:
            break
        upper = slab.up_to_kwh
        in_band = (min(total_kwh, upper) if upper is not None else total_kwh) - lower
        uses.append(SlabUse(lower, upper, in_band, slab.rate_per_kwh, in_band * slab.rate_per_kwh))
        if upper is None:
            break
        lower = upper

    if mode is SlabMode.TELESCOPIC or not uses:
        return sum((u.amount for u in uses), Decimal(0)), uses
    # Whole usage: every kWh at the rate of the highest band reached.
    top_rate = uses[-1].rate_per_kwh
    return total_kwh * top_rate, [
        SlabUse(u.from_kwh, u.to_kwh, u.kwh, top_rate, u.kwh * top_rate) for u in uses
    ]


@dataclass(frozen=True, slots=True)
class BillLine:
    label: str
    kind: str
    """energy | fixed_monthly | per_kwh | percentage"""
    amount: Decimal
    detail: str


@dataclass(frozen=True, slots=True)
class Bill:
    total_kwh: Decimal
    energy_charge: Decimal
    lines: tuple[BillLine, ...]
    subtotal: Decimal
    total: Decimal

    @property
    def effective_rate_per_kwh(self) -> Decimal | None:
        return self.total / self.total_kwh if self.total_kwh else None


def energy_charge_line(tariff: TariffSpec, total_kwh: Decimal, timed_charge: Decimal) -> BillLine:
    """`timed_charge` is the step-by-step charge for flat/TOU; ignored for slab tariffs."""
    if tariff.tariff_type is TariffType.SLAB:
        amount, uses = slab_charge(tariff.slabs, tariff.slab_mode, total_kwh)
        parts = [f"{u.kwh.normalize():f} kWh @ {u.rate_per_kwh.normalize():f}" for u in uses]
        return BillLine("Energy charge", "energy", amount, " + ".join(parts) or "0 kWh")
    if tariff.tariff_type is TariffType.FLAT:
        detail = f"{total_kwh.normalize():f} kWh @ {tariff.flat_rate_per_kwh}"
    else:
        detail = f"{total_kwh.normalize():f} kWh priced by time of use"
    return BillLine("Energy charge", "energy", timed_charge, detail)


def compute_bill(tariff: TariffSpec, total_kwh: Decimal, timed_charge: Decimal) -> Bill:
    energy = energy_charge_line(tariff, total_kwh, timed_charge)
    lines = [energy]

    for charge in tariff.charges:
        if charge.kind is ChargeKind.FIXED_MONTHLY:
            lines.append(BillLine(charge.label, charge.kind.value, charge.amount, "per month"))
        elif charge.kind is ChargeKind.PER_KWH:
            lines.append(
                BillLine(
                    charge.label,
                    charge.kind.value,
                    charge.amount * total_kwh,
                    f"{charge.amount.normalize():f} per kWh",
                )
            )
    # Round each line as it would be printed, so the bill can be checked by hand:
    # the subtotal is the sum of the printed lines, and percentages apply to it.
    lines = [BillLine(line.label, line.kind, money(line.amount), line.detail) for line in lines]
    subtotal = sum((line.amount for line in lines), Decimal(0))

    for charge in tariff.charges:
        if charge.kind is ChargeKind.PERCENTAGE:
            lines.append(
                BillLine(
                    charge.label,
                    charge.kind.value,
                    money(subtotal * charge.amount / HUNDRED),
                    f"{charge.amount.normalize():f}% of subtotal",
                )
            )

    return Bill(
        total_kwh=total_kwh,
        energy_charge=lines[0].amount,
        lines=tuple(lines),
        subtotal=subtotal,
        total=sum((line.amount for line in lines), Decimal(0)),
    )
