#!/usr/bin/env python3

from __future__ import annotations

import sys
from pathlib import Path

# ----- Ensure src/ is on sys.path so `import slice` works -----
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from sqlalchemy import text  # type: ignore

from slice.db import apply_schema, get_engine, ping


def main() -> int:
    # Optional: load .env with python-dotenv if available
    try:
        from dotenv import load_dotenv  # type: ignore

        load_dotenv(dotenv_path=PROJECT_ROOT / ".env")
    except ImportError:
        # Fine if not installed; then you must provide env vars via shell
        pass

    try:
        print("Pinging database...")
        ping()
        print("DB connection OK.")

        print("Applying schema from sql/slice_schema.sql ...")
        apply_schema()
        print("Schema applied successfully.")

        # Quick sanity check: list a few tables
        engine = get_engine()
        with engine.connect() as conn:
            res = conn.execute(
                text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'public' "
                    "ORDER BY table_name LIMIT 5"
                )
            )
            tables = [row[0] for row in res]
        print(f"Visible tables (sample): {tables}")

        return 0

    except Exception as exc:
        print(f"Database initialization FAILED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())