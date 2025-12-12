"""
CLI tool for testing sizing calculations.

Usage:
    python scripts/cli/sizing_cli.py list [--status STATUS]
    python scripts/cli/sizing_cli.py compute <thesis_id> --max-dd 0.08 --cap 0.10 [--no-portfolio]
"""
import argparse
import sys
import traceback
from pathlib import Path
from typing import Optional

# Add src to path so we can import voyager
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

# pylint: disable=wrong-import-position
from voyager.api.deps import (
    get_sizing_service_instance,
    get_backtest_service_instance,
    get_thesis_service_instance,
    get_data_access_instance
)
from voyager.models.thesis import RiskRails


def compute_command(thesis_id: str, max_dd: float, cap: float, no_portfolio: bool):
    """Compute sizing for a thesis"""
    sizing_service = get_sizing_service_instance()
    backtest_service = get_backtest_service_instance()
    thesis_service = get_thesis_service_instance()

    # Load thesis and backtest
    thesis = thesis_service.get(thesis_id)
    if thesis is None:
        print(f"Thesis not found: {thesis_id}", file=sys.stderr)
        sys.exit(1)

    backtest = backtest_service.get_latest(thesis_id)
    if backtest is None:
        print("No backtest found for thesis. Run backtest first.", file=sys.stderr)
        sys.exit(1)

    rails = RiskRails(
        max_dd_tolerance=max_dd,
        position_cap=cap
    )

    try:
        result = sizing_service.compute(
            thesis=thesis,
            rails=rails,
            backtest=backtest,
            include_portfolio_impact=not no_portfolio
        )

        print(f"\n=== Sizing Results ===")
        print(f"Historical Max DD: {result.historical_max_dd:.2%}")
        print(f"Your Tolerance: {result.tolerance:.2%}")
        print(f"Implied Size: {result.implied_size:.2%}")
        print(f"Position Cap: {result.position_cap:.2%}")
        print(f"Suggested Size: {result.suggested_size:.2%}")

        if result.portfolio_impact:
            print(f"\n=== Portfolio Impact ===")
            print(f"Correlation to Book: {result.portfolio_impact.correlation_to_book:.2f}")
            print(f"Marginal Vol: {result.portfolio_impact.marginal_vol:+.2%}")
        elif not no_portfolio:
            print(f"\n=== Portfolio Impact ===")
            print("No portfolio impact calculated (empty portfolio or insufficient data)")

    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:  # pylint: disable=broad-exception-caught
        print(f"Unexpected error: {e}", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)


def list_command(status_filter: Optional[str]):
    """List theses with available backtests"""
    thesis_service = get_thesis_service_instance()
    backtest_service = get_backtest_service_instance()

    # Get theses
    if status_filter:
        theses = thesis_service.list_by_status(status_filter)
    else:
        # Get all theses
        data_access = get_data_access_instance()
        theses = data_access.thesis_repo.list_all()

    # Filter to only those with backtests
    theses_with_backtests = []
    for thesis in theses:
        backtest = backtest_service.get_latest(thesis.id)
        if backtest:
            theses_with_backtests.append((thesis, backtest))

    if not theses_with_backtests:
        print("No theses with backtests found.")
        if status_filter:
            print(f"(Filtered by status: {status_filter})")
        return

    print(f"\n=== Available Theses ({len(theses_with_backtests)}) ===\n")
    for thesis, backtest in theses_with_backtests:
        status_str = thesis.status.value if hasattr(thesis.status, 'value') else str(thesis.status)
        print(f"ID: {thesis.id}")
        print(f"  Title: {thesis.title}")
        print(f"  Status: {status_str}")
        print(f"  Max DD: {backtest.metrics.max_drawdown:.2%}")
        print()


def main():
    parser = argparse.ArgumentParser(description="Sizing CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Compute sizing
    compute_parser = subparsers.add_parser("compute", help="Compute sizing for thesis")
    compute_parser.add_argument("thesis_id", help="Thesis ID")
    compute_parser.add_argument("--max-dd", type=float, required=True, help="Max DD tolerance (e.g., 0.08)")
    compute_parser.add_argument("--cap", type=float, required=True, help="Position cap (e.g., 0.10)")
    compute_parser.add_argument("--no-portfolio", action="store_true", help="Skip portfolio impact")

    # List theses
    list_parser = subparsers.add_parser("list", help="List theses with backtests")
    list_parser.add_argument("--status", type=str, help="Filter by status (e.g., BACKTESTED, ACTIVE)")

    args = parser.parse_args()

    if args.command == "compute":
        compute_command(args.thesis_id, args.max_dd, args.cap, args.no_portfolio)
    elif args.command == "list":
        list_command(args.status if hasattr(args, 'status') else None)


if __name__ == "__main__":
    main()
