"""
CLI tool for testing quant queries.

Usage:
    python scripts/quant_cli.py correlation DFII10 GLD --period 5Y
    python scripts/quant_cli.py conditional GLD DFII10 ">" 2.0
    python scripts/quant_cli.py distribution DFII10
    python scripts/quant_cli.py relationship DFII10 GLD negative --period 5Y
"""
import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

# Add src to path so we can import voyager
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from voyager.api.deps import get_quant_service_instance


def main():
    parser = argparse.ArgumentParser(description="Quant Service CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # Correlation command
    corr_parser = subparsers.add_parser("correlation", help="Compute correlation")
    corr_parser.add_argument("series_a", help="First series ID")
    corr_parser.add_argument("series_b", help="Second series ID")
    corr_parser.add_argument("--period", default="5Y", help="Time period (default: 5Y)")
    corr_parser.add_argument("--no-returns", action="store_true", help="Use levels instead of returns")
    
    # Conditional returns command
    cond_parser = subparsers.add_parser("conditional", help="Compute conditional returns")
    cond_parser.add_argument("asset", help="Asset ID")
    cond_parser.add_argument("condition_series", help="Condition series ID")
    cond_parser.add_argument("operator", choices=[">", "<", ">=", "<="], help="Comparison operator")
    cond_parser.add_argument("value", type=float, help="Condition threshold")
    cond_parser.add_argument("--period", default="5Y", help="Time period (default: 5Y)")
    
    # Distribution command
    dist_parser = subparsers.add_parser("distribution", help="Get distribution stats")
    dist_parser.add_argument("series", help="Series ID")
    dist_parser.add_argument("--period", default="10Y", help="Time period (default: 10Y)")
    dist_parser.add_argument("--on", choices=["levels", "returns"], default="levels", help="Compute on levels or returns (default: levels)")
    
    # Relationship command
    rel_parser = subparsers.add_parser("relationship", help="Evaluate relationship strength")
    rel_parser.add_argument("series_a", help="First series ID")
    rel_parser.add_argument("series_b", help="Second series ID")
    rel_parser.add_argument("direction", choices=["positive", "negative"], help="Expected direction")
    rel_parser.add_argument("--period", default="5Y", help="Time period (default: 5Y)")
    
    args = parser.parse_args()
    
    try:
        quant = get_quant_service_instance()
        
        if args.command == "correlation":
            result = quant.correlation(
                args.series_a, 
                args.series_b, 
                args.period,
                use_returns=not args.no_returns
            )
            print(json.dumps(asdict(result), indent=2, default=str))
        
        elif args.command == "conditional":
            result = quant.conditional_returns(
                args.asset, 
                args.condition_series, 
                args.operator, 
                args.value, 
                args.period
            )
            print(json.dumps(asdict(result), indent=2, default=str))
        
        elif args.command == "distribution":
            result = quant.distribution(args.series, args.period, on=args.on)
            print(json.dumps(asdict(result), indent=2, default=str))
        
        elif args.command == "relationship":
            result = quant.relationship_strength(
                args.series_a, 
                args.series_b, 
                args.direction, 
                args.period
            )
            print(json.dumps(asdict(result), indent=2, default=str))
    
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
