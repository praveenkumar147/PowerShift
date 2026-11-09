"""Database access for tariffs, plus conversion between rows and domain specs."""

from __future__ import annotations

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, selectinload

from powershift.db.models import Tariff, TariffCharge, TariffPeriod, TariffSlab
from powershift.domain.tariff import (
    Charge,
    ChargeKind,
    DayType,
    Slab,
    SlabMode,
    TariffSpec,
    TariffType,
    TouPeriod,
)
from powershift.domain.time_window import TimeWindow


class TariffRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list(self) -> list[Tariff]:
        query = (
            select(Tariff)
            .options(
                selectinload(Tariff.periods),
                selectinload(Tariff.slabs),
                selectinload(Tariff.charges),
            )
            .order_by(Tariff.is_active.desc(), func.lower(Tariff.name))
        )
        return list(self._session.scalars(query))

    def get(self, tariff_id: int) -> Tariff | None:
        return self._session.get(Tariff, tariff_id)

    def active(self) -> Tariff | None:
        return self._session.scalar(select(Tariff).where(Tariff.is_active.is_(True)))

    def count(self) -> int:
        return int(self._session.scalar(select(func.count()).select_from(Tariff)) or 0)

    def add(self, spec: TariffSpec) -> Tariff:
        row = Tariff(is_active=False)
        apply_spec(row, spec)
        self._session.add(row)
        self._session.flush()
        return row

    def delete(self, row: Tariff) -> None:
        self._session.delete(row)

    def make_active(self, row: Tariff) -> None:
        # Deactivate everything first and flush, so the "only one active" index
        # never sees two active rows at once.
        self._session.execute(update(Tariff).values(is_active=False))
        self._session.flush()
        self._session.refresh(row)
        row.is_active = True
        self._session.flush()


def to_spec(row: Tariff) -> TariffSpec:
    return TariffSpec(
        name=row.name,
        tariff_type=TariffType(row.tariff_type),
        effective_date=row.effective_date,
        flat_rate_per_kwh=row.flat_rate_per_kwh,
        tou_periods=tuple(
            TouPeriod(TimeWindow(p.start_minute, p.end_minute), DayType(p.day_type), p.rate_per_kwh)
            for p in row.periods
        ),
        slabs=tuple(Slab(s.up_to_kwh, s.rate_per_kwh) for s in row.slabs),
        slab_mode=SlabMode(row.slab_mode),
        charges=tuple(Charge(ChargeKind(c.kind), c.label, c.amount) for c in row.charges),
    )


def apply_spec(row: Tariff, spec: TariffSpec) -> None:
    """Copy a validated spec onto a row. Child lists are replaced as a whole;
    they have no unique constraints, so delete-then-insert is safe."""
    row.name = spec.name
    row.tariff_type = spec.tariff_type.value
    row.effective_date = spec.effective_date
    row.flat_rate_per_kwh = spec.flat_rate_per_kwh
    row.slab_mode = spec.slab_mode.value
    row.periods = [
        TariffPeriod(
            position=i,
            day_type=p.day_type.value,
            start_minute=p.window.start_minute,
            end_minute=p.window.end_minute,
            rate_per_kwh=p.rate_per_kwh,
        )
        for i, p in enumerate(spec.tou_periods)
    ]
    row.slabs = [
        TariffSlab(position=i, up_to_kwh=s.up_to_kwh, rate_per_kwh=s.rate_per_kwh)
        for i, s in enumerate(spec.slabs)
    ]
    row.charges = [
        TariffCharge(position=i, kind=c.kind.value, label=c.label, amount=c.amount)
        for i, c in enumerate(spec.charges)
    ]
