import datetime as dt

import pytest

from voyager.models.thesis import Thesis, ThesisStatus, ThesisExpressionLeg
from voyager.models.common import Direction
from voyager.repositories.thesis_repo import ThesisRepository


@pytest.mark.usefixtures("clean_core_tables")
def test_insert_and_get_by_id_roundtrip(db_engine):
    repo = ThesisRepository(engine=db_engine)

    thesis = Thesis(
        id="t1",
        title="Test thesis",
        hypothesis="Rates will rise on stronger growth.",
        drivers=["growth_up", "inflation_expectations"],
        disconfirmers=["growth_shock_down"],
        expression=[
            ThesisExpressionLeg(
                asset="US2Y",
                direction=Direction.LONG,
                size_pct=1.0,
            )
        ],
        start_date="2025-01-01",
        review_date=None,
        status=ThesisStatus.ACTIVE,
        tags=["test", "rates"],
        monitor_indices=["US2Y"],
        notes="integration test",
    )

    repo.insert(thesis)

    loaded = repo.get_by_id("t1")
    assert loaded is not None
    assert loaded.id == thesis.id
    assert loaded.title == thesis.title
    assert loaded.status == thesis.status
    assert loaded.drivers == thesis.drivers
    assert loaded.tags == thesis.tags


@pytest.mark.usefixtures("clean_core_tables")
def test_get_by_id_nonexistent_returns_none(db_engine):
    repo = ThesisRepository(engine=db_engine)

    loaded = repo.get_by_id("does-not-exist")
    assert loaded is None


@pytest.mark.usefixtures("clean_core_tables")
def test_list_all_returns_all_theses(db_engine):
    repo = ThesisRepository(engine=db_engine)

    t1 = Thesis(
        id="t1",
        title="One",
        hypothesis="h1",
        drivers=["driver1"],
        disconfirmers=["disconfirmer1"],
        expression=[
            ThesisExpressionLeg(
                asset="US2Y",
                direction=Direction.LONG,
                size_pct=1.0,
            )
        ],
        start_date="2025-01-01",
        review_date=None,
        status=ThesisStatus.ACTIVE,
        tags=[],
        monitor_indices=[],
        notes="",
    )
    t2 = Thesis(
        id="t2",
        title="Two",
        hypothesis="h2",
        drivers=["driver2"],
        disconfirmers=["disconfirmer2"],
        expression=[
            ThesisExpressionLeg(
                asset="TLT",
                direction=Direction.SHORT,
                size_pct=2.0,
            )
        ],
        start_date="2025-01-02",
        review_date=None,
        status=ThesisStatus.ACTIVE,
        tags=[],
        monitor_indices=[],
        notes="",
    )

    repo.insert(t1)
    repo.insert(t2)

    all_theses = repo.list_all()
    ids = {t.id for t in all_theses}
    assert ids == {"t1", "t2"}


@pytest.mark.usefixtures("clean_core_tables")
def test_list_recent_orders_by_start_date_desc(db_engine):
    repo = ThesisRepository(engine=db_engine)

    # Older
    t1 = Thesis(
        id="t1",
        title="One",
        hypothesis="h1",
        drivers=["driver1"],
        disconfirmers=["disconfirmer1"],
        expression=[
            ThesisExpressionLeg(
                asset="US2Y",
                direction=Direction.LONG,
                size_pct=1.0,
            )
        ],
        start_date="2025-01-01",
        review_date=None,
        status=ThesisStatus.ACTIVE,
        tags=[],
        monitor_indices=[],
        notes="",
    )
    # Newer
    t2 = Thesis(
        id="t2",
        title="Two",
        hypothesis="h2",
        drivers=["driver2"],
        disconfirmers=["disconfirmer2"],
        expression=[
            ThesisExpressionLeg(
                asset="TLT",
                direction=Direction.SHORT,
                size_pct=2.0,
            )
        ],
        start_date="2025-02-01",
        review_date=None,
        status=ThesisStatus.ACTIVE,
        tags=[],
        monitor_indices=[],
        notes="",
    )

    repo.insert(t1)
    repo.insert(t2)

    recent = repo.list_recent(limit=10)
    assert [t.id for t in recent] == ["t2", "t1"]
