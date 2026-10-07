"""Create a consistent SQLite backup for the teaching platform."""

from __future__ import annotations

import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))
load_dotenv(BACKEND_ROOT / ".env")

from app.database import get_database_path  # noqa: E402


def main() -> None:
    source_path = get_database_path()
    if not source_path.is_file():
        raise SystemExit(f"Database does not exist: {source_path}")

    backup_root = Path(
        os.getenv("BACKUP_DIR", str(source_path.parent / "backups"))
    )
    backup_root.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target_path = backup_root / f"teaching-platform-{timestamp}.db"

    source = sqlite3.connect(source_path)
    target = sqlite3.connect(target_path)
    try:
        source.backup(target)
        integrity = target.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise SystemExit(f"Backup integrity check failed: {integrity}")
    finally:
        target.close()
        source.close()

    print(f"Backup written to: {target_path}")


if __name__ == "__main__":
    main()
