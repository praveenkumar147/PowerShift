"""FastAPI dependencies shared by routers."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from powershift.core.config import Settings
from powershift.db.session import session_scope


def get_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def get_session(request: Request) -> Iterator[Session]:
    yield from session_scope(request.app.state.session_factory)


def get_engine(request: Request) -> Engine:
    engine: Engine = request.app.state.engine
    return engine


SettingsDep = Annotated[Settings, Depends(get_settings)]
EngineDep = Annotated[Engine, Depends(get_engine)]
# scope="function": the commit in get_session runs as soon as the endpoint returns, BEFORE the
# response is sent, so a client told "success" can rely on the data being saved, and a failed
# commit becomes a proper error response instead of happening after a 2xx.
SessionDep = Annotated[Session, Depends(get_session, scope="function")]
