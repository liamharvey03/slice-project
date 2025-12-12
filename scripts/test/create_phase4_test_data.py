"""
Create test data for Phase 4 testing.

Creates a test thesis with backtest so the sizing CLI can be tested.

Usage:
    python scripts/test/create_phase4_test_data.py
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

# pylint: disable=wrong-import-position
from voyager.api.deps import (
    get_thesis_service_instance,
    get_backtest_service_instance
)
from voyager.models.v3 import ThesisDraftInput


def create_test_thesis_with_backtest():
    """Create a test thesis with backtest"""
    thesis_svc = get_thesis_service_instance()
    backtest_svc = get_backtest_service_instance()

    # Create thesis
    draft = ThesisDraftInput(
        title="Test Gold vs Real Yields",
        hypothesis="Rising real yields pressure gold prices",
        drivers=["Fed tightening", "Strong dollar"],
        disconfirmers=["Flight to safety", "Inflation fears"],
        expression=[{"asset": "GLD", "direction": "LONG", "size_pct": 100.0}]
    )

    thesis = thesis_svc.create_draft(draft)
    print(f"Created thesis: {thesis.id}")

    # Run backtest
    try:
        backtest = backtest_svc.run(
            thesis_id=thesis.id,
            start_date="2020-01-01",
            end_date="2023-12-31",
            include_factor_exposure=False
        )
        print(f"Backtest completed:")
        print(f"  Max DD: {backtest.metrics.max_drawdown:.2%}")
        print(f"  Sharpe: {backtest.metrics.sharpe:.2f}")
        print(f"  CAGR: {backtest.metrics.cagr:.2%}")

        # Transition to BACKTESTED status
        thesis_svc.transition_status(thesis.id, "VALIDATED")
        thesis_svc.transition_status(thesis.id, "CRITIQUED")
        thesis_svc.transition_status(thesis.id, "BACKTESTED")

        print(f"\nThesis ready for sizing test:")
        print(f"  ID: {thesis.id}")
        print(f"  Status: BACKTESTED")

        return thesis.id

    except Exception as e:
        print(f"Error creating backtest: {e}")
        import traceback
        traceback.print_exc()
        print("\nNote: Make sure you have market data loaded for GLD.")
        print("Run data loading scripts if needed.")
        return None


if __name__ == "__main__":
    print("Creating Phase 4 test data...\n")
    thesis_id = create_test_thesis_with_backtest()
    if thesis_id:
        print(f"\n{'='*60}")
        print("Test data created successfully!")
        print(f"{'='*60}")
        print(f"\nNow you can test sizing:")
        print(f"  python scripts/cli/sizing_cli.py list")
        print(f"  python scripts/cli/sizing_cli.py list --status BACKTESTED")
        print(f"  python scripts/cli/sizing_cli.py compute {thesis_id} --max-dd 0.08 --cap 0.10")
    else:
        print("\nFailed to create test data. Check error messages above.")
