"""
CLI tool for testing Phase 3 LLM layer components.

Usage:
    python scripts/cli/llm_cli.py extract <thesis_id>
    python scripts/cli/llm_cli.py validate <thesis_id>
    python scripts/cli/llm_cli.py critique <thesis_id>
    python scripts/cli/llm_cli.py drill-down <thesis_id> <dimension> <message>
"""
import argparse
import asyncio
import json
import sys
import traceback
from pathlib import Path

# Add src to path so we can import voyager
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

# pylint: disable=wrong-import-position
from voyager.api.deps import (
    get_query_translator_instance,
    get_validation_service_instance,
    get_critique_service_instance,
    get_data_access_instance
)


async def extract_command(thesis_id: str):
    """Test QueryTranslator link extraction"""
    thesis_repo = get_data_access_instance().thesis_repo
    thesis = thesis_repo.get_by_id(thesis_id)

    if thesis is None:
        print(f"Error: Thesis '{thesis_id}' not found", file=sys.stderr)
        sys.exit(1)

    translator = get_query_translator_instance()
    output = await translator.extract_and_resolve(thesis)

    result = {
        "thesis_id": thesis_id,
        "links_extracted": len(output.links),
        "links": [link.model_dump() for link in output.links],
        "resolved": [link.model_dump() for link in output.resolved],
        "ambiguities": [amb.model_dump() for amb in output.ambiguities]
    }

    print(json.dumps(result, indent=2, default=str))


async def validate_command(thesis_id: str):
    """Run full validation flow"""
    thesis_repo = get_data_access_instance().thesis_repo
    thesis = thesis_repo.get_by_id(thesis_id)

    if thesis is None:
        print(f"Error: Thesis '{thesis_id}' not found", file=sys.stderr)
        sys.exit(1)

    validation_service = get_validation_service_instance()
    result = await validation_service.validate(thesis)

    output = {
        "thesis_id": thesis_id,
        "status": result.status,
        "links": [link.model_dump() if link else None for link in (result.links or [])],
        "ambiguities": [amb.model_dump() for amb in (result.ambiguities or [])],
        "error_message": result.error_message
    }

    print(json.dumps(output, indent=2, default=str))


async def critique_command(thesis_id: str):
    """Generate critique summary"""
    critique_service = get_critique_service_instance()

    try:
        summary = await critique_service.start(thesis_id)

        output = {
            "thesis_id": thesis_id,
            "concerns": [concern.model_dump() for concern in summary.concerns],
            "opening_message": summary.opening_message
        }

        print(json.dumps(output, indent=2, default=str))

    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


async def drill_down_command(thesis_id: str, dimension: str, message: str):
    """Test drill-down conversation"""
    critique_service = get_critique_service_instance()

    try:
        response = await critique_service.continue_conversation(
            thesis_id=thesis_id,
            dimension=dimension,
            user_message=message
        )

        output = {
            "thesis_id": thesis_id,
            "dimension": dimension,
            "message": response.message,
            "edit_suggestion": response.thesis_edit_suggestion.model_dump() if response.thesis_edit_suggestion else None
        }

        print(json.dumps(output, indent=2, default=str))

    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    """Parse arguments and dispatch to appropriate command handler."""
    parser = argparse.ArgumentParser(description="Phase 3 LLM Layer CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Extract command
    extract_parser = subparsers.add_parser("extract", help="Extract causal links from thesis")
    extract_parser.add_argument("thesis_id", help="Thesis ID")

    # Validate command
    validate_parser = subparsers.add_parser("validate", help="Run full validation flow")
    validate_parser.add_argument("thesis_id", help="Thesis ID")

    # Critique command
    critique_parser = subparsers.add_parser("critique", help="Generate critique summary")
    critique_parser.add_argument("thesis_id", help="Thesis ID")

    # Drill-down command
    drill_down_parser = subparsers.add_parser("drill-down", help="Continue drill-down conversation")
    drill_down_parser.add_argument("thesis_id", help="Thesis ID")
    drill_down_parser.add_argument("dimension", help="Dimension (e.g., logical_coherence)")
    drill_down_parser.add_argument("message", help="Your message to the critique engine")

    args = parser.parse_args()

    try:
        if args.command == "extract":
            asyncio.run(extract_command(args.thesis_id))
        elif args.command == "validate":
            asyncio.run(validate_command(args.thesis_id))
        elif args.command == "critique":
            asyncio.run(critique_command(args.thesis_id))
        elif args.command == "drill-down":
            asyncio.run(drill_down_command(args.thesis_id, args.dimension, args.message))

    except Exception as e:  # pylint: disable=broad-exception-caught
        print(f"Error: {e}", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
