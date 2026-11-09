"""Database access for appliances, plus conversion between rows and domain specs."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from powershift.db.models import (
    Appliance,
    ApplianceFlexConstraint,
    ApplianceOperatingDay,
    ApplianceUsageBlock,
)
from powershift.domain.appliance import (
    ApplianceCategory,
    ApplianceMode,
    ApplianceSpec,
    FlexibleSchedule,
    Priority,
)
from powershift.domain.time_window import TimeWindow


class ApplianceRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list(
        self,
        search: str | None = None,
        category: ApplianceCategory | None = None,
        mode: ApplianceMode | None = None,
    ) -> list[Appliance]:
        query = (
            select(Appliance)
            .options(
                selectinload(Appliance.operating_days),
                selectinload(Appliance.usage_blocks),
                selectinload(Appliance.flex_constraint),
            )
            .order_by(func.lower(Appliance.name))
        )
        if search:
            query = query.where(Appliance.name.icontains(search, autoescape=True))
        if category is not None:
            query = query.where(Appliance.category == category.value)
        if mode is not None:
            query = query.where(Appliance.mode == mode.value)
        return list(self._session.scalars(query))

    def get(self, appliance_id: int) -> Appliance | None:
        return self._session.get(Appliance, appliance_id)

    def name_taken(self, name: str, exclude_id: int | None = None) -> bool:
        query = select(Appliance.id).where(func.lower(Appliance.name) == name.lower())
        if exclude_id is not None:
            query = query.where(Appliance.id != exclude_id)
        return self._session.scalar(query) is not None

    def add(self, spec: ApplianceSpec) -> Appliance:
        row = Appliance()
        apply_spec(row, spec)
        self._session.add(row)
        self._session.flush()  # assigns row.id
        return row

    def delete(self, row: Appliance) -> None:
        self._session.delete(row)


def to_spec(row: Appliance) -> ApplianceSpec:
    flex = row.flex_constraint
    return ApplianceSpec(
        name=row.name,
        category=ApplianceCategory(row.category),
        rated_power_w=row.rated_power_w,
        quantity=row.quantity,
        duty_cycle=row.duty_cycle,
        mode=ApplianceMode(row.mode),
        priority=Priority(row.priority),
        allow_simultaneous=row.allow_simultaneous,
        operating_days=tuple(day.weekday for day in row.operating_days),
        fixed_blocks=tuple(TimeWindow(b.start_minute, b.end_minute) for b in row.usage_blocks),
        flexible=_flex_to_schedule(flex) if flex is not None else None,
    )


def _flex_to_schedule(flex: ApplianceFlexConstraint) -> FlexibleSchedule:
    preferred = None
    if flex.preferred_start_minute is not None and flex.preferred_end_minute is not None:
        preferred = TimeWindow(flex.preferred_start_minute, flex.preferred_end_minute)
    return FlexibleSchedule(
        run_duration_minutes=flex.run_duration_minutes,
        allowed_window=TimeWindow(flex.earliest_start_minute, flex.latest_end_minute),
        current_start_minute=flex.current_start_minute,
        preferred_window=preferred,
        must_be_contiguous=flex.must_be_contiguous,
    )


def apply_spec(row: Appliance, spec: ApplianceSpec) -> None:
    """Copy a validated spec onto a row (used for both create and update)."""
    row.name = spec.name
    row.category = spec.category.value
    row.rated_power_w = spec.rated_power_w
    row.quantity = spec.quantity
    row.duty_cycle = spec.duty_cycle
    row.mode = spec.mode.value
    row.priority = spec.priority.value
    row.allow_simultaneous = spec.allow_simultaneous
    _sync_operating_days(row, spec.operating_days)
    row.usage_blocks = [
        ApplianceUsageBlock(start_minute=w.start_minute, end_minute=w.end_minute)
        for w in spec.fixed_blocks
    ]
    _sync_flex_constraint(row, spec.flexible)


def _sync_operating_days(row: Appliance, weekdays: tuple[int, ...]) -> None:
    # Update by difference rather than delete-all-then-insert: re-inserting the same
    # weekday before the old row is deleted would break the (appliance, weekday)
    # unique constraint inside a single flush.
    wanted = set(weekdays)
    row.operating_days = [day for day in row.operating_days if day.weekday in wanted]
    existing = {day.weekday for day in row.operating_days}
    row.operating_days.extend(ApplianceOperatingDay(weekday=w) for w in sorted(wanted - existing))


def _sync_flex_constraint(row: Appliance, flex: FlexibleSchedule | None) -> None:
    if flex is None:
        row.flex_constraint = None
        return
    # Update in place: the constraint's primary key IS the appliance id, so
    # replacing the object would try to insert a duplicate key.
    target = row.flex_constraint or ApplianceFlexConstraint()
    preferred = flex.preferred_window
    target.run_duration_minutes = flex.run_duration_minutes
    target.earliest_start_minute = flex.allowed_window.start_minute
    target.latest_end_minute = flex.allowed_window.end_minute
    target.current_start_minute = flex.current_start_minute
    target.preferred_start_minute = preferred.start_minute if preferred else None
    target.preferred_end_minute = preferred.end_minute if preferred else None
    target.must_be_contiguous = flex.must_be_contiguous
    row.flex_constraint = target
