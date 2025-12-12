"""
Integration tests for V3 API routes.
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, AsyncMock, patch
from typing import Optional

from voyager.api.main import app
from voyager.models.thesis import Thesis, ThesisStatus, ThesisSnapshot
from voyager.models.v3 import (
    ValidationResult,
    CritiqueSummary,
    CritiqueResponse,
    BacktestResult,
    BacktestMetrics,
    SizingResult,
    PortfolioImpact,
    Concern,
    EquityPoint,
)
from voyager.models.common import Direction


@pytest.fixture
def client():
    """FastAPI test client"""
    return TestClient(app)


@pytest.fixture
def mock_thesis_service():
    """Mock ThesisService (sync methods)"""
    return MagicMock()


@pytest.fixture
def mock_validation_service():
    """Mock ValidationService (async methods)"""
    return AsyncMock()


@pytest.fixture
def mock_critique_service():
    """Mock CritiqueService (async methods)"""
    return AsyncMock()


@pytest.fixture
def mock_backtest_service():
    """Mock BacktestService (sync methods)"""
    return MagicMock()


@pytest.fixture
def mock_sizing_service():
    """Mock SizingService (sync methods)"""
    return MagicMock()


@pytest.fixture
def sample_thesis():
    """Sample thesis for testing"""
    return Thesis(
        id="thesis_123",
        title="Test Thesis",
        hypothesis="Test hypothesis",
        drivers=["driver1"],
        disconfirmers=["disconfirmer1"],
        expression=[],
        start_date="2024-01-01",
        review_date=None,
        status=ThesisStatus.WATCHLIST,
        tags=["test"],
        monitor_indices=[],
        notes=None,
        risk_rails=None,
        final_size=None
    )


@pytest.fixture
def sample_backtest_result():
    """Sample backtest result"""
    return BacktestResult(
        id="bt_123",
        thesis_id="thesis_123",
        expression={"GLD": 0.7, "TIP": 0.3},
        period_start="2020-01-01",
        period_end="2023-12-31",
        metrics=BacktestMetrics(
            total_return=0.25,
            cagr=0.08,
            volatility=0.15,
            sharpe=0.53,
            max_drawdown=0.18
        ),
        equity_curve=[
            EquityPoint(date="2020-01-01", value=100.0),
            EquityPoint(date="2023-12-31", value=125.0)
        ],
        factor_exposure=None,
        iteration_count=1
    )


# ===========================================
# Thesis CRUD Tests
# ===========================================

class TestThesisCRUD:
    
    def test_create_thesis(self, client, mock_thesis_service, sample_thesis):
        """Test creating a thesis draft"""
        with patch('voyager.api.v3_routes.get_thesis_service_instance', return_value=mock_thesis_service):
            mock_thesis_service.create_draft.return_value = sample_thesis
            
            response = client.post("/api/v3/thesis", json={
                "title": "Test Thesis",
                "hypothesis": "Test hypothesis",
                "drivers": ["driver1"],
                "disconfirmers": ["disconfirmer1"],
                "expression": []
            })
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "created"
            assert data["thesis"]["id"] == "thesis_123"
            mock_thesis_service.create_draft.assert_called_once()
    
    def test_create_thesis_invalid_input(self, client, mock_thesis_service):
        """Test creating thesis with missing required fields"""
        with patch('voyager.api.v3_routes.get_thesis_service_instance', return_value=mock_thesis_service):
            response = client.post("/api/v3/thesis", json={
                "title": "Test",
                # Missing hypothesis, drivers, etc.
            })
            
            assert response.status_code == 422  # Validation error
    
    def test_get_thesis(self, client, mock_thesis_service, sample_thesis):
        """Test getting thesis by ID"""
        with patch('voyager.api.v3_routes.get_thesis_service_instance', return_value=mock_thesis_service):
            mock_thesis_service.get.return_value = sample_thesis
            
            response = client.get("/api/v3/thesis/thesis_123")
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ok"
            assert data["thesis"]["id"] == "thesis_123"
    
    def test_get_thesis_not_found(self, client, mock_thesis_service):
        """Test getting non-existent thesis"""
        with patch('voyager.api.v3_routes.get_thesis_service_instance', return_value=mock_thesis_service):
            mock_thesis_service.get.return_value = None
            
            response = client.get("/api/v3/thesis/nonexistent")
            
            assert response.status_code == 404
            assert "not found" in response.json()["detail"].lower()
    
    def test_update_thesis(self, client, mock_thesis_service, sample_thesis):
        """Test updating thesis fields"""
        with patch('voyager.api.v3_routes.get_thesis_service_instance', return_value=mock_thesis_service):
            updated_thesis = Thesis(**{**sample_thesis.model_dump(), "hypothesis": "Updated hypothesis"})
            mock_thesis_service.get.return_value = sample_thesis
            mock_thesis_service.update.return_value = updated_thesis
            
            response = client.patch("/api/v3/thesis/thesis_123", json={
                "hypothesis": "Updated hypothesis"
            })
            
            assert response.status_code == 200
            assert response.json()["status"] == "updated"
    
    def test_update_thesis_readonly_status(self, client, mock_thesis_service):
        """Test updating thesis in ACTIVE status (should fail)"""
        with patch('voyager.api.v3_routes.get_thesis_service_instance', return_value=mock_thesis_service):
            active_thesis = Thesis(
                id="thesis_active",
                title="Active Thesis",
                hypothesis="Test",
                drivers=[],
                disconfirmers=[],
                expression=[],
                start_date="2024-01-01",
                status=ThesisStatus.ACTIVE,
                tags=[]
            )
            mock_thesis_service.get.return_value = active_thesis
            mock_thesis_service.update.side_effect = ValueError("Cannot edit thesis in ACTIVE status")
            
            response = client.patch("/api/v3/thesis/thesis_active", json={"hypothesis": "New"})
            
            assert response.status_code == 400
    
    def test_list_snapshots(self, client, mock_thesis_service, sample_thesis):
        """Test listing thesis snapshots"""
        with patch('voyager.api.v3_routes.get_thesis_service_instance', return_value=mock_thesis_service):
            mock_thesis_service.get.return_value = sample_thesis
            snapshots = [
                ThesisSnapshot(
                    id="snap_1",
                    thesis_id="thesis_123",
                    snapshot_type="pre_critique",
                    content={},
                    created_at="2024-01-01T00:00:00Z"
                )
            ]
            mock_thesis_service.get_snapshots.return_value = snapshots
            
            response = client.get("/api/v3/thesis/thesis_123/snapshots")
            
            assert response.status_code == 200
            assert len(response.json()) == 1


# ===========================================
# Validation Tests
# ===========================================

class TestValidation:
    
    @pytest.mark.asyncio
    async def test_validate_returns_complete(self, client, mock_validation_service, mock_thesis_service, sample_thesis):
        """Test successful validation flow"""
        with patch('voyager.api.v3_routes.get_validation_service_instance', return_value=mock_validation_service), \
             patch('voyager.api.v3_routes.get_thesis_service_instance', return_value=mock_thesis_service):
            mock_thesis_service.get.return_value = sample_thesis
            mock_validation_service.validate.return_value = ValidationResult(
                status="complete",
                links=[],
                ambiguities=None,
                error_message=None
            )
            
            response = client.post("/api/v3/thesis/thesis_123/validate")
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "complete"
    
    @pytest.mark.asyncio
    async def test_validate_returns_ambiguities(self, client, mock_validation_service, mock_thesis_service, sample_thesis):
        """Test validation with ambiguities requiring clarification"""
        with patch('voyager.api.v3_routes.get_validation_service_instance', return_value=mock_validation_service), \
             patch('voyager.api.v3_routes.get_thesis_service_instance', return_value=mock_thesis_service):
            mock_thesis_service.get.return_value = sample_thesis
            mock_validation_service.validate.return_value = ValidationResult(
                status="needs_clarification",
                links=None,
                ambiguities=[{"concept": "bonds", "candidates": []}],
                error_message=None
            )
            
            response = client.post("/api/v3/thesis/thesis_123/validate")
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "needs_clarification"
            assert data["ambiguities"] is not None
    
    @pytest.mark.asyncio
    async def test_validate_thesis_not_found(self, client, mock_validation_service, mock_thesis_service):
        """Test validation for non-existent thesis"""
        with patch('voyager.api.v3_routes.get_validation_service_instance', return_value=mock_validation_service), \
             patch('voyager.api.v3_routes.get_thesis_service_instance', return_value=mock_thesis_service):
            mock_thesis_service.get.return_value = None
            
            response = client.post("/api/v3/thesis/nonexistent/validate")
            
            assert response.status_code == 404
    
    @pytest.mark.asyncio
    async def test_clarify_resolves_ambiguities(self, client, mock_validation_service, mock_thesis_service, sample_thesis):
        """Test clarification submission"""
        with patch('voyager.api.v3_routes.get_validation_service_instance', return_value=mock_validation_service), \
             patch('voyager.api.v3_routes.get_thesis_service_instance', return_value=mock_thesis_service):
            mock_thesis_service.get.return_value = sample_thesis
            mock_validation_service.validate_with_clarifications.return_value = ValidationResult(
                status="complete",
                links=[],
                ambiguities=None,
                error_message=None
            )
            
            response = client.post("/api/v3/thesis/thesis_123/validate/clarify", json={
                "resolutions": {"bonds": "TLT"}
            })
            
            assert response.status_code == 200
            assert response.json()["status"] == "complete"
    
    @pytest.mark.asyncio
    async def test_get_latest_validation(self, client, mock_validation_service, mock_thesis_service, sample_thesis):
        """Test fetching latest validation"""
        with patch('voyager.api.v3_routes.get_validation_service_instance', return_value=mock_validation_service), \
             patch('voyager.api.v3_routes.get_thesis_service_instance', return_value=mock_thesis_service):
            mock_thesis_service.get.return_value = sample_thesis
            mock_validation_service.get_latest_validation.return_value = {
                "id": "val_123",
                "thesis_id": "thesis_123",
                "links": []
            }
            
            response = client.get("/api/v3/thesis/thesis_123/validation")
            
            assert response.status_code == 200


# ===========================================
# Critique Tests
# ===========================================

class TestCritique:
    
    @pytest.mark.asyncio
    async def test_start_critique(self, client, mock_critique_service, mock_thesis_service, sample_thesis):
        """Test starting critique session"""
        with patch('voyager.api.v3_routes.get_critique_service_instance', return_value=mock_critique_service), \
             patch('voyager.api.v3_routes.get_thesis_service_instance', return_value=mock_thesis_service):
            mock_thesis_service.get.return_value = sample_thesis
            mock_critique_service.start.return_value = CritiqueSummary(
                concerns=[
                    Concern(
                        dimension="empirical_grounding",
                        severity="high",
                        summary="Test concern"
                    )
                ],
                opening_message="Test opening"
            )
            
            response = client.post("/api/v3/thesis/thesis_123/critique/start")
            
            assert response.status_code == 200
            data = response.json()
            assert "concerns" in data
            assert "opening_message" in data
    
    @pytest.mark.asyncio
    async def test_critique_message(self, client, mock_critique_service, mock_thesis_service, sample_thesis):
        """Test drill-down conversation"""
        with patch('voyager.api.v3_routes.get_critique_service_instance', return_value=mock_critique_service), \
             patch('voyager.api.v3_routes.get_thesis_service_instance', return_value=mock_thesis_service):
            mock_thesis_service.get.return_value = sample_thesis
            mock_critique_service.continue_conversation.return_value = CritiqueResponse(
                message="Test response",
                thesis_edit_suggestion=None
            )
            
            response = client.post("/api/v3/thesis/thesis_123/critique/message", json={
                "dimension": "empirical_grounding",
                "message": "I think..."
            })
            
            assert response.status_code == 200
            assert "message" in response.json()
    
    @pytest.mark.asyncio
    async def test_critique_not_started(self, client, mock_critique_service, mock_thesis_service, sample_thesis):
        """Test message without starting critique"""
        with patch('voyager.api.v3_routes.get_critique_service_instance', return_value=mock_critique_service), \
             patch('voyager.api.v3_routes.get_thesis_service_instance', return_value=mock_thesis_service):
            mock_thesis_service.get.return_value = sample_thesis
            mock_critique_service.continue_conversation.side_effect = ValueError("Critique not started")
            
            response = client.post("/api/v3/thesis/thesis_123/critique/message", json={
                "dimension": "empirical_grounding",
                "message": "Test"
            })
            
            assert response.status_code == 400
    
    @pytest.mark.asyncio
    async def test_complete_critique(self, client, mock_critique_service, mock_thesis_service, sample_thesis):
        """Test completing critique session"""
        with patch('voyager.api.v3_routes.get_critique_service_instance', return_value=mock_critique_service), \
             patch('voyager.api.v3_routes.get_thesis_service_instance', return_value=mock_thesis_service):
            mock_thesis_service.get.return_value = sample_thesis
            completed_thesis = Thesis(**{**sample_thesis.model_dump(), "status": ThesisStatus.CRITIQUED})
            mock_critique_service.complete.return_value = completed_thesis
            
            response = client.post("/api/v3/thesis/thesis_123/critique/complete")
            
            assert response.status_code == 200
            assert response.json()["status"] == "critique_completed"
    
    @pytest.mark.asyncio
    async def test_apply_critique_edit(self, client, mock_critique_service, mock_thesis_service, sample_thesis):
        """Test applying suggested edit"""
        with patch('voyager.api.v3_routes.get_critique_service_instance', return_value=mock_critique_service), \
             patch('voyager.api.v3_routes.get_thesis_service_instance', return_value=mock_thesis_service):
            mock_thesis_service.get.return_value = sample_thesis
            updated_thesis = Thesis(**{**sample_thesis.model_dump(), "hypothesis": "Updated"})
            mock_critique_service.apply_edit_suggestion.return_value = updated_thesis
            
            response = client.post("/api/v3/thesis/thesis_123/critique/apply-edit", json={
                "field": "hypothesis",
                "action": "replace",
                "value": "Updated"
            })
            
            assert response.status_code == 200
            assert response.json()["status"] == "edit_applied"


# ===========================================
# Backtest Tests
# ===========================================

class TestBacktest:
    
    def test_run_backtest(self, client, mock_backtest_service, mock_thesis_service, sample_thesis, sample_backtest_result):
        """Test executing backtest"""
        with patch('voyager.api.v3_routes.get_backtest_service_instance', return_value=mock_backtest_service), \
             patch('voyager.api.v3_routes.get_thesis_service_instance', return_value=mock_thesis_service):
            mock_thesis_service.get.return_value = sample_thesis
            mock_backtest_service.run.return_value = sample_backtest_result
            
            response = client.post("/api/v3/thesis/thesis_123/backtest")
            
            assert response.status_code == 200
            data = response.json()
            assert data["thesis_id"] == "thesis_123"
            assert "metrics" in data
    
    def test_run_backtest_with_dates(self, client, mock_backtest_service, mock_thesis_service, sample_thesis, sample_backtest_result):
        """Test backtest with custom date range"""
        with patch('voyager.api.v3_routes.get_backtest_service_instance', return_value=mock_backtest_service), \
             patch('voyager.api.v3_routes.get_thesis_service_instance', return_value=mock_thesis_service):
            mock_thesis_service.get.return_value = sample_thesis
            mock_backtest_service.run.return_value = sample_backtest_result
            
            response = client.post(
                "/api/v3/thesis/thesis_123/backtest",
                params={"start_date": "2020-01-01", "end_date": "2023-12-31"}
            )
            
            assert response.status_code == 200
            mock_backtest_service.run.assert_called_once()
    
    def test_backtest_invalid_dates(self, client, mock_backtest_service, mock_thesis_service, sample_thesis):
        """Test backtest with invalid date range"""
        with patch('voyager.api.v3_routes.get_backtest_service_instance', return_value=mock_backtest_service), \
             patch('voyager.api.v3_routes.get_thesis_service_instance', return_value=mock_thesis_service):
            mock_thesis_service.get.return_value = sample_thesis
            mock_backtest_service.run.side_effect = ValueError("Invalid date range")
            
            response = client.post(
                "/api/v3/thesis/thesis_123/backtest",
                params={"start_date": "invalid-date"}
            )
            
            assert response.status_code == 400
    
    def test_get_latest_backtest(self, client, mock_backtest_service, mock_thesis_service, sample_thesis, sample_backtest_result):
        """Test fetching latest backtest"""
        with patch('voyager.api.v3_routes.get_backtest_service_instance', return_value=mock_backtest_service), \
             patch('voyager.api.v3_routes.get_thesis_service_instance', return_value=mock_thesis_service):
            mock_thesis_service.get.return_value = sample_thesis
            mock_backtest_service.get_latest.return_value = sample_backtest_result
            
            response = client.get("/api/v3/thesis/thesis_123/backtest/latest")
            
            assert response.status_code == 200
            assert response.json()["thesis_id"] == "thesis_123"
    
    def test_list_backtest_history(self, client, mock_backtest_service, mock_thesis_service, sample_thesis, sample_backtest_result):
        """Test listing all backtests"""
        with patch('voyager.api.v3_routes.get_backtest_service_instance', return_value=mock_backtest_service), \
             patch('voyager.api.v3_routes.get_thesis_service_instance', return_value=mock_thesis_service):
            mock_thesis_service.get.return_value = sample_thesis
            mock_backtest_service.list_history.return_value = [sample_backtest_result]
            
            response = client.get("/api/v3/thesis/thesis_123/backtest/history")
            
            assert response.status_code == 200
            assert len(response.json()) == 1


# ===========================================
# Sizing Tests
# ===========================================

class TestSizing:
    
    def test_compute_sizing(self, client, mock_sizing_service, mock_thesis_service, mock_backtest_service,
                           sample_thesis, sample_backtest_result):
        """Test sizing calculation"""
        with patch('voyager.api.v3_routes.get_sizing_service_instance', return_value=mock_sizing_service), \
             patch('voyager.api.v3_routes.get_thesis_service_instance', return_value=mock_thesis_service), \
             patch('voyager.api.v3_routes.get_backtest_service_instance', return_value=mock_backtest_service):
            mock_thesis_service.get.return_value = sample_thesis
            mock_backtest_service.get_latest.return_value = sample_backtest_result
            mock_sizing_service.compute.return_value = SizingResult(
                historical_max_dd=0.18,
                tolerance=0.08,
                implied_size=0.444,
                position_cap=0.10,
                suggested_size=0.10,
                portfolio_impact=None
            )
            
            response = client.post("/api/v3/thesis/thesis_123/sizing", json={
                "max_dd_tolerance": 0.08,
                "position_cap": 0.10
            })
            
            assert response.status_code == 200
            data = response.json()
            assert data["suggested_size"] == 0.10
            assert data["historical_max_dd"] == 0.18
    
    def test_sizing_no_backtest(self, client, mock_sizing_service, mock_thesis_service, mock_backtest_service, sample_thesis):
        """Test sizing without backtest (should fail)"""
        with patch('voyager.api.v3_routes.get_sizing_service_instance', return_value=mock_sizing_service), \
             patch('voyager.api.v3_routes.get_thesis_service_instance', return_value=mock_thesis_service), \
             patch('voyager.api.v3_routes.get_backtest_service_instance', return_value=mock_backtest_service):
            mock_thesis_service.get.return_value = sample_thesis
            mock_backtest_service.get_latest.return_value = None
            
            response = client.post("/api/v3/thesis/thesis_123/sizing", json={
                "max_dd_tolerance": 0.08,
                "position_cap": 0.10
            })
            
            assert response.status_code == 400
            assert "backtest" in response.json()["detail"].lower()
    
    def test_sizing_invalid_constraints(self, client, mock_sizing_service, mock_thesis_service, mock_backtest_service,
                                       sample_thesis, sample_backtest_result):
        """Test sizing with invalid constraints"""
        with patch('voyager.api.v3_routes.get_sizing_service_instance', return_value=mock_sizing_service), \
             patch('voyager.api.v3_routes.get_thesis_service_instance', return_value=mock_thesis_service), \
             patch('voyager.api.v3_routes.get_backtest_service_instance', return_value=mock_backtest_service):
            mock_thesis_service.get.return_value = sample_thesis
            mock_backtest_service.get_latest.return_value = sample_backtest_result
            mock_sizing_service.compute.side_effect = ValueError("Invalid max DD")
            
            response = client.post("/api/v3/thesis/thesis_123/sizing", json={
                "max_dd_tolerance": -0.08,  # Invalid negative
                "position_cap": 0.10
            })
            
            assert response.status_code == 400
    
    def test_activate_thesis(self, client, mock_thesis_service, sample_thesis):
        """Test thesis activation"""
        with patch('voyager.api.v3_routes.get_thesis_service_instance', return_value=mock_thesis_service):
            mock_thesis_service.get.return_value = sample_thesis
            activated_thesis = Thesis(**{**sample_thesis.model_dump(), "status": ThesisStatus.ACTIVE})
            mock_thesis_service.activate.return_value = activated_thesis
            
            response = client.post("/api/v3/thesis/thesis_123/activate-with-rails", json={
                "final_size": 0.10,
                "max_dd_tolerance": 0.08,
                "position_cap": 0.10
            })
            
            assert response.status_code == 200
            assert response.json()["status"] == "activated"
    
    def test_activate_wrong_status(self, client, mock_thesis_service, sample_thesis):
        """Test activating thesis not in BACKTESTED status"""
        with patch('voyager.api.v3_routes.get_thesis_service_instance', return_value=mock_thesis_service):
            mock_thesis_service.get.return_value = sample_thesis
            mock_thesis_service.activate.side_effect = ValueError("Thesis must be BACKTESTED")
            
            response = client.post("/api/v3/thesis/thesis_123/activate-with-rails", json={
                "final_size": 0.10,
                "max_dd_tolerance": 0.08,
                "position_cap": 0.10
            })
            
            assert response.status_code == 400
