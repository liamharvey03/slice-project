import pytest

from slice.intelligence.context.context_builder import ContextBuilder


class StubThesis:
    def __init__(self, thesis_id: int):
        self.thesis_id = thesis_id

    def dict(self):
        return {"thesis_id": self.thesis_id, "stub": True}


class StubObservation:
    def __init__(self, obs_id: int, thesis_id: int | None = None):
        self.obs_id = obs_id
        self.thesis_id = thesis_id

    def dict(self):
        return {
            "observation_id": self.obs_id,
            "thesis_id": self.thesis_id,
            "stub": True,
        }


class StubRiskSnapshot:
    def __init__(self, label: str):
        self.label = label

    def dict(self):
        return {"snapshot_label": self.label, "stub": True}


class DummyDataAccess:
    """
    Minimal stand-in for DataAccess.

    We avoid importing real repositories or models here and instead
    just return stub objects with .dict() to verify ContextBuilder's
    behavior and output shape.
    """

    def __init__(
        self,
        thesis: StubThesis | None = None,
        theses: list[StubThesis] | None = None,
        observations_for_thesis: list[StubObservation] | None = None,
        recent_observations: list[StubObservation] | None = None,
        risk_snapshot: StubRiskSnapshot | None = None,
    ):
        self._thesis = thesis
        self._theses = theses or []
        self._obs_for_thesis = observations_for_thesis or []
        self._recent_obs = recent_observations or []
        self._risk = risk_snapshot

        # call counters (optional, but nice to have)
        self.calls = {
            "get_thesis": 0,
            "get_all_theses": 0,
            "get_observations_for_thesis": 0,
            "get_recent_observations": 0,
            "get_risk_snapshot": 0,
        }

    def get_thesis(self, thesis_id: int):
        self.calls["get_thesis"] += 1
        return self._thesis

    def get_all_theses(self):
        self.calls["get_all_theses"] += 1
        return self._theses

    def get_observations_for_thesis(self, thesis_id: int):
        self.calls["get_observations_for_thesis"] += 1
        return self._obs_for_thesis

    def get_recent_observations(self, limit: int = 10):
        self.calls["get_recent_observations"] += 1
        # ignore limit; this is just a stub
        return self._recent_obs

    def get_risk_snapshot(self):
        self.calls["get_risk_snapshot"] += 1
        return self._risk


def test_build_thesis_context_success():
    thesis = StubThesis(thesis_id=1)
    observations = [StubObservation(1, thesis_id=1), StubObservation(2, thesis_id=1)]
    risk = StubRiskSnapshot("test-snapshot")

    data_access = DummyDataAccess(
        thesis=thesis,
        observations_for_thesis=observations,
        risk_snapshot=risk,
    )
    builder = ContextBuilder(data_access)

    ctx = builder.build_thesis_context(thesis_id=1)

    assert "error" not in ctx
    assert ctx["thesis"] == thesis.dict()
    assert ctx["observations"] == [o.dict() for o in observations]
    assert ctx["risk_snapshot"] == risk.dict()

    # sanity: we actually called the expected DataAccess methods
    assert data_access.calls["get_thesis"] == 1
    assert data_access.calls["get_observations_for_thesis"] == 1
    assert data_access.calls["get_risk_snapshot"] == 1


def test_build_thesis_context_missing_thesis():
    data_access = DummyDataAccess(thesis=None)
    builder = ContextBuilder(data_access)

    ctx = builder.build_thesis_context(thesis_id=999)

    assert ctx == {"error": "thesis_not_found"}
    assert data_access.calls["get_thesis"] == 1
    # When thesis is missing, builder should not need to hit other calls
    assert data_access.calls["get_observations_for_thesis"] == 0
    assert data_access.calls["get_risk_snapshot"] == 0


def test_build_multi_thesis_context():
    theses = [StubThesis(1), StubThesis(2)]
    data_access = DummyDataAccess(theses=theses)
    builder = ContextBuilder(data_access)

    ctx = builder.build_multi_thesis_context()

    assert "theses" in ctx
    assert ctx["theses"] == [t.dict() for t in theses]
    assert data_access.calls["get_all_theses"] == 1


def test_build_intuition_context_passthrough():
    data_access = DummyDataAccess()
    builder = ContextBuilder(data_access)

    question = "Why did we add this position?"
    recalled = [
        {"observation_id": 1, "text": "past note A"},
        {"observation_id": 2, "text": "past note B"},
    ]

    ctx = builder.build_intuition_context(question=question, recalled_obs=recalled)

    assert ctx["question"] == question
    assert ctx["recalled_observations"] == recalled
    # Should not call any DataAccess methods for this helper
    assert all(count == 0 for count in data_access.calls.values())


def test_build_daily_context():
    recent_obs = [StubObservation(1), StubObservation(2)]
    risk = StubRiskSnapshot("daily-snapshot")

    data_access = DummyDataAccess(
        recent_observations=recent_obs,
        risk_snapshot=risk,
    )
    builder = ContextBuilder(data_access)

    ctx = builder.build_daily_context()

    assert ctx["recent_observations"] == [o.dict() for o in recent_obs]
    assert ctx["risk_snapshot"] == risk.dict()

    assert data_access.calls["get_recent_observations"] == 1
    assert data_access.calls["get_risk_snapshot"] == 1