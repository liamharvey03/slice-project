# src/slice/db.py

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, List

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from .config import load_settings


_ENGINE: Optional[Engine] = None


def get_engine(db_url: Optional[str] = None) -> Engine:
    """
    Return a singleton SQLAlchemy engine for the Slice database.

    If db_url is provided, it is used on first initialization; subsequent calls
    reuse the existing engine.
    """
    global _ENGINE
    if _ENGINE is None:
        url = db_url or load_settings().db.url
        _ENGINE = create_engine(
            url,
            future=True,
            pool_pre_ping=True,
        )
    return _ENGINE


def _default_schema_path() -> Path:
    """
    Locate sql/slice_schema.sql relative to this file.
    Assumes project root layout:

      project_root/
        sql/slice_schema.sql
        src/slice/db.py
    """
    # db.py → slice → src → project_root
    project_root = Path(__file__).resolve().parents[2]
    return project_root / "sql" / "slice_schema.sql"


def _split_sql_statements(sql_text: str) -> list[str]:
    """
    Remove comment-only lines and split the remaining SQL into statements.

    This avoids trying to execute chunks that are just:
      -- comment...
    which Postgres treats as empty queries.
    """
    # Drop comment and blank lines
    lines: list[str] = []
    for line in sql_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("--"):
            continue
        lines.append(line)

    clean_sql = "\n".join(lines).strip()
    if not clean_sql:
        return []

    parts = clean_sql.split(";")
    return [part.strip() for part in parts if part.strip()]


def apply_schema(schema_path: Optional[Path] = None) -> None:
    """
    Apply the core database schema from slice_schema.sql.

    Expects the SQL file to contain DDL (CREATE TABLE, CREATE INDEX, etc.).
    """
    if schema_path is None:
        schema_path = _default_schema_path()

    if not schema_path.exists():
        raise FileNotFoundError(f"Schema file not found: {schema_path}")

    sql_text = schema_path.read_text(encoding="utf-8")

    engine = get_engine()
    with engine.begin() as conn:
        for stmt in _split_sql_statements(sql_text):
            conn.execute(text(stmt))


def ping() -> None:
    """
    Simple connectivity check. Raises if the DB is unreachable.
    """
    engine = get_engine()
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))


def get_last_market_date(engine, ticker: str):
    sql = """
        SELECT MAX(date) 
        FROM market_data 
        WHERE ticker = :ticker
    """
    with engine.connect() as conn:
        result = conn.execute(text(sql), {"ticker": ticker}).scalar()
    return result  # could be None if empty


def get_last_macro_date(engine, series_id: str):
    sql = """
        SELECT MAX(date)
        FROM econ_data
        WHERE series_id = :sid
    """
    with engine.connect() as conn:
        result = conn.execute(text(sql), {"sid": series_id}).scalar()
    return result

def apply_phase4_schema() -> None:
    """
    Apply the Phase 4 schema for thesis/observation/trade/scenario.

    This reads sql/phase4_schema.sql and executes it statement-by-statement,
    using the same splitting/clean execution method as apply_schema().
    """
    # Determine path relative to project root
    project_root = Path(__file__).resolve().parents[2]
    schema_path = project_root / "sql" / "phase4_schema.sql"

    if not schema_path.exists():
        raise FileNotFoundError(f"Phase 4 schema file not found: {schema_path}")

    sql_text = schema_path.read_text(encoding="utf-8")
    stmts = _split_sql_statements(sql_text)

    engine = get_engine()
    with engine.begin() as conn:
        for stmt in stmts:
            conn.execute(text(stmt))