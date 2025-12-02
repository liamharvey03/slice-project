#!/usr/bin/env python3
"""
Insert a test thesis (T1 - Gold vs Real Yields) into the database for E6 UI testing.
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
        id="T1",
        title="Gold vs Real Yields",
        hypothesis="Gold outperforms when real yields decline due to inflation exceeding nominal rate increases. As central banks pause or pivot dovish while inflation remains elevated, real yields compress, making gold attractive relative to bonds.",
        drivers=[
            "Declining real yields (nominal rates - inflation)",
            "Inflation fears / persistent inflation prints above target",
            "Fed dovish pivot or pause in rate hikes",
            "Geopolitical tensions increasing safe-haven demand"
        ],
        disconfirmers=[
            "Real yields rising (Fed aggressive, inflation cooling)",
            "Strong USD (inverse correlation with gold)",
            "Risk-on rally in equities reducing gold safe-haven demand",
            "Fed successfully anchoring inflation expectations"
        ],
        expression=[
            ThesisExpressionLeg(
                asset="GLD",
                direction=Direction.LONG,
                size_pct=100.0
            )
        ],
        start_date="2024-01-01",
        review_date=None,
        status=ThesisStatus.WATCHLIST,
        tags=["gold", "inflation", "macro", "real-yields"],
        monitor_indices=["DXY", "TIP", "CPI", "SPX"],
        notes="Gold vs Inflation thesis for E6 evaluation harness testing"
    )
    
    repo.insert(thesis)
    print(f"✓ Inserted thesis: {thesis.id} - {thesis.title}")
    print(f"  Status: {thesis.status}")
    print(f"  Asset: {thesis.expression[0].asset} ({thesis.expression[0].direction})")

if __name__ == "__main__":
    main()

