#!/usr/bin/env python

"""
scripts/memory_ingest_and_recall.py

Usage (after `slice-init`):

  python scripts/memory_ingest_and_recall.py \
    "Fed is concerned about inflation and keeping rates high" \
    --thesis-ref fed_rates \
    --sentiment BEARISH \
    --categories "fed,inflation,rates" \
    -k 3
"""

import argparse
from typing import List, Optional

from slice.memory.api import build_context_for_text


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ingest an observation into Slice memory and recall similar observations."
    )
    parser.add_argument(
        "text",
        help="Observation text to ingest (required).",
    )
    parser.add_argument(
        "--thesis-ref",
        dest="thesis_ref",
        default=None,
        help="Optional thesis_ref to associate with this observation.",
    )
    parser.add_argument(
        "--sentiment",
        default="NEUTRAL",
        help="Sentiment label, e.g. NEUTRAL, BULLISH, BEARISH, etc.",
    )
    parser.add_argument(
        "--categories",
        default=None,
        help='Comma-separated categories, e.g. "fed,inflation,rates".',
    )
    parser.add_argument(
        "-k",
        type=int,
        default=5,
        help="Number of nearest neighbors to retrieve.",
    )
    parser.add_argument(
        "--max-chars",
        type=int,
        default=2000,
        help="Max characters in the returned context block.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    categories: Optional[List[str]] = None
    if args.categories:
        categories = [c.strip() for c in args.categories.split(",") if c.strip()]

    ctx = build_context_for_text(
        text=args.text,
        thesis_ref=args.thesis_ref,
        sentiment=args.sentiment,
        categories=categories,
        k=args.k,
        max_chars=args.max_chars,
    )

    print(f"OK: {ctx.ok}")
    if not ctx.ok:
        print("Errors:")
        for e in ctx.errors:
            print(" -", e)
        return

    print(f"Observation ID: {ctx.observation_id}")
    print("\n--- CONTEXT BLOCK ---")
    print(ctx.context_block or "")

    if ctx.matches:
        print("\n--- MATCHES ---")
        for obs, dist in ctx.matches:
            print(f"{obs.id} | dist={dist:.4f} | {obs.categories} | {obs.sentiment}")
            print("  ", obs.text)


if __name__ == "__main__":
    main()