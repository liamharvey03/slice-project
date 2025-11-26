import datetime as dt
import uuid
from typing import List

import pytest

from slice.models.common import Sentiment
from slice.models.observation import Observation
from slice.repositories.observation_repo import ObservationRepository

EMBED_DIM = 1536


def _make_obs(
    obs_id: str,
    thesis_refs: List[str],
    ts: dt.datetime,
    text: str = "obs",
) -> Observation:
    return Observation(
        id=obs_id,
        timestamp=ts,
        text=text,
        thesis_ref=thesis_refs,
        sentiment=Sentiment.NEUTRAL,
        categories=["macro"],
        actionable="",
    )


@pytest.mark.usefixtures("clean_core_tables")
def test_insert_and_get_by_id_roundtrip(db_engine):
    repo = ObservationRepository(engine=db_engine)

    obs_id = str(uuid.uuid4())
    ts = dt.datetime(2025, 1, 1, 12, 0, 0)

    obs = _make_obs(
        obs_id=obs_id,
        thesis_refs=["t1"],
        ts=ts,
        text="FOMC meeting today",
    )

    repo.insert(obs, embedding_vector=[0.0] * EMBED_DIM)

    loaded = repo.get_by_id(obs_id)
    assert loaded is not None
    assert loaded.id == obs.id
    assert loaded.text == obs.text
    assert loaded.sentiment == obs.sentiment
    assert loaded.thesis_ref == obs.thesis_ref
    assert loaded.categories == obs.categories


@pytest.mark.usefixtures("clean_core_tables")
def test_list_for_thesis_filters_by_thesis_ref(db_engine):
    repo = ObservationRepository(engine=db_engine)

    now = dt.datetime(2025, 1, 1, 10, 0, 0)
    o1 = _make_obs(obs_id="o1", thesis_refs=["t1"], ts=now, text="for t1")
    o2 = _make_obs(obs_id="o2", thesis_refs=["t1", "t2"], ts=now, text="for t1 and t2")
    o3 = _make_obs(obs_id="o3", thesis_refs=["t3"], ts=now, text="for t3 only")

    repo.insert(o1, embedding_vector=None)
    repo.insert(o2, embedding_vector=None)
    repo.insert(o3, embedding_vector=None)

    res_t1 = repo.list_for_thesis("t1")
    ids_t1 = {o.id for o in res_t1}
    assert ids_t1 == {"o1", "o2"}

    res_t3 = repo.list_for_thesis("t3")
    ids_t3 = {o.id for o in res_t3}
    assert ids_t3 == {"o3"}


@pytest.mark.usefixtures("clean_core_tables")
def test_list_recent_orders_by_timestamp_desc(db_engine):
    repo = ObservationRepository(engine=db_engine)

    earlier = dt.datetime(2025, 1, 1, 9, 0, 0)
    later = dt.datetime(2025, 1, 1, 12, 0, 0)

    o1 = _make_obs(obs_id="o1", thesis_refs=["t1"], ts=earlier, text="earlier")
    o2 = _make_obs(obs_id="o2", thesis_refs=["t1"], ts=later, text="later")

    repo.insert(o1, embedding_vector=None)
    repo.insert(o2, embedding_vector=None)

    recent = repo.list_recent(limit=10)
    assert [o.id for o in recent] == ["o2", "o1"]