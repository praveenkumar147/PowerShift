"""Backend entry point.

Startup sequence:
1. Parse arguments (data directory, port, token).
2. Create folders and configure logging.
3. Migrate the SQLite database to the latest schema.
4. Bind a socket on 127.0.0.1 (port 0 = OS picks a free one).
5. Print a single READY line with the real port so the desktop shell can read it.
6. Serve requests until the shell stops the process.
"""

from __future__ import annotations

import logging
import socket
import sys

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from powershift import __version__
from powershift.api import health
from powershift.api.security import TOKEN_HEADER, token_middleware
from powershift.core.config import LOOPBACK_HOST, Settings, parse_settings
from powershift.core.errors import register_error_handlers
from powershift.core.logging_setup import configure_logging
from powershift.db.migrate import upgrade_to_head
from powershift.db.session import create_db_engine, create_session_factory

logger = logging.getLogger(__name__)

READY_PREFIX = "POWERSHIFT_READY"


def create_app(settings: Settings) -> FastAPI:
    """Build the FastAPI application. Assumes the database is already migrated."""
    app = FastAPI(
        title="PowerShift API",
        version=__version__,
        docs_url="/docs" if settings.token is None else None,  # no docs in packaged app
        redoc_url=None,
    )
    engine = create_db_engine(settings.database_url)
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = create_session_factory(engine)

    # Middleware added last runs first: CORS must wrap the token check so that
    # even 401 responses carry CORS headers the WebView can read.
    if settings.token is not None:
        app.middleware("http")(token_middleware(settings.token))
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.allowed_origins),
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Content-Type", TOKEN_HEADER],
    )

    register_error_handlers(app)
    app.include_router(health.router)
    return app


def prepare_database(settings: Settings) -> None:
    engine = create_db_engine(settings.database_url)
    try:
        upgrade_to_head(engine, settings.database_path, settings.backups_dir)
    finally:
        engine.dispose()


def bind_socket(port: int) -> socket.socket:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind((LOOPBACK_HOST, port))
    return sock


def main(argv: list[str] | None = None) -> None:
    settings = parse_settings(argv)
    settings.ensure_directories()
    configure_logging(settings.logs_dir)
    logger.info("Starting PowerShift backend %s (data: %s)", __version__, settings.data_dir)

    prepare_database(settings)
    app = create_app(settings)

    sock = bind_socket(settings.port)
    actual_port = sock.getsockname()[1]
    # The desktop shell waits for exactly this line on stdout.
    print(f"{READY_PREFIX} port={actual_port}", flush=True)

    server = uvicorn.Server(uvicorn.Config(app, log_config=None, access_log=False))
    server.run(sockets=[sock])


if __name__ == "__main__":
    main(sys.argv[1:])
