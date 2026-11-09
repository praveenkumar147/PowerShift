"""Runtime configuration for the backend process.

The desktop shell (Tauri) starts the backend with command-line arguments. During
development you can start it by hand with the same arguments. Nothing here reads
from the network or from global machine state other than the arguments given.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

DATABASE_FILENAME = "powershift.db"
LOOPBACK_HOST = "127.0.0.1"
DEFAULT_DEV_DATA_DIR = Path(__file__).resolve().parents[2] / ".data"


@dataclass(frozen=True, slots=True)
class Settings:
    """Immutable settings shared by the whole backend."""

    data_dir: Path
    port: int = 0
    """0 means "let the operating system pick a free port"."""
    token: str | None = None
    """Per-launch secret. When set, every /api request must send it."""
    allowed_origins: tuple[str, ...] = (
        "http://tauri.localhost",  # Tauri v2 on Windows (production)
        "tauri://localhost",  # Tauri on macOS/Linux, kept for completeness
        "http://localhost:1420",  # Vite dev server
    )

    @property
    def database_path(self) -> Path:
        return self.data_dir / DATABASE_FILENAME

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.database_path.as_posix()}"

    @property
    def backups_dir(self) -> Path:
        return self.data_dir / "backups"

    @property
    def logs_dir(self) -> Path:
        return self.data_dir / "logs"

    def ensure_directories(self) -> None:
        for directory in (self.data_dir, self.backups_dir, self.logs_dir):
            directory.mkdir(parents=True, exist_ok=True)


def parse_settings(argv: list[str] | None = None) -> Settings:
    """Build Settings from command-line arguments."""
    parser = argparse.ArgumentParser(prog="powershift-backend")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DEV_DATA_DIR)
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--token", default=None)
    args = parser.parse_args(argv)

    if not 0 <= args.port <= 65535:
        parser.error("--port must be between 0 and 65535")

    return Settings(data_dir=args.data_dir.resolve(), port=args.port, token=args.token or None)
