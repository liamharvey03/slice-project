# Phase 2 Backtest Engine - Testing Guide

## Prerequisites

Before testing, ensure:

1. **V3 Schema Applied**: The `backtest_result` table must exist
   - Apply using psql: `psql $DATABASE_URL -f sql/v3_schema.sql`
   - Or manually run the SQL statements from `sql/v3_schema.sql`

2. **Market Data Loaded**: Price data must be in `market_data` table
   ```bash
   python scripts/data/backfill_data.py
   ```

## Quick Start

### 1. Ensure Dependencies Installed
```bash
pip install -r scripts/requirements.txt
```

### 2. Run Unit Tests
```bash
pytest tests/v3/test_backtest_engine.py -v
```

Expected: All 11 tests pass

### 3. Test CLI - Direct Expression

Run a backtest on a portfolio expression directly:

```bash
python scripts/cli/backtest_cli.py run '{"GLD": 0.7, "TIP": 0.3}' --start 2020-01-01
```

Expected output:
```
=== Backtest Results ===
Period: 2020-01-02 to 2025-12-04
Total Return: 100.69%
CAGR: 12.50%
Volatility: 12.27%
Sharpe: 0.77
Max Drawdown: 7.09%
Equity Curve Points: 497
```

### 4. Test CLI - Thesis Backtest

First, insert a test thesis:

```bash
python scripts/db/insert_test_thesis.py
```

Then run backtest for that thesis:

```bash
python scripts/cli/backtest_cli.py thesis T1 --start 2020-01-01
```

Expected output includes factor exposure analysis.

## Available Commands

### Run Expression Backtest
```bash
python scripts/cli/backtest_cli.py run '<json_expression>' [--start YYYY-MM-DD] [--end YYYY-MM-DD]
```

### Run Thesis Backtest
```bash
python scripts/cli/backtest_cli.py thesis <thesis_id> [--start YYYY-MM-DD] [--end YYYY-MM-DD]
```

## Troubleshooting

**Error: "No module named 'voyager'"**
- Make sure you're running from project root: `cd /path/to/voyager`
- The script uses `sys.path.insert()` to find src/

**Error: "relation 'backtest_result' does not exist"**
- Apply V3 schema: Run the SQL in `sql/v3_schema.sql` against your database
- Or use psql: `psql $DATABASE_URL -f sql/v3_schema.sql`

**Error: "Thesis not found"**
- Check thesis exists: `SELECT id, title FROM thesis;`
- Insert test thesis: `python scripts/db/insert_test_thesis.py`

**Error: "No price data"**
- Run data backfill: `python scripts/data/backfill_data.py`
- Verify data loaded: `SELECT COUNT(*) FROM market_data WHERE ticker='GLD';`
