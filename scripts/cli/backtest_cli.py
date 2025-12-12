"""
CLI tool for testing backtests.

Usage:
    # Run backtest on a JSON expression directly
    python scripts/backtest_cli.py run '{"GLD": 0.7, "TIP": 0.3}' --start 2020-01-01
    
    # Run backtest for an existing thesis (replace T1 with your actual thesis ID)
    python scripts/backtest_cli.py thesis T1 --start 2020-01-01
    
    # To create a test thesis first:
    python scripts/insert_test_thesis.py

Examples:
    # 70% GLD, 30% TIP from 2020
    python scripts/backtest_cli.py run '{"GLD": 0.7, "TIP": 0.3}' --start 2020-01-01
    
    # Backtest thesis T1 over full history
    python scripts/backtest_cli.py thesis T1
    
    # Backtest thesis T1 from 2020 to 2023
    python scripts/backtest_cli.py thesis T1 --start 2020-01-01 --end 2023-12-31
"""
import argparse
import json
import sys
from datetime import date
from pathlib import Path

# Add src to path so we can import voyager
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from voyager.api.deps import get_backtest_engine_instance, get_backtest_service_instance


def main():
    parser = argparse.ArgumentParser(description="Backtest CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # Run expression directly
    run_parser = subparsers.add_parser("run", help="Run backtest on expression")
    run_parser.add_argument("expression", help="JSON expression, e.g., '{\"GLD\": 0.7}'")
    run_parser.add_argument("--start", help="Start date (YYYY-MM-DD)")
    run_parser.add_argument("--end", help="End date (YYYY-MM-DD)")
    
    # Run for thesis
    thesis_parser = subparsers.add_parser("thesis", help="Run backtest for thesis")
    thesis_parser.add_argument("thesis_id", help="Thesis ID")
    thesis_parser.add_argument("--start", help="Start date (YYYY-MM-DD)")
    thesis_parser.add_argument("--end", help="End date (YYYY-MM-DD)")
    
    args = parser.parse_args()
    
    if args.command == "run":
        engine = get_backtest_engine_instance()
        expression = json.loads(args.expression)
        
        result = engine.run(
            expression=expression,
            start_date=date.fromisoformat(args.start) if args.start else None,
            end_date=date.fromisoformat(args.end) if args.end else None
        )
        
        print(f"\n=== Backtest Results ===")
        print(f"Period: {result.period_start} to {result.period_end}")
        print(f"Total Return: {result.metrics.total_return:.2%}")
        print(f"CAGR: {result.metrics.cagr:.2%}")
        print(f"Volatility: {result.metrics.volatility:.2%}")
        print(f"Sharpe: {result.metrics.sharpe:.2f}")
        print(f"Max Drawdown: {result.metrics.max_drawdown:.2%}")
        print(f"Equity Curve Points: {len(result.equity_curve)}")
    
    elif args.command == "thesis":
        service = get_backtest_service_instance()
        
        result = service.run(
            thesis_id=args.thesis_id,
            start_date=args.start,
            end_date=args.end
        )
        
        print(f"\n=== Backtest Results for {args.thesis_id} ===")
        print(f"Iteration: #{result.iteration_count}")
        print(f"Period: {result.period_start} to {result.period_end}")
        print(f"Total Return: {result.metrics.total_return:.2%}")
        print(f"CAGR: {result.metrics.cagr:.2%}")
        print(f"Volatility: {result.metrics.volatility:.2%}")
        print(f"Sharpe: {result.metrics.sharpe:.2f}")
        print(f"Max Drawdown: {result.metrics.max_drawdown:.2%}")
        
        if result.factor_exposure:
            print(f"\n=== Factor Exposure ===")
            print(f"R²: {result.factor_exposure.r_squared:.2%}")
            for factor, beta in result.factor_exposure.betas.items():
                print(f"  {factor}: {beta:.3f}")


if __name__ == "__main__":
    main()
