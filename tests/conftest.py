import sys
from pathlib import Path
import pytest
from sqlalchemy import text

from slice.db import get_engine, apply_phase4_schema

# Directory containing both "src" and "tests"
ROOT = Path(__file__).resolve().parent.parent

root_str = str(ROOT)
if root_str not in sys.path:
    sys.path.insert(0, root_str)


@pytest.fixture(scope="session")
def db_engine():
    """
    Session-wide database engine for integration tests.

    Uses the configured SLICE_DB_URL via get_engine() and applies the core schema
    once at the beginning of the test session.
    """
    engine = get_engine()
    # Ensure core tables (thesis, observation, trade, etc.) exist.
    apply_phase4_schema()
    return engine


@pytest.fixture(autouse=False)
def clean_core_tables(db_engine):
    """
    Clean core tables before each test that opts into DB-backed repos.

    This fixture can be explicitly requested by tests that perform DB writes,
    so we don't accidentally truncate tables for pure unit tests.
    """
    # Pre-test cleanup
    with db_engine.begin() as conn:
        conn.execute(text("TRUNCATE thesis RESTART IDENTITY CASCADE"))
        conn.execute(text("TRUNCATE observation RESTART IDENTITY CASCADE"))
        conn.execute(text("TRUNCATE trade RESTART IDENTITY CASCADE"))
    yield
    # Optional post-test cleanup (can be the same as pre-test)
    with db_engine.begin() as conn:
        conn.execute(text("TRUNCATE thesis RESTART IDENTITY CASCADE"))
        conn.execute(text("TRUNCATE observation RESTART IDENTITY CASCADE"))
        conn.execute(text("TRUNCATE trade RESTART IDENTITY CASCADE"))
