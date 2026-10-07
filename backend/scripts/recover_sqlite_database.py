"""Copy a readable SQLite database away from a stale journal file.

The source is opened in immutable read-only mode. The script refuses to
overwrite an existing target so the original data remains recoverable.
"""

from __future__ import annotations

import argparse
import os
import sqlite3
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = BACKEND_ROOT / "data" / "chat_records.db"


def default_target() -> Path:
    local_app_data = os.getenv("LOCALAPPDATA", "").strip()
    if os.name == "nt" and local_app_data:
        return Path(local_app_data) / "TeachingAssistant" / "data" / "teaching-platform.db"
    return BACKEND_ROOT / "data" / "teaching-platform.db"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--target", type=Path, default=default_target())
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    source_path = args.source.resolve()
    target_path = args.target.resolve()

    if not source_path.is_file():
        raise SystemExit(f"Source database does not exist: {source_path}")
    if target_path.exists():
        raise SystemExit(f"Target database already exists: {target_path}")

    target_path.parent.mkdir(parents=True, exist_ok=True)
    source_uri = f"{source_path.as_uri()}?mode=ro&immutable=1"
    source = sqlite3.connect(source_uri, uri=True)
    try:
        sql_dump = "\n".join(source.iterdump())
    finally:
        source.close()

    target = sqlite3.connect(target_path)
    try:
        target.executescript(sql_dump)
        integrity = target.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise SystemExit(f"Recovered database integrity check failed: {integrity}")
    finally:
        target.close()

    print(f"Recovered database written to: {target_path}")


if __name__ == "__main__":
    main()
