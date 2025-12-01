#!/usr/bin/env python3
"""
Insert a test thesis (TEST_T1) into the database for E4 verification.
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from slice.db import get_engine
from slice.repositories.thesis_repo import ThesisRepository
from slice.models.thesis import Thesis, ThesisExpressionLeg
from slice.models.common import Direction, ThesisStatus

def main():
    engine = get_engine()
    repo = ThesisRepository(engine=engine)
    
    thesis = Thesis(
        id="TEST_T1",
        title="Test Gold Long Thesis",
        hypothesis="Gold will appreciate due to inflation hedging demand",
        drivers=["inflation", "currency debasement"],
        disconfirmers=["strong USD", "rising real yields"],
        expression=[
            ThesisExpressionLeg(
                asset="GLD",
                direction=Direction.LONG,
                size_pct=100.0
            )
        ],
        start_date="2024-01-01",
        review_date=None,
        status=ThesisStatus.ACTIVE,
        tags=[],
        monitor_indices=["SPX"]
    )
    
    repo.insert(thesis)
    print(f"✓ Inserted thesis: {thesis.id} - {thesis.title}")
    print(f"  Status: {thesis.status}")
    print(f"  Asset: {thesis.expression[0].asset} ({thesis.expression[0].direction})")

if __name__ == "__main__":
    main()

