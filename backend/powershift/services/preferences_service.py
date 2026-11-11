"""App preferences (currently the colour theme), stored in the single `app_settings` row."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from powershift.db.models import AppSettings
from powershift.schemas.data import Preferences, PreferencesUpdate


class PreferencesService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def _row(self) -> AppSettings | None:
        return self._session.scalars(select(AppSettings).limit(1)).first()

    def get(self) -> Preferences:
        """No row yet means nothing was ever chosen: the default is to follow Windows."""
        row = self._row()
        return Preferences(theme=row.theme if row else "system")  # type: ignore[arg-type]

    def update(self, update: PreferencesUpdate) -> Preferences:
        row = self._row()
        if row is None:
            row = AppSettings(theme=update.theme, default_optimization_priority="balanced")
            self._session.add(row)
        else:
            row.theme = update.theme
        self._session.flush()
        return Preferences(theme=update.theme)
