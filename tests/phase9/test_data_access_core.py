import pytest

from voyager.intelligence.context.data_access import DataAccess


# --- Helper fakes -----------------------------------------------------------

class DummyThesis:
    def __init__(self, thesis_id: int, title: str = "dummy"):
        self.id = thesis_id
        self.title = title


class DummyObservation:
    def __init__(self, obs_id: int, thesis_id: int, text: str = "obs"):
        self.id = obs_id
        self.text = text
        self.thesis_id = thesis_id


class ThesisRepoWithAll:
    """Has both list_all and list_recent; used to test preference for list_all."""

    def __init__(self):
        self._theses = {
            1: DummyThesis(1, "one"),
            2: DummyThesis(2, "two"),
        }
        self.calls = []

    def get_by_id(self, thesis_id: int):
        return self._theses.get(thesis_id)

    def list_all(self):
        self.calls.append("list_all")
        return list(self._theses.values())

    def list_recent(self, limit: int = 50):
        self.calls.append("list_recent")
        return list(self._theses.values())[:limit]


class ThesisRepoOnlyRecent:
    """Only list_recent exists; used to verify fallback path."""

    def __init__(self):
        self._theses = {
            1: DummyThesis(1, "one"),
            2: DummyThesis(2, "two"),
        }
        self.calls = []

    def get_by_id(self, thesis_id: int):
        return self._theses.get(thesis_id)

    def list_recent(self, limit: int = 50):
        self.calls.append("list_recent")
        return list(self._theses.values())[:limit]


class ThesisRepoMinimal:
    """Only get_by_id; DataAccess.get_all_theses will raise AttributeError in this case."""

    def __init__(self):
        self._theses = {
            1: DummyThesis(1, "one"),
        }

    def get_by_id(self, thesis_id: int):
        return self._theses.get(thesis_id)


class ObservationRepoBasic:
    def __init__(self):
        self._by_thesis = {
            1: [DummyObservation(1, 1, "obs 1"), DummyObservation(2, 1, "obs 2")],
            2: [],
        }
        self._recent = [DummyObservation(3, 1, "recent 1")]

    def list_for_thesis(self, thesis_id: int):
        return list(self._by_thesis.get(thesis_id, []))

    def list_recent(self, limit: int = 50):
        return self._recent[:limit]


class TradeRepoDummy:
    """Minimal trade repo; unused in these tests but required by DataAccess.__init__."""
    pass


def _new_data_access(thesis_repo=None, obs_repo=None):
    """
    Helper to construct a DataAccess instance with explicit repos.
    DataAccess.__init__ currently requires (thesis_repo, obs_repo, trade_repo).
    """
    if thesis_repo is None:
        thesis_repo = ThesisRepoMinimal()
    if obs_repo is None:
        obs_repo = ObservationRepoBasic()
    trade_repo = TradeRepoDummy()
    return DataAccess(thesis_repo, obs_repo, trade_repo)


# --- Tests: get_thesis ------------------------------------------------------


def test_get_thesis_returns_none_when_missing():
    repo = ThesisRepoMinimal()
    da = _new_data_access(thesis_repo=repo)

    result = da.get_thesis(thesis_id=999)
    assert result is None


def test_get_thesis_returns_thesis_when_present():
    repo = ThesisRepoMinimal()
    da = _new_data_access(thesis_repo=repo)

    result = da.get_thesis(thesis_id=1)
    assert result is repo._theses[1]
    assert result.id == 1
    assert result.title == "one"


# --- Tests: get_all_theses --------------------------------------------------


def test_get_all_theses_prefers_list_all_over_list_recent():
    repo = ThesisRepoWithAll()
    da = _new_data_access(thesis_repo=repo)

    theses = da.get_all_theses()
    assert "list_all" in repo.calls
    assert theses == list(repo._theses.values())


def test_get_all_theses_falls_back_to_list_recent_when_no_list_all():
    repo = ThesisRepoOnlyRecent()
    da = _new_data_access(thesis_repo=repo)

    theses = da.get_all_theses()
    assert "list_recent" in repo.calls
    assert theses == list(repo._theses.values())


# NOTE: We do NOT test behavior when thesis_repo lacks both list_all and list_recent,
# because the current DataAccess implementation would raise AttributeError in that case
# and production wiring is expected to supply repos with the needed methods.


# --- Tests: observation helpers --------------------------------------------


def test_get_observations_for_thesis_returns_list():
    obs_repo = ObservationRepoBasic()
    da = _new_data_access(obs_repo=obs_repo)

    obs = da.get_observations_for_thesis(thesis_id=1)
    assert isinstance(obs, list)
    assert len(obs) == 2
    assert all(isinstance(o, DummyObservation) for o in obs)


def test_get_recent_observations_uses_list_recent_if_available():
    obs_repo = ObservationRepoBasic()
    da = _new_data_access(obs_repo=obs_repo)

    obs = da.get_recent_observations()
    assert isinstance(obs, list)
    assert len(obs) == 1
    assert obs[0].text == "recent 1"
