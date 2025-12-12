"""
Tests for ValidationService.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from voyager.services.v3.validation_service import ValidationService
from voyager.models.thesis import Thesis, LogicValidation, LogicLink, ThesisExpressionLeg
from voyager.models.common import Direction
from voyager.models.v3 import ValidationResult, Ambiguity, ResolvedLink, CausalLink
from voyager.quant.quant_service import RelationshipStrengthResult


@pytest.fixture
def mock_query_translator():
    """Mock QueryTranslator"""
    translator = AsyncMock()
    return translator


@pytest.fixture
def mock_quant_service():
    """Mock QuantService"""
    quant = MagicMock()
    return quant


@pytest.fixture
def mock_validation_repo():
    """Mock LogicValidationRepository"""
    repo = MagicMock()
    return repo


@pytest.fixture
def mock_thesis_repo():
    """Mock ThesisRepository"""
    repo = MagicMock()
    return repo


@pytest.fixture
def sample_thesis():
    """Sample thesis"""
    return Thesis(
        id="test_thesis_1",
        title="Gold vs Real Yields",
        hypothesis="Rising real yields will pressure gold prices",
        drivers=["Fed tightening"],
        disconfirmers=["Flight to safety"],
        expression=[
            ThesisExpressionLeg(asset="GLD", direction=Direction.LONG, size_pct=100.0)
        ],
        start_date="2024-01-01",
        review_date=None,
        status="WATCHLIST",
        tags=["test"],
        monitor_indices=["DXY"]
    )


@pytest.fixture
def validation_service(mock_query_translator, mock_quant_service, mock_validation_repo, mock_thesis_repo):
    """ValidationService instance with mocked dependencies"""
    return ValidationService(
        query_translator=mock_query_translator,
        quant_service=mock_quant_service,
        validation_repo=mock_validation_repo,
        thesis_repo=mock_thesis_repo
    )


@pytest.mark.asyncio
async def test_validate_success(validation_service, mock_query_translator, mock_quant_service, 
                                mock_validation_repo, mock_thesis_repo, sample_thesis):
    """Test successful validation flow"""
    # Mock translator output - all resolved
    from voyager.models.v3 import QueryTranslatorOutput
    mock_query_translator.extract_and_resolve.return_value = QueryTranslatorOutput(
        links=[
            CausalLink(
                claim="Real yields lead to gold prices",
                concept_a="real yields",
                concept_b="gold",
                direction="negative"
            )
        ],
        resolved=[
            ResolvedLink(
                claim="Real yields lead to gold prices",
                series_a="DFII10",
                series_b="GLD",
                query_type="correlation",
                direction="negative"
            )
        ],
        ambiguities=[]
    )
    
    # Mock quant service result
    mock_quant_service.relationship_strength.return_value = RelationshipStrengthResult(
        correlation=-0.38,
        expected_direction="negative",
        actual_direction="negative",
        direction_matches=True,
        strength="weak",
        interpretation="weak",
        confidence="low",
        n_observations=100,
        p_value=0.01
    )
    
    result = await validation_service.validate(sample_thesis)
    
    assert result.status == "complete"
    assert len(result.links) == 1
    assert result.links[0].interpretation == "weak"
    mock_validation_repo.insert.assert_called_once()
    mock_thesis_repo.update_status.assert_called_once_with(sample_thesis.id, "VALIDATED")


@pytest.mark.asyncio
async def test_validate_with_ambiguities(validation_service, mock_query_translator, sample_thesis):
    """Test validation with ambiguities requiring clarification"""
    from voyager.models.v3 import QueryTranslatorOutput
    mock_query_translator.extract_and_resolve.return_value = QueryTranslatorOutput(
        links=[],
        resolved=[],
        ambiguities=[
            Ambiguity(
                concept="bonds",
                candidates=[
                    {"id": "TLT", "name": "20Y+ Treasury", "source": "TwelveData"},
                    {"id": "IEF", "name": "7-10Y Treasury", "source": "TwelveData"}
                ]
            )
        ]
    )
    
    result = await validation_service.validate(sample_thesis)
    
    assert result.status == "needs_clarification"
    assert len(result.ambiguities) == 1
    assert result.ambiguities[0].concept == "bonds"


@pytest.mark.asyncio
async def test_validate_no_links(validation_service, mock_query_translator, sample_thesis):
    """Test validation with no testable claims"""
    from voyager.models.v3 import QueryTranslatorOutput
    mock_query_translator.extract_and_resolve.return_value = QueryTranslatorOutput(
        links=[],
        resolved=[],
        ambiguities=[]
    )
    
    result = await validation_service.validate(sample_thesis)
    
    assert result.status == "complete"
    assert len(result.links) == 0
    assert "No testable" in result.error_message


@pytest.mark.asyncio
async def test_validate_with_clarifications(validation_service, mock_query_translator, mock_quant_service,
                                            mock_validation_repo, mock_thesis_repo, sample_thesis):
    """Test validation with PM clarifications"""
    from voyager.models.v3 import QueryTranslatorOutput
    
    # Mock resolved output after clarifications
    mock_query_translator.resolve_with_clarifications.return_value = QueryTranslatorOutput(
        links=[
            CausalLink(
                claim="Bonds affect yields",
                concept_a="bonds",
                concept_b="yields",
                direction="positive"
            )
        ],
        resolved=[
            ResolvedLink(
                claim="Bonds affect yields",
                series_a="TLT",
                series_b="DGS10",
                query_type="correlation",
                direction="positive"
            )
        ],
        ambiguities=[]
    )
    
    mock_quant_service.relationship_strength.return_value = RelationshipStrengthResult(
        correlation=0.65,
        expected_direction="positive",
        actual_direction="positive",
        direction_matches=True,
        strength="moderate",
        interpretation="supports",
        confidence="medium",
        n_observations=100,
        p_value=0.001
    )
    
    clarifications = {"bonds": "TLT"}
    result = await validation_service.validate_with_clarifications(sample_thesis, clarifications)
    
    assert result.status == "complete"
    assert len(result.links) == 1
    mock_validation_repo.insert.assert_called_once()


@pytest.mark.asyncio
async def test_validate_parse_failed(validation_service, mock_query_translator, sample_thesis):
    """Test handling of parse failure"""
    mock_query_translator.extract_and_resolve.side_effect = Exception("Parse error")
    
    result = await validation_service.validate(sample_thesis)
    
    assert result.status == "parse_failed"
    assert "Failed to parse" in result.error_message


@pytest.mark.asyncio
async def test_validate_quant_query_failure(validation_service, mock_query_translator, mock_quant_service,
                                            mock_validation_repo, mock_thesis_repo, sample_thesis):
    """Test handling of quant query failure"""
    from voyager.models.v3 import QueryTranslatorOutput
    mock_query_translator.extract_and_resolve.return_value = QueryTranslatorOutput(
        links=[],
        resolved=[
            ResolvedLink(
                claim="Test claim",
                series_a="DFII10",
                series_b="GLD",
                query_type="correlation",
                direction="negative"
            )
        ],
        ambiguities=[]
    )
    
    # Mock quant service failure
    mock_quant_service.relationship_strength.side_effect = Exception("Data not available")
    
    result = await validation_service.validate(sample_thesis)
    
    # Should continue with error link
    assert result.status == "complete"
    assert len(result.links) == 1
    assert "error" in result.links[0].interpretation.lower()


@pytest.mark.asyncio
async def test_get_latest_validation(validation_service, mock_validation_repo):
    """Test getting latest validation"""
    mock_validation = LogicValidation(
        id="val_123",
        thesis_id="test_thesis_1",
        links=[],
        created_at="2024-01-01T00:00:00Z"
    )
    mock_validation_repo.get_by_thesis.return_value = mock_validation
    
    result = validation_service.get_latest_validation("test_thesis_1")
    
    assert result == mock_validation
    mock_validation_repo.get_by_thesis.assert_called_once_with("test_thesis_1")
